"""Read-only, offline synthetic single-cell pseudobulk reference computation."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import statistics
from pathlib import Path, PurePosixPath

from codex_science.bulk_expression_pack import benjamini_hochberg, welch_test as _welch


STAGES = ("01-design", "02-qc", "03-aggregation", "04-comparison", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_DEPTH = 64
IDENTITIES = ("organism", "genome_version", "annotation_version", "identifier_namespace")
POSITIVE = {"supported", "replicated", "suggestive"}
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*|differentially\s+expressed)\b", re.I)
MAX_UNITS = 1000
MAX_CELL_TYPES = 100
OVERREACH = re.compile(
    r"\b(caus\w*|mechanis\w*|therap\w*|clinical\w*|efficac\w*|effective\w*|treat\w*|cure\w*|"
    r"prevent\w*|driv\w*|induc\w*|regulat\w*|activat\w*|repress\w*|bind\w*|affinit\w*|inhibit\w*|fate\w*|"
    r"trajector\w*|pseudotim\w*|truth|physical[\s-]+validity|"
    r"disease[\s-]+modif\w*|patient[\s-]+benefit\w*)\b", re.I,
)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|physical|clinical|truth", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _obj(value, label):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    return value


def _fields(value, allowed, label):
    value = _obj(value, label)
    _require(set(value) <= set(allowed), "invalid-record", f"{label} contains unknown fields")
    return value


def _items(value, label, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    return value


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), "invalid-record", f"{label} must be nonempty text")
    return value


def _names(value, label, empty=False):
    values = _items(value, label, empty)
    for item in values:
        _text(item, label)
    _require(len(set(values)) == len(values), "invalid-record", f"duplicate {label}")
    return values


def _number(value, label, low=0, high=1e100, integer=False):
    valid_type = type(value) is int if integer else type(value) in (int, float)
    _require(valid_type and abs(value) <= 1e100 and math.isfinite(value) and low <= value <= high,
             "invalid-record", f"{label} must be finite in [{low}, {high}]")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _int(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer", -1e100)


def _float(value):
    return _number(float(value), "JSON number", -1e100)


def _json_nodes(raw):
    # Upper bound before parsing: root, commas, and each non-empty container's first value.
    return 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))


def _json(raw):
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant, parse_int=_int, parse_float=_float), "JSON root")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            if type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds 64 levels")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children if type(child) in (dict, list))
        return root
    except (ValueError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: finite UTF-8 JSON object required; duplicate keys refused") from error


def specification_hash(value):
    """Canonical hash of a pack-local specification, never an attestation of timing."""
    try:
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                         allow_nan=False).encode()).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid-record: specification must be finite JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and not re.match(r"^[A-Za-z]:", value)
             and all(ord(character) >= 32 for character in value),
             "input-path", "artifact path must be canonical and bundle-relative")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    """Pin each directory component and retain its descriptor-relative identity."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-file", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-changed", "root ancestor changed during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            identities.append((opened.st_dev, opened.st_ino))
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


