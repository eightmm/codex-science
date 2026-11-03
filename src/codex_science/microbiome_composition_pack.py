"""Read-only, offline taxon-count admission and bounded stdlib reference computation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import random
import re
import stat
import statistics

from codex_science.bulk_expression_pack import welch_test as _welch


STAGES = ("01-design", "02-qc", "03-composition", "04-taxa", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_RECORDS = 128
MAX_ITEMS = 20000
MAX_DEPTH = 32
MAX_TEXT = 4096
MAX_NUMBER = 1e12
MAX_SAMPLES = 64
MAX_TAXA = 256
MAX_CELLS = 16384
MAX_PERMUTATIONS = 999
MAX_PERMUTATION_WORK = 2000000
MAX_CLAIMS = 128
MAX_COUNT = 1000000000
COVARIATES = ("batch", "extraction_batch", "sequencing_run")
POSITIVE = {"supported", "replicated", "suggestive"}
STATUSES = POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"}
WORDING_FAMILIES = (
    "caus*, mechanis*, therap*, clinic*, efficac*, effective*, treat*, cure*, prevent*, "
    "recommend*, prescri*, bind*, affinit*, inhibit*, activat*, regulat*, "
    "drive/drives/driv*, induc*"
)
OVERREACH = re.compile(
    r"\b(?:caus\w*|mechanis\w*|therap\w*|clinic\w*|efficac\w*|effective\w*|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|prescri\w*|bind\w*|affinit\w*|"
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|truth|"
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|biomarker\w*|dysbiosis)\b", re.I,
)
ABSOLUTE = re.compile(r"\b(?:absolute\w*|(?:microbial|taxon|total)[\s-]+load)\b", re.I)
ABSENCE = re.compile(r"\b(?:absen\w*|eradicated)\b", re.I)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _fields(value, names, label):
    _require(type(value) is dict and set(value) == set(names.split()),
             "invalid-record", f"{label} fields differ from the pack-local schema")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} requires bounded nonempty text")
    return value


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and low <= value <= high
             and math.isfinite(value), "invalid-record", f"{label} has invalid numeric type or range")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds the declared limit")
    _require(empty or bool(value), "invalid-record", f"{label} cannot be empty")
    return value


def _names(value, label, limit, empty=False):
    _items(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "duplicate-identity", f"duplicate {label}")
    return value


def _record(value, schema, names):
    _fields(value, "schema schema_version fixture " + names, schema)
    _require(value["schema"] == schema and value["fixture"] == "synthetic fixture",
             "invalid-record", "expected a labelled synthetic fixture record")
    _number(value["schema_version"], "schema_version", 1, 1, True)
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many JSON object fields")
    value = {}
    for key, item in pairs:
        _require(key not in value, "invalid-json", "duplicate JSON key")
        value[key] = item
    return value


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _integer(value):
    _require(len(value.lstrip("-")) <= 13, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer", -MAX_NUMBER)


def _json(raw, allowance):
    # This conservative upper bound also counts commas inside strings.
    nodes = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_constant=_constant, parse_int=_integer,
                           parse_float=lambda text: _number(float(text), "JSON number", -MAX_NUMBER))
        _require(type(value) is dict, "invalid-json", "JSON root must be an object")
        pending = [(value, 0)]
        while pending:
            item, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "input-limit", "JSON nesting exceeds MAX_DEPTH")
            if type(item) in (dict, list):
                _require(len(item) <= MAX_ITEMS, "input-limit", "JSON container exceeds MAX_ITEMS")
                if type(item) is dict:
                    for key in item:
                        _text(key, "JSON key")
                    children = item.values()
                else:
                    children = item
                pending.extend((child, depth + 1) for child in children)
            elif type(item) is str:
                _text(item, "JSON text")
        return value, nodes
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value
             and all(ord(c) >= 32 for c in value), "input-path", "canonical bundle-relative path required")
    return path


def _identity(value):
    _fields(value, "path sha256", "artifact identity")
    _relative(value["path"])
    _text(value["sha256"], "sha256")
    _require(re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None,
             "input-hash", "lowercase SHA-256 required")
    return value


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    """Pin every ancestor before opening any artifact relative to the final descriptor."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    identities = []
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "input-root", "root ancestor changed during pinning")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
            identities.append((opened.st_dev, opened.st_ino))
        current = os.stat(root, follow_symlinks=False)
        opened = os.fstat(descriptor)
        _require(root.resolve(strict=True) == root and stat.S_ISDIR(current.st_mode)
                 and (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino),
                 "input-root", "root changed or resolved through a symlink")
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        _require(isinstance(path, (str, Path)), "input-path", "bundle must be a path string or Path")
        entry_text = _text(str(path), "bundle path")
        _require(not any(ord(char) < 32 for char in entry_text), "input-path", "control characters in bundle path")
        absolute = Path(os.path.abspath(path))
        self.root, self.entry = absolute.parent, absolute.name
        self.fd, self.identities = _open_root(self.root)
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = self.nodes_read = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def _read(self, path, checked=None):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory = os.dup(self.fd)
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact directory")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    os.close(child)
                    raise ValueError("input-file: artifact directory replaced")
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                actual = os.fstat(handle.fileno())
                _require(stat.S_ISREG(actual.st_mode) and actual.st_size <= MAX_BYTES
                         and _signature(before) == _signature(actual),
                         "input-file", "artifact changed during open")
                signature = _signature(actual)
                identity = signature[:2]
                if identity in self.artifacts:
                    _require(signature == self.artifacts[identity][2], "input-changed", "cached input changed")
                    if checked is None or identity in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(actual.st_size <= limit, "input-limit", "aggregate artifact bytes exceed MAX_TOTAL_BYTES")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == actual.st_size and signature == _signature(after),
                     "input-file", "artifact grew or changed during bounded read")
            return raw, signature
        finally:
            os.close(directory)

    def snapshot(self, name):
        path = _relative(name)
        if name not in self.cache:
            _require(len(self.cache) < MAX_RECORDS, "input-limit", "too many artifact paths")
            raw, signature = self._read(path)
            identity = signature[:2]
            if raw is not None:
                value, nodes = _json(raw, MAX_TOTAL_NODES - self.nodes_read)
                self.artifacts[identity] = value, hashlib.sha256(raw).hexdigest(), signature
                self.bytes_read += len(raw)
                self.nodes_read += nodes
            self.cache[name] = self.artifacts[identity]
        value, digest, _ = self.cache[name]
        return value, digest

    def load(self, identity):
        _identity(identity)
        value, digest = self.snapshot(identity["path"])
        _require(identity["sha256"] == digest, "input-hash", "artifact hash differs from parsed bytes")
        return value

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle root replaced during validation")
        finally:
            os.close(descriptor)

    def recheck(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self._read(_relative(name), checked)
            _require(signature == current and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "artifact replaced during validation")
            checked.add(current[:2])
        self._check_root()


def _specification(spec):
    _fields(spec, "contrast biological_unit covariates minimum_read_depth prevalence_filter zero_rule "
            "pseudocount diversity_indices distance permutations seed permutation_strata fdr_alpha minimum_group_size",
            "design specification")
    _require(len(_names(spec["contrast"], "contrast", 2)) == 2,
             "invalid-record", "exactly two distinct conditions required")
    _require(spec["biological_unit"] == "subject", "technical-replicates", "independent subject units required")
    _require(_names(spec["covariates"], "covariates", 3) == list(COVARIATES),
             "invalid-record", "batch, extraction batch and sequencing run must be frozen")
    _number(spec["minimum_read_depth"], "minimum_read_depth", 1, MAX_COUNT, True)
    _number(spec["prevalence_filter"], "prevalence_filter", 0, 1)
    _require(spec["zero_rule"] == "add-pseudocount", "zero-rule", "additive pseudocount rule required")
    _number(spec["pseudocount"], "pseudocount", 1e-9, 1000000)
    _require(_names(spec["diversity_indices"], "diversity indices", 2) == ["shannon", "simpson"]
             and spec["distance"] == "aitchison", "composition-method", "Shannon, Simpson and Aitchison required")
    _number(spec["permutations"], "permutations", 1, MAX_PERMUTATIONS, True)
    _number(spec["seed"], "seed", 0, 4294967295, True)
    strata = _names(spec["permutation_strata"], "permutation strata", 3)
    _require(set(strata) == set(COVARIATES), "permutation-contract", "permutations must respect all frozen covariates")
    _number(spec["fdr_alpha"], "fdr_alpha", 1e-9, 0.5)
    _number(spec["minimum_group_size"], "minimum_group_size", 2, MAX_SAMPLES, True)
    return spec


def _table(table, spec):
    _record(table, "microbiome-count-table-v1", "taxa samples")
    taxa = _names(table["taxa"], "taxon IDs", MAX_TAXA)
    samples = _items(table["samples"], "samples", MAX_SAMPLES)
    _require(len(taxa) * len(samples) <= MAX_CELLS, "input-limit", "count table exceeds MAX_CELLS")
    sample_ids, subject_ids, retained, blanks, qc = set(), set(), [], [], []
    for sample in samples:
        _fields(sample, "sample_id biological_id condition batch extraction_batch sequencing_run control counts", "sample")
        for key in ("sample_id", "biological_id", "condition", *COVARIATES, "control"):
            _text(sample[key], key)
        _require(sample["sample_id"] not in sample_ids, "duplicate-identity", "duplicate sample ID")
        sample_ids.add(sample["sample_id"])
        counts = _items(sample["counts"], "sample counts", MAX_TAXA)
        _require(len(counts) == len(taxa), "invalid-record", "one integer count per taxon required")
        for count in counts:
            _number(count, "taxon count", 0, MAX_COUNT, True)
        depth = sum(counts)
        control = sample["control"]
        _require(control in ("biological", "negative-extraction-blank"), "invalid-record", "unknown control type")
        if control == "negative-extraction-blank":
            blanks.append(sample)
            reason = "negative-control"
        else:
            _require(sample["condition"] in spec["contrast"], "invalid-record", "unknown sample condition")
            _require(sample["biological_id"] not in subject_ids, "technical-replicates",
                     "technical replicates cannot count as independent subjects")
            subject_ids.add(sample["biological_id"])
            reason = "low-depth" if depth < spec["minimum_read_depth"] else "retained"
            if reason == "retained":
                retained.append(sample)
        qc.append({"sample_id": sample["sample_id"], "depth": depth, "retained": reason == "retained", "reason": reason})
    _require(bool(blanks), "missing-controls", "negative extraction blanks must remain visible")
    for group in spec["contrast"]:
        _require(sum(sample["condition"] == group for sample in retained) >= spec["minimum_group_size"],
                 "insufficient-units", "too few retained independent subjects per condition")
    for covariate in COVARIATES:
        levels = {}
        for sample in retained:
            levels.setdefault(sample[covariate], set()).add(sample["condition"])
        _require(any(len(groups) > 1 for groups in levels.values()), "confounded-design",
                 f"{covariate} is perfectly confounded with condition")
    _require(spec["permutations"] * len(retained) ** 2 <= MAX_PERMUTATION_WORK,
             "input-limit", "permutation distance work exceeds MAX_PERMUTATION_WORK")
    return taxa, retained, blanks, qc


def clr_transform(counts, pseudocount):
    """Add the frozen pseudocount in count space, then center natural logarithms."""
    _items(counts, "CLR counts", MAX_TAXA)
    _number(pseudocount, "pseudocount", 1e-9, 1000000)
    for count in counts:
        _number(count, "CLR count", 0, MAX_COUNT, True)
    _require(len(counts) >= 2 and sum(counts) > 0, "degenerate-composition", "two taxa and positive filtered depth required")
    logs = [math.log(count + pseudocount) for count in counts]
    center = math.fsum(logs) / len(logs)
    return [value - center for value in logs]


def alpha_diversity(counts):
    """Shannon natural-log entropy and Simpson 1-D on the same filtered raw counts."""
    _items(counts, "diversity counts", MAX_TAXA)
    for count in counts:
        _number(count, "diversity count", 0, MAX_COUNT, True)
    total = sum(counts)
    _require(total > 0, "degenerate-composition", "positive filtered depth required")
    proportions = [count / total for count in counts if count > 0]
    return {"shannon": -math.fsum(p * math.log(p) for p in proportions),
            "simpson": 1 - math.fsum(p * p for p in proportions)}


def welch_test(first, second, minimum=2):
    """Two-sided Welch on CLR values; refuse either zero-variance group."""
    _number(minimum, "minimum_group_size", 2, MAX_SAMPLES, True)
    for group in (first, second):
        _items(group, "Welch group", MAX_SAMPLES)
        _require(len(group) >= minimum, "insufficient-units", "too few independent observations for Welch")
        for value in group:
            _number(value, "CLR value", -MAX_NUMBER)
    scale = max(abs(value) for group in (first, second) for value in group)
    _require(scale > 0, "degenerate-variance", "zero within-group variance")
    scaled = [[value / scale for value in group] for group in (first, second)]
    _require(all(statistics.variance(group) > 0 for group in scaled),
             "degenerate-variance", "zero within-group variance")
    result = _welch(*scaled)
    return {"clr_difference": math.fsum(second) / len(second) - math.fsum(first) / len(first),
            "t": result["t"], "df": result["df"], "p_value": result["p_value"]}


def benjamini_hochberg(values):
    """Adjust the complete tested taxon family in input order."""
    _items(values, "BH family", MAX_TAXA, True)
    for value in values:
        _number(value, "p value", 0, 1)
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted, running = [1.0] * len(values), 1.0
    for rank in range(len(values), 0, -1):
        index = order[rank - 1]
        running = min(running, values[index] * (len(values) / rank))
        adjusted[index] = running
    return adjusted


def _pseudo_f(squared, labels, total):
    groups = ([i for i, label in enumerate(labels) if label == 0],
              [i for i, label in enumerate(labels) if label == 1])
    within = math.fsum(math.fsum(squared[i][j] for i in group for j in group if i < j) / len(group)
                       for group in groups)
    _require(within > 0, "degenerate-permutation", "zero within-group distance variation")
    return max(0.0, total - within) / (within / (len(labels) - 2))


def reference_computation(specification, count_table):
    """Return statistical composition evidence from already-counted synthetic fixtures."""
    spec = _specification(specification)
    taxa, samples, blanks, qc = _table(count_table, spec)
    contaminants = {j for j in range(len(taxa)) if any(blank["counts"][j] > 0 for blank in blanks)}
    prevalence = [sum(sample["counts"][j] > 0 for sample in samples) / len(samples) for j in range(len(taxa))]
    keep = [j for j in range(len(taxa)) if j not in contaminants and prevalence[j] >= spec["prevalence_filter"]]
    _require(len(keep) >= 2, "degenerate-composition", "fewer than two taxa survive the frozen filter and controls")
    filtered = [[sample["counts"][j] for j in keep] for sample in samples]
    clr = [clr_transform(counts, spec["pseudocount"]) for counts in filtered]
    alpha = [{"sample_id": sample["sample_id"], **alpha_diversity(counts)} for sample, counts in zip(samples, filtered)]
    squared = [[math.fsum((a - b) ** 2 for a, b in zip(first, second)) for second in clr] for first in clr]
    condition_indices = {condition: index for index, condition in enumerate(spec["contrast"])}
    labels = [condition_indices[sample["condition"]] for sample in samples]
    total = math.fsum(squared[i][j] for i in range(len(samples)) for j in range(i + 1, len(samples))) / len(samples)
    observed = _pseudo_f(squared, labels, total)
    blocks = {}
    for i, sample in enumerate(samples):
        blocks.setdefault(tuple(sample[key] for key in spec["permutation_strata"]), []).append(i)
    _require(any(len({labels[i] for i in block}) > 1 for block in blocks.values()),
             "permutation-space", "joint frozen strata permit no condition exchanges")
    rng, exceeding, successful = random.Random(spec["seed"]), 0, 0
    for _ in range(spec["permutations"]):
        permuted = labels.copy()
        for block in blocks.values():
            shuffled = [labels[i] for i in block]
            rng.shuffle(shuffled)
            for i, label in zip(block, shuffled):
                permuted[i] = label
        try:
            value = _pseudo_f(squared, permuted, total)
        except ValueError as error:
            if not str(error).startswith("degenerate-permutation:"):
                raise
            continue
        successful += 1
        exceeding += value >= observed - 1e-12 * max(1.0, abs(observed))
    _require(successful == spec["permutations"], "permutation-degenerate",
             f"only {successful} of {spec['permutations']} frozen draws had nonzero within-group variation")
    columns = {j: k for k, j in enumerate(keep)}
    group_indices = [[i for i, label in enumerate(labels) if label == group] for group in (0, 1)]
    differential, tested = [], []
    for j, taxon in enumerate(taxa):
        row = {"taxon_id": taxon, "prevalence": prevalence[j]}
        if j in contaminants or j not in columns:
            row.update(status="untested-control" if j in contaminants else "untested-prevalence",
                       clr_difference=None, t=None, df=None, p_value=None, q_value=None, significant=False)
        else:
            k = columns[j]
            row.update(status="tested", **welch_test(*[[clr[i][k] for i in indices] for indices in group_indices],
                                                    minimum=spec["minimum_group_size"]))
            tested.append(row)
        differential.append(row)
    for row, adjusted in zip(tested, benjamini_hochberg([row["p_value"] for row in tested])):
        row.update(q_value=adjusted, significant=adjusted <= spec["fdr_alpha"])
    return {"qc": qc, "sample_ids": [sample["sample_id"] for sample in samples],
            "filtered_taxa": [taxa[j] for j in keep], "control_taxa": [taxa[j] for j in sorted(contaminants)],
            "low_depth_samples": [row["sample_id"] for row in qc if row["reason"] == "low-depth"],
            "clr": clr, "alpha_diversity": alpha, "aitchison_distance": [[math.sqrt(d) for d in row] for row in squared],
            "permanova": {"pseudo_f": observed, "p_value": (1 + exceeding) / (1 + spec["permutations"]),
                          "permutations": spec["permutations"], "successful_permutations": successful,
                          "seed": spec["seed"], "strata": spec["permutation_strata"]},
            "per_taxon": differential, "correction": "benjamini-hochberg", "fdr_alpha": spec["fdr_alpha"]}


def _claims(bundle, pack, computation):
    claims = _items(pack["claims"], "claims", MAX_CLAIMS, True)
    ids = []
    own = [pack[key] for key in ("design", "table", "report")] + pack["study_outputs"]
    own_paths = {identity["path"] for identity in own} | {bundle.entry}
    own_hashes = {identity["sha256"] for identity in own} | {bundle.cache[bundle.entry][1]}
    by_taxon = {row["taxon_id"]: row for row in computation["per_taxon"]}
    for claim in claims:
        _fields(claim, "id kind text status taxon_id support", "claim")
        ids.append(_text(claim["id"], "claim ID"))
        status, kind, text, taxon = (_text(claim[key], key) for key in ("status", "kind", "text", "taxon_id"))
        _require(status in STATUSES, "claim-boundary", "unknown claim status")
        _require(ABSOLUTE.search(text) is None, "relative-only", "relative composition is never absolute abundance or load")
        _require(ABSENCE.search(text) is None, "zero-not-absence", "zero counts never prove absence")
        _require(kind in ("descriptive", "associational") and OVERREACH.search(text) is None,
                 "claim-boundary", "statistical composition evidence only; causal, therapeutic and clinical wording refused")
        _require(status != "unavailable" or ASSERTION.search(text) is None,
                 "claim-boundary", "unavailable claims cannot assert positive evidence")
        support = _items(claim["support"], "claim support", MAX_RECORDS, True)
        _require(bool(support) or status == "unavailable", "unavailable-evidence", "absent records are unavailable, never negative evidence")
        for identity in support:
            evidence = bundle.load(identity)
            _record(evidence, "microbiome-evidence-v1", "kind result origin taxon_id")
            record_kind, result, origin = (_text(evidence[key], key) for key in ("kind", "result", "origin"))
            _text(evidence["taxon_id"], "evidence taxon")
            _require(origin in ("study", "external", "independent", "preregistered"), "invalid-record", "unknown evidence origin")
            if origin != "study":
                _require(identity["path"] not in own_paths and identity["sha256"] not in own_hashes,
                         "dependent-evidence", "asserted external evidence aliases this study")
            _require("unavailable" not in (record_kind, result) or status == "unavailable",
                     "unavailable-evidence", "any unavailable cited record requires unavailable status")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(record_kind + " " + result) is None
                         and record_kind == "statistical-composition-evidence"
                         and result == ("community-association" if taxon == "community" else "taxon-association")
                         and evidence["taxon_id"] == taxon,
                         "claim-evidence", "review approval and computed agreement cannot support positive claims")
        if status in POSITIVE:
            row = by_taxon.get(taxon)
            _require(row is None or row["status"] != "untested-control", "negative-control-hit", "negative-control taxa cannot be findings")
            _require((taxon == "community" and computation["permanova"]["p_value"] <= computation["fdr_alpha"])
                     or (row is not None and row["status"] == "tested" and row["significant"]),
                     "claim-evidence", "positive claims require the frozen permutation or full-family BH threshold")
            _require(status != "replicated", "claim-boundary", "one synthetic study cannot establish replication")
            _require(not pack["exploratory"] or status == "suggestive", "claim-boundary", "changed designs remain exploratory and suggestive")
    _names(ids, "claim IDs", MAX_CLAIMS, True)