def _read(root, relative, *, bundle=None, checked=None):
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    directory = None
    try:
        directory = _open_root(root)[0] if bundle is None else os.dup(bundle.descriptor)
        for part in relative.parts[:-1]:
            before = os.lstat(part, dir_fd=directory)
            _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            try:
                opened = os.fstat(child)
                _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-changed", "artifact ancestor changed")
            except BaseException:
                os.close(child)
                raise
            os.close(directory)
            directory = child
        before = os.lstat(relative.name, dir_fd=directory)
        _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                 "input-file", "input must be a regular file at most 64 MiB")
        descriptor = os.open(relative.name, flags, dir_fd=directory)
        with os.fdopen(descriptor, "rb") as handle:
            opened = os.fstat(handle.fileno())
            _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                     and _signature(before) == _signature(opened),
                     "input-file", "input changed or is not a bounded regular file")
            signature = _signature(opened)
            if bundle is not None and relative.as_posix() == bundle.entry and bundle.entry not in bundle.cache:
                _require(signature == bundle.entry_signature, "input-file", "entry changed during root pinning")
            identity = signature[:2]
            cached = bundle.artifacts.get(identity) if bundle is not None else None
            if cached is not None:
                _require(signature == cached[2], "input-changed", "cached input changed")
                if checked is None or identity in checked:
                    return None, signature
            limit = MAX_BYTES
            if bundle is not None and checked is None:
                limit = min(limit, MAX_TOTAL_BYTES - bundle.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "total input byte budget exceeded")
            raw = handle.read(min(limit, opened.st_size) + 1)
            after = os.fstat(handle.fileno())
        _require(len(raw) <= MAX_BYTES and len(raw) == opened.st_size
                 and signature == _signature(after), "input-file", "input grew or changed while reading")
        if bundle is not None and checked is None:
            bundle.bytes_read += len(raw)
        return raw, signature
    except OSError as error:
        raise ValueError("input-file: unavailable regular file or symlinked component") from error
    finally:
        if directory is not None:
            os.close(directory)