def _same(actual, expected, label):
    if type(expected) is dict:
        _fields(actual, " ".join(expected), label)
        for key, value in expected.items():
            _same(actual[key], value, label + "." + key)
    elif type(expected) is list:
        _require(type(actual) is list and len(actual) == len(expected), "output-mismatch", label + " length differs")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _same(left, right, f"{label}[{index}]")
    elif type(expected) is float:
        _number(actual, label, -MAX_NUMBER)
        _require(math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-12), "output-mismatch", label + " differs")
    else:
        _require(type(actual) is type(expected) and actual == expected, "output-mismatch", label + " differs")


def validate_microbiome_composition_pack(path):
    """Validate one immutable pack JSON and its hash-bound inputs without writing files."""
    try:
        with _Bundle(path) as bundle:
            pack, _ = bundle.snapshot(bundle.entry)
            _record(pack, "microbiome-pack-v1", "stages design table report applied_specification exploratory claims study_outputs")
            _require(_names(pack["stages"], "stage IDs", 5) == list(STAGES), "stage-order", "five ordered stages required")
            _boolean(pack["exploratory"], "exploratory")
            design = bundle.load(pack["design"])
            _record(design, "microbiome-design-v1", "frozen_before_counts specification")
            _require(_boolean(design["frozen_before_counts"], "frozen_before_counts"),
                     "design-freeze", "design must be hashed before the count table is read")
            frozen = _specification(design["specification"])
            applied = pack["applied_specification"]
            _require(type(applied) is dict, "invalid-record", "applied specification must be an object")
            _require(applied == frozen or pack["exploratory"], "post-hoc-design", "changed pseudocount, filter or distance requires exploratory label")
            spec = _specification(applied)
            _require(all(spec[key] == frozen[key] for key in spec if key not in ("pseudocount", "prevalence_filter")),
                     "post-hoc-design", "only labelled pseudocount or prevalence sensitivity is supported")
            for key in ("table", "report"):
                _identity(pack[key])
            table = bundle.load(pack["table"])
            computation = reference_computation(spec, table)
            outputs = _items(pack["study_outputs"], "study outputs", MAX_RECORDS, True)
            for identity in outputs:
                bundle.load(identity)
            _claims(bundle, pack, computation)
            report = bundle.load(pack["report"])
            _record(report, "microbiome-report-v1", "design_sha256 exploratory interpretation computation")
            _require(report["design_sha256"] == pack["design"]["sha256"], "design-freeze", "report must retain frozen design identity")
            _require(_boolean(report["exploratory"], "report exploratory") == pack["exploratory"],
                     "post-hoc-design", "exploratory label must reach the report")
            _require(report["interpretation"] == "statistical composition evidence only", "claim-boundary", "bounded interpretation required")
            reported = report["computation"]
            _require(type(reported) is dict, "invalid-record", "report computation must be an object")
            reported_qc = _items(reported.get("qc"), "reported QC", MAX_SAMPLES)
            retained = set()
            for row in reported_qc:
                _fields(row, "sample_id depth retained reason", "reported sample QC")
                _text(row["sample_id"], "reported sample ID")
                _number(row["depth"], "reported depth", 0, MAX_COUNT * MAX_TAXA, True)
                if _boolean(row["retained"], "reported retention"):
                    retained.add(row["sample_id"])
            _require(not retained.intersection(computation["low_depth_samples"]), "low-depth-retained", "samples below frozen depth cannot be retained")
            permutation = reported.get("permanova")
            _require(type(permutation) is dict, "permutation-contract", "frozen seeded permutation record required")
            for key in ("seed", "permutations", "successful_permutations"):
                _number(permutation.get(key), "reported " + key, 0, MAX_NUMBER, True)
            _require(permutation["seed"] == frozen["seed"] and permutation["permutations"] == frozen["permutations"]
                     and permutation["successful_permutations"] == frozen["permutations"]
                     and permutation.get("strata") == frozen["permutation_strata"],
                     "permutation-contract", "frozen seed, count and within-strata permutations required")
            rows = _items(reported.get("per_taxon"), "reported taxa", MAX_TAXA)
            _require(reported.get("correction") == "benjamini-hochberg"
                     and all(type(row) is dict and "q_value" in row for row in rows),
                     "fdr-required", "per-taxon p-values require full-family Benjamini-Hochberg correction")
            _same(reported, computation, "computation")
            bundle.recheck()
            return {"schema": "microbiome-result-v1", "schema_version": 1, "fixture": "synthetic fixture",
                    "status": "accepted", "interpretation": "statistical composition evidence only",
                    "review": "unavailable", "exploratory": pack["exploratory"], "stages": list(STAGES),
                    "inputs": [{"path": name, "sha256": digest} for name, (_, digest, _) in bundle.cache.items()],
                    "computation": computation}
    except (OSError, UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("input-file: unavailable, changed or invalid bounded input") from error