class _Bundle:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        self.root = absolute.parent
        self.entry = absolute.name
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.nodes_read = 0
        self.descriptor = None
        try:
            # Record the entry before pinning so mutations during that walk are refused too.
            self.entry_signature = _signature(os.lstat(absolute))
            self.descriptor, self.root_identities = _open_root(self.root)
            self.pack = self.load({"path": absolute.name}, check_hash=False)
        except BaseException as error:
            self.close()
            if isinstance(error, OSError):
                raise ValueError("input-file: unavailable regular file or symlinked component") from error
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None

    def load(self, identity, schema=None, check_hash=True):
        identity = _fields(identity, ("path", "sha256"), "artifact identity")
        path = _relative(identity.get("path"))
        name = path.as_posix()
        if name not in self.cache:
            raw, signature = _read(self.root, path, bundle=self)
            key = signature[:2]
            if raw is not None:
                nodes = _json_nodes(raw)
                _require(nodes <= MAX_TOTAL_NODES - self.nodes_read,
                         "input-limit", "total JSON value budget exceeded")
                self.artifacts[key] = (_json(raw), hashlib.sha256(raw).hexdigest(), signature)
                self.nodes_read += nodes
            self.cache[name] = self.artifacts[key]
        value, digest, _ = self.cache[name]
        if check_hash:
            expected = identity.get("sha256")
            _require(type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected) is not None
                     and expected == digest, "input-hash", "artifact hash mismatch")
        if schema:
            _require(value.get("schema") == schema and value.get("fixture") is True,
                     "invalid-record", f"expected synthetic fixture {schema}")
        return value

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.root_identities, "input-changed", "bundle root replaced")
        finally:
            os.close(descriptor)

    def recheck(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = _read(self.root, _relative(name), bundle=self, checked=checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input was replaced or changed during validation")
            checked.add(current[:2])
        self._check_root()


def welch_test(first, second, minimum=2):
    """Two-sided Welch on log values, refusing degenerate biological replicates."""
    _number(minimum, "minimum donors", 2, integer=True)
    for group in (first, second):
        _items(group, "log values")
        _require(len(group) >= minimum, "insufficient-donors", "Welch requires the declared biological replicate minimum")
        for value in group:
            _number(value, "log value", -1e100)
        _require(statistics.variance(group) > 0, "degenerate-data", "zero within-condition variance is untestable")
    scale = max(1, *(abs(x) for x in first + second))
    result = _welch([x / scale for x in first], [x / scale for x in second])
    result["log2_fold_change"] *= scale
    _require(all(type(v) in (int, float) and math.isfinite(v) for v in result.values()),
             "degenerate-data", "non-finite Welch result")
    return result


def _spec(spec, genes):
    spec = _fields(spec, ("replicate_unit", "aggregation", "model", "minimum_donors", "alpha", "contrast",
                         "test_genes", "cell_types", "correction", "correction_scope", "qc"), "specification")
    _require(spec.get("replicate_unit") in ("donor", "biological_sample"),
             "pseudoreplication", "cells cannot be condition-test replicates")
    _require(spec.get("aggregation") in ("sum-raw-counts", "mean-raw-counts"),
             "aggregation-rule", "reference requires sum-raw-counts or mean-raw-counts")
    _require(spec.get("model") == "welch-log2-cpm", "unsupported-model", "reference requires welch-log2-cpm")
    _number(spec.get("minimum_donors"), "minimum_donors", 2, integer=True)
    _number(spec.get("alpha"), "alpha", 0, 1)
    contrast = _names(spec.get("contrast"), "contrast")
    _require(len(contrast) == 2, "invalid-record", "exactly two conditions required")
    tested = _names(spec.get("test_genes"), "test_genes")
    _require(set(tested) <= set(genes), "identifier-mismatch", "test gene missing from counts")
    _names(spec.get("cell_types"), "cell_types")
    _require(spec.get("correction") == "BH", "multiple-testing", "BH correction is mandatory")
    _require(spec.get("correction_scope") == "all-tested-gene-cell-type-pairs",
             "multiple-testing", "correct the complete tested set, never a post-test subset")
    qc = _fields(spec.get("qc"), ("min_genes", "min_counts", "min_cells", "gene_min_units", "max_mito_fraction"), "QC thresholds")
    for key in ("min_genes", "min_counts", "min_cells", "gene_min_units"):
        _number(qc.get(key), key, 1, integer=True)
    _number(qc.get("max_mito_fraction"), "max_mito_fraction", 0, 1)
    return spec


def _labels(bundle, pack, labels, cell_types, spec):
    assertions = _items(labels.get("labels"), "cell-type labels")
    _require(set(_names([_obj(x, "label").get("cell_type") for x in assertions], "label names")) == set(cell_types),
             "label-evidence", "every cell type needs recorded marker or reference evidence")
    own = list(pack["inputs"].values()) + _items(pack.get("study_outputs"), "study_outputs", True)
    for identity in own:
        bundle.load(identity)
    for label in assertions:
        _fields(label, ("cell_type", "method", "origin", "source", "genes", "reference_id"), "label")
        _require(label.get("method") in ("marker", "reference"), "label-evidence", "marker or reference evidence required")
        source = _obj(label.get("source"), "label source")
        source_path = _relative(source.get("path")).as_posix()
        origin = label.get("origin")
        _require(origin in ("external", "study"), "label-evidence", "label origin must be recorded")
        if origin == "external":
            _require(all(source_path != item["path"] and source.get("sha256") != item.get("sha256") for item in own),
                     "label-independence", "external evidence aliases a study input or output")
        record = bundle.load(source, "single-cell-pseudobulk-evidence-v1")
        _require(record.get("kind") == label["method"] + "-evidence"
                 and record.get("result") == label["method"] + "-support"
                 and label["cell_type"] in _names(record.get("cell_types"), "evidence cell types"),
                 "label-evidence", "source does not record evidence for the asserted label")
        markers = _names(label.get("genes"), "label genes", True)
        if label["method"] == "marker":
            _require(bool(markers) and set(markers) <= set(_names(record.get("genes"), "evidence genes")),
                     "label-evidence", "marker evidence must name the recorded marker genes")
        else:
            _require(_text(label.get("reference_id"), "reference_id") == record.get("reference_id"),
                     "label-evidence", "reference identity mismatch")
        _require(not set(markers).intersection(spec["test_genes"]) or pack["exploratory"],
                 "circular-label", "labels derived from tested genes require an exploratory label")


def _claims(bundle, pack, results):
    claims = _items(pack.get("claims"), "claims", True)
    _names([_obj(x, "claim").get("id") for x in claims], "claim ids", True)
    statuses = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
    for claim in claims:
        _fields(claim, ("id", "kind", "text", "status", "support", "cell_type", "gene_id"), "claim")
        text = _text(claim.get("text"), "claim text")
        _require(claim.get("kind") in ("descriptive", "associational") and OVERREACH.search(text) is None,
                 "claim-boundary", "only descriptive or associational statistical wording is allowed")
        status = claim.get("status")
        _require(type(status) is str and status in statuses, "claim-boundary", "invalid claim status")
        _require(status != "unavailable" or UNAVAILABLE_POSITIVE.search(text) is None, "claim-boundary",
                 "unavailable claim cannot assert positive evidence")
        support = _items(claim.get("support"), "claim support", True)
        _require(support or status == "unavailable", "unavailable-evidence", "missing records are unavailable, never negative evidence")
        for identity in support:
            evidence = bundle.load(identity, "single-cell-pseudobulk-evidence-v1")
            kind = _text(evidence.get("kind"), "evidence kind")
            result = _text(evidence.get("result"), "evidence result")
            _require("unavailable" not in (kind, result) or status == "unavailable", "unavailable-evidence",
                     "an unavailable record cannot support a positive or negative conclusion")
            _require(status not in POSITIVE or (NON_EVIDENCE.search(kind + " " + result) is None
                     and kind == "statistical-evidence" and result == "donor-level-association"),
                     "claim-evidence", "review approval or computed agreement cannot support a positive claim")
        if status in POSITIVE:
            _require(status != "replicated", "claim-boundary", "one synthetic study cannot establish independent replication")
            _require(not pack["exploratory"] or status == "suggestive", "claim-boundary", "exploratory claims remain suggestive")
            key = (claim.get("cell_type"), claim.get("gene_id"))
            _require(any((row["cell_type"], row["gene_id"]) == key and row["significant"] for row in results),
                     "claim-evidence", "positive association requires the declared donor-level BH threshold")


def _analyze(bundle):
    pack = _fields(bundle.pack, ("schema", "fixture", "stages", "inputs", "frozen_spec", "analysis_spec",
                   "frozen_sha256", "frozen_design_sha256", "freeze_before_results", "exploratory",
                   "included_units", "study_outputs", "claims"), "pack")
    _require(pack.get("schema") == "single-cell-pseudobulk-pack-v1" and pack.get("fixture") is True,
             "invalid-record", "reference accepts single-cell-pseudobulk-pack-v1 synthetic fixtures only")
    _require(pack.get("stages") == list(STAGES), "stage-order", "five stages must retain their fixed order")
    inputs = _fields(pack.get("inputs"), ("design", "counts", "gene_sets", "labels"), "inputs")
    design = bundle.load(inputs.get("design"), "single-cell-pseudobulk-design-v1")
    counts = bundle.load(inputs.get("counts"), "single-cell-pseudobulk-counts-v1")
    _require("seed" not in counts or type(counts["seed"]) is int,
             "invalid-record", "seed must be an integer when declared")
    gene_sets = bundle.load(inputs.get("gene_sets"), "single-cell-pseudobulk-gene-sets-v1")
    labels = bundle.load(inputs.get("labels"), "single-cell-pseudobulk-labels-v1")
    for key in IDENTITIES:
        value = _text(design.get(key), key)
        _require(all(record.get(key) == value for record in (counts, gene_sets, labels)),
                 "identifier-mismatch", f"{key} differs between counts, labels, design or gene sets")
    genes = _names(counts.get("genes"), "gene ids")
    gene_index = {gene: position for position, gene in enumerate(genes)}
    mitochondrial = _names(counts.get("mitochondrial_genes"), "mitochondrial genes", True)
    _require(set(mitochondrial) <= set(genes), "identifier-mismatch", "mitochondrial genes missing from counts")
    for collection in _items(gene_sets.get("sets"), "gene sets"):
        _obj(collection, "gene set")
        _text(collection.get("id"), "gene set id")
        _require(set(_names(collection.get("genes"), "gene-set members", True)) <= set(genes),
                 "identifier-mismatch", "gene-set identifiers absent from counts")
    spec = _spec(pack.get("analysis_spec"), genes)
    frozen = _spec(pack.get("frozen_spec"), genes)
    exploratory = _boolean(pack.get("exploratory"), "exploratory")
    _require(pack.get("frozen_sha256") == specification_hash(frozen)
             and pack.get("frozen_design_sha256") == inputs["design"]["sha256"],
             "freeze-hash", "design and pre-result specification must be frozen and hashed")
    _require(pack.get("freeze_before_results") is True, "freeze-order", "freeze must precede results")
    _require(frozen == spec or exploratory, "post-result-change", "changed QC or aggregation rules require an exploratory label")
    units = _items(design.get("biological_units"), "biological_units")
    _require(len(units) <= MAX_UNITS, "invalid-record", f"at most {MAX_UNITS} units are accepted")
    for unit in units:
        _obj(unit, "biological unit")
        for key in ("id", "donor_id", "condition", "batch", "chemistry"):
            _text(unit.get(key), key)
    ids = _names([unit["id"] for unit in units], "biological unit ids")
    _require(len({x["donor_id"] for x in units}) == len(units), "donor-confounding",
             "repeated samples from one donor are not independent replicates; paired models need a gated extension")
    adjustment = _names(design.get("adjustment"), "adjustment", True)
    _require("donor" not in adjustment, "donor-confounding", "donor fixed effects nested in condition cannot identify a condition effect")
    _require(not adjustment, "unsupported-model", "reference cannot adjust covariates")
    _require(set(x["condition"] for x in units) == set(spec["contrast"]), "invalid-record", "unit conditions differ from contrast")
    for key in ("batch", "chemistry"):
        mixed = any(len({x["condition"] for x in units if x[key] == value}) == 2 for value in {x[key] for x in units})
        _require(mixed, key + "-confounding", f"{key} is perfectly confounded with condition")
    cells = _items(counts.get("cells"), "cells")
    _names([_obj(cell, "cell").get("id") for cell in cells], "cell ids")
    cell_types = _names(labels.get("cell_types"), "cell types")
    _require(len(cell_types) <= MAX_CELL_TYPES, "invalid-record", f"at most {MAX_CELL_TYPES} cell types are accepted")
    _require(set(spec["cell_types"]) <= set(cell_types), "label-evidence", "tested cell type has no evidence")
    _labels(bundle, pack, labels, cell_types, spec)
    grouped = {(unit, cell_type): [] for unit in ids for cell_type in cell_types}
    exclusions, cell_qc = [], []
    mito_indices = [gene_index[gene] for gene in mitochondrial]
    qc = spec["qc"]
    for cell in cells:
        _require(cell.get("unit_id") in ids and cell.get("cell_type") in cell_types,
                 "invalid-record", "cell unit or cell type missing from design")
        values = _items(cell.get("counts"), "cell counts")
        _require(len(values) == len(genes), "invalid-record", "cell counts and genes differ in length")
        for value in values:
            _number(value, "count", integer=True)
        doublet = _boolean(cell.get("doublet"), "supplied doublet call")
        total = sum(values)
        detected = sum(x > 0 for x in values)
        mito = sum(values[i] for i in mito_indices) / total if total else 1.0
        reasons = [name for name, failed in (("min_counts", total < qc["min_counts"]),
                   ("min_genes", detected < qc["min_genes"]), ("max_mito_fraction", mito > qc["max_mito_fraction"]),
                   ("supplied-doublet", doublet)) if failed]
        measurement = {"cell_id": cell["id"], "counts": total, "genes": detected,
                       "mito_fraction": mito, "reasons": reasons}
        cell_qc.append(measurement)
        if reasons:
            exclusions.append(measurement)
        else:
            grouped[cell["unit_id"], cell["cell_type"]].append(values)
    retained, bulk, excluded_units = [], [], []
    for unit in units:
        for cell_type in cell_types:
            rows = grouped[unit["id"], cell_type]
            identity = {"unit_id": unit["id"], "cell_type": cell_type}
            if len(rows) < qc["min_cells"]:
                excluded_units.append({**identity, "cells": len(rows), "threshold": qc["min_cells"], "reason": "min_cells"})
            elif cell_type in spec["cell_types"]:
                retained.append(identity)
                divisor = len(rows) if spec["aggregation"] == "mean-raw-counts" else 1
                bulk.append({**identity, "condition": unit["condition"], "batch": unit["batch"], "chemistry": unit["chemistry"],
                             "cells": len(rows), "counts": [sum(row[i] for row in rows) / divisor for i in range(len(genes))]})
    included = _items(pack.get("included_units"), "included_units", True)
    for entry in included:
        _obj(entry, "included unit")
    _require(included == retained, "minimum-cells", "included units must exactly match QC-eligible biological unit/cell-type pairs")
    results, excluded_genes = [], []
    for cell_type in spec["cell_types"]:
        rows = [row for row in bulk if row["cell_type"] == cell_type]
        library = {id(row): sum(row["counts"]) for row in rows}
        groups = [[row for row in rows if row["condition"] == condition] for condition in spec["contrast"]]
        _require(all(len(group) >= spec["minimum_donors"] for group in groups), "insufficient-donors",
                 "retained donors per condition are below the declared minimum")
        for factor in ("batch", "chemistry"):
            _require(any(len({row["condition"] for row in rows if row[factor] == value}) == 2 for value in {row[factor] for row in rows}),
                     factor + "-confounding", f"QC retained perfectly confounded {factor}")
        for gene in spec["test_genes"]:
            index = gene_index[gene]
            expressing = sum(row["counts"][index] > 0 for row in rows)
            if expressing < qc["gene_min_units"]:
                excluded_genes.append({"gene_id": gene, "cell_type": cell_type, "units": expressing,
                                       "threshold": qc["gene_min_units"], "reason": "gene_min_units"})
                continue
            values = [[math.log2(1 + 1e6 * row["counts"][index] / library[id(row)]) for row in group] for group in groups]
            results.append({"gene_id": gene, "cell_type": cell_type, "donors": [len(g) for g in groups],
                            **welch_test(*values, minimum=spec["minimum_donors"])})
    _require(bool(results), "degenerate-data", "no genes pass the predeclared gene QC threshold")
    for result, adjusted in zip(results, benjamini_hochberg([row["p_value"] for row in results])):
        result.update(q_value=adjusted, significant=adjusted <= spec["alpha"])
    _claims(bundle, pack, results)
    return {"schema": "single-cell-pseudobulk-result-v1", "fixture": True, "stages": list(STAGES),
            "evidence_level": "statistical-only", "review": "unavailable", "exploratory": exploratory,
            "specification_sha256": specification_hash(spec), "cell_qc": cell_qc, "excluded_cells": exclusions,
            "excluded_units": excluded_units, "excluded_genes": excluded_genes, "pseudobulk": bulk,
            "differential": results, "limitations": ["Synthetic software fixture; no biological validity established.",
                "Unadjusted log2(CPM+1) Welch is a reference, not a count-dispersion model or a power calculation.",
                "Batch, chemistry, label provenance and historical freeze declarations still require independent review.",
                "Null results and failed QC controls are retained; absence of a record remains unavailable."]}


def validate_single_cell_pseudobulk_pack(path: Path | str) -> dict:
    """Validate snapshots, compute donor-level evidence and recheck all input hashes; write nothing."""
    try:
        with _Bundle(path) as bundle:
            result = _analyze(bundle)
            bundle.recheck()
            result["input_identities"] = [{"path": name, "sha256": item[1]} for name, item in sorted(bundle.cache.items())]
            return result
    except OSError as error:
        raise ValueError("input-file: unavailable regular file or symlinked component") from error
    except (TypeError, KeyError, IndexError, RecursionError, OverflowError, ZeroDivisionError) as error:
        raise ValueError("invalid-record: malformed or numerically degenerate synthetic bundle") from error
    except ValueError as error:
        if re.match(r"^[a-z][a-z-]*: ", str(error)):
            raise
        raise ValueError("invalid-record: malformed synthetic bundle") from error
