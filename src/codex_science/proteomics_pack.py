"""Read-only, offline synthetic protein-intensity reference; statistical evidence only."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics

from codex_science.bulk_expression_pack import welch_test as _welch


STAGES = ("01-design", "02-qc", "03-normalization", "04-testing", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_DEPTH = 64
MAX_TEXT = 8192
MAX_ITEMS = 20000
MAX_SAMPLES = 256
MAX_PROTEINS = 10000
MAX_VALUES = 1000000
MAX_CLAIMS = 1000
MAX_RECORDS = 1000
MAX_NUMBER = 1e100
IDENTITIES = ("organism", "database_name", "database_version")
POSITIVE = {"supported", "replicated", "suggestive"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|truth|physical[\s-]+validity)\b", re.I,
)
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|physical|clinic|truth", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _obj(value, label, fields=None):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    if fields is not None:
        _require(set(value) == set(fields), "invalid-record", f"{label} has missing or unknown fields")
    return value


def _items(value, label, limit=MAX_ITEMS, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds limit {limit}")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip()),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _names(value, label, limit=MAX_ITEMS, empty=False):
    values = _items(value, label, limit, empty)
    for item in values:
        _text(item, label)
    _require(len(set(values)) == len(values), "invalid-record", f"duplicate {label}")
    return values


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value) and low <= value <= high,
             "invalid-record", f"{label} must be finite in [{low}, {high}] with the declared numeric type")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many object fields")
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _int(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer", -MAX_NUMBER)


def _float(value):
    return _number(float(value), "JSON number", -MAX_NUMBER)


def _json_nodes(raw, limit):
    """Count value tokens without allocating a parsed tree; _json validates syntax."""
    start = re.compile(rb'[^ \t\r\n,:}\]]')
    string_end = re.compile(rb'["\\]')
    space = re.compile(rb'[ \t\r\n]*')
    primitive = re.compile(rb'[^ \t\r\n,:{}\[\]"]+')
    position = nodes = 0
    while match := start.search(raw, position):
        position = match.end()
        char = raw[match.start()]
        if char == ord('"'):
            while True:
                end = string_end.search(raw, position)
                _require(end is not None, "invalid-json", "unterminated JSON string")
                position = end.end()
                if raw[end.start()] == ord('"'):
                    break
                position += 1
            position = space.match(raw, position).end()
            if raw[position:position + 1] == b':':
                continue
        elif char not in b'{[':
            position = primitive.match(raw, match.start()).end()
        nodes += 1
        _require(nodes <= limit, "input-limit", "total JSON node budget exceeded")
    return nodes


def _json(raw):
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_int=_int, parse_float=_float, parse_constant=_constant), "JSON root")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            if type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON text exceeds MAX_TEXT")
            elif type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "input-limit", "JSON nesting exceeds MAX_DEPTH")
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds MAX_ITEMS")
                if type(value) is dict:
                    for key in value:
                        _require(len(key) <= MAX_TEXT, "input-limit", "JSON key exceeds MAX_TEXT")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children)
        return root
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def specification_hash(value):
    """Canonical content identity, never proof of historical freezing."""
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False, ensure_ascii=False).encode()
        return hashlib.sha256(raw).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid-record: specification must be finite JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and not re.match(r"^[A-Za-z]:", value)
             and all(ord(char) >= 32 for char in value), "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    """Pin each ancestor without following links, including a swap at open time."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                os.close(child)
                raise ValueError("input-root: root ancestor changed during open")
            os.close(descriptor)
            descriptor = child
        resolved = root.resolve(strict=True)
        current = os.stat(resolved, follow_symlinks=False)
        opened = os.fstat(descriptor)
        _require(resolved == root and (opened.st_dev, opened.st_ino) == (current.st_dev, current.st_ino),
                 "input-root", "root changed or resolved through a symlink")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        self.root = absolute.parent
        self.entry = absolute.name
        self.cache = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.nodes_read = 0
        self.descriptor = _open_root(self.root)
        opened = os.fstat(self.descriptor)
        self.root_identity = (opened.st_dev, opened.st_ino)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.descriptor)

    def read(self, path, *, checked=None):
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        directory = os.dup(self.descriptor)
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "symlinked artifact component")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                    os.close(child)
                    raise ValueError("input-file: artifact ancestor changed")
                os.close(directory)
                directory = child
            before = os.lstat(path.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "input must be a regular file at most 64 MiB")
            descriptor = os.open(path.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                opened = os.fstat(handle.fileno())
                _require(stat.S_ISREG(opened.st_mode) and opened.st_size <= MAX_BYTES
                         and _signature(before) == _signature(opened), "input-file", "input changed during open")
                signature = _signature(opened)
                identity = signature[:2]
                cached = self.artifacts.get(identity)
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached input modified during validation")
                    if checked is None or identity in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "total input byte budget exceeded")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and _signature(opened) == _signature(after),
                     "input-file", "input grew or changed during read")
            if checked is None:
                self.bytes_read += len(raw)
            return raw, _signature(after)
        finally:
            os.close(directory)

    def load(self, identity, schema=None):
        _obj(identity, "artifact identity", ("path", "sha256"))
        path = _relative(identity["path"])
        expected = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", expected) is not None, "input-hash", "invalid SHA-256")
        value, digest = self.snapshot(path)
        _require(expected == digest, "input-hash", "artifact hash mismatch")
        if schema is not None:
            _require(value.get("schema") == schema and value.get("fixture") is True,
                     "invalid-record", f"expected synthetic fixture {schema}")
        return value

    def snapshot(self, path):
        name = path.as_posix()
        if name not in self.cache:
            _require(len(self.cache) < MAX_RECORDS, "input-limit", "too many input artifacts")
            raw, signature = self.read(path)
            identity = signature[:2]
            if raw is not None:
                nodes = _json_nodes(raw, MAX_TOTAL_NODES - self.nodes_read)
                self.artifacts[identity] = (_json(raw), hashlib.sha256(raw).hexdigest(), signature)
                self.nodes_read += nodes
            self.cache[name] = self.artifacts[identity]
        value, digest, _ = self.cache[name]
        return value, digest

    def recheck(self):
        descriptor = _open_root(self.root)
        try:
            current = os.fstat(descriptor)
            _require((current.st_dev, current.st_ino) == self.root_identity,
                     "input-changed", "bundle root replaced during validation")
        finally:
            os.close(descriptor)
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self.read(_relative(name), checked=checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced or modified during validation")
            checked.add(current[:2])
        descriptor = _open_root(self.root)
        try:
            current = os.fstat(descriptor)
            _require((current.st_dev, current.st_ino) == self.root_identity,
                     "input-changed", "bundle root replaced during recheck")
        finally:
            os.close(descriptor)


def _spec(value):
    _obj(value, "specification", ("contrast", "replicate_unit", "normalization", "missing_rule", "alpha",
                                "minimum_peptides", "minimum_observed_per_group", "correction", "correction_scope", "qc"))
    contrast = _names(value["contrast"], "contrast", 2)
    _require(len(contrast) == 2, "invalid-record", "exactly two ordered conditions required")
    _require(value["replicate_unit"] == "biological_sample", "technical-replicates", "technical replicates are not biological units")
    _require(value["normalization"] in ("median-log2", "none"), "invalid-record", "unsupported normalization")
    _require(value["correction"] == "BH" and value["correction_scope"] == "all-tested-proteins",
             "bh-required", "BH across every tested protein is mandatory")
    _number(value["alpha"], "FDR alpha", 0, 1)
    _number(value["minimum_peptides"], "minimum peptides", 1, MAX_ITEMS, True)
    _number(value["minimum_observed_per_group"], "minimum observed", 2, MAX_SAMPLES, True)
    rule = _obj(value["missing_rule"], "missing rule")
    method = _text(rule.get("method"), "missing method")
    _require(method in ("keep-missing", "constant-log2"), "missing-rule", "missing abundance cannot be filled with zero")
    _obj(rule, "missing rule", ("method",) if method == "keep-missing" else ("method", "value"))
    if method == "constant-log2":
        _number(rule["value"], "imputation log2 value", -1000, 1000)
    qc = _obj(value["qc"], "QC", ("max_missing_rate", "max_log2_total_deviation"))
    _number(qc["max_missing_rate"], "missing rate", 0, 1)
    _number(qc["max_log2_total_deviation"], "total deviation", 0, 1000)
    return value


def welch_test(first, second, minimum=2):
    """Two-sided Welch on observed log2 intensities; degenerate groups are refused."""
    _number(minimum, "minimum observed", 2, MAX_SAMPLES, True)
    for group in (first, second):
        _items(group, "Welch group", MAX_SAMPLES)
        _require(len(group) >= minimum, "untestable-replicates", "too few observed biological replicates")
        for value in group:
            _number(value, "log2 intensity", -1000, 1000)
        _require(statistics.variance(group) > 0, "untestable-variance", "zero within-group variance")
    # A common scale leaves t and df unchanged and avoids squaring subnormal variances.
    scale = max(abs(value) for group in (first, second) for value in group)
    result = _welch([value / scale for value in first], [value / scale for value in second])
    result["log2_fold_change"] = math.fsum(second) / len(second) - math.fsum(first) / len(first)
    return result


def benjamini_hochberg(values):
    """Adjust the complete tested family; preserve its input order."""
    _items(values, "BH family", MAX_PROTEINS, True)
    for value in values:
        _number(value, "p value", 0, 1)
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [1.0] * len(values)
    running = 1.0
    for rank in range(len(values), 0, -1):
        index = order[rank - 1]
        running = min(running, values[index] * (len(values) / rank))
        result[index] = running
    return result


def _claims(bundle, pack, differential):
    claims = _items(pack["claims"], "claims", MAX_CLAIMS, True)
    _names([_obj(claim, "claim").get("id") for claim in claims], "claim IDs", MAX_CLAIMS, True)
    by_protein = {row["protein_id"]: row for row in differential}
    study = list(pack["inputs"].values()) + pack["study_outputs"]
    study_paths = {identity["path"] for identity in study}
    study_hashes = {identity["sha256"] for identity in study}
    for claim in claims:
        _obj(claim, "claim", ("id", "kind", "text", "status", "support", "protein_id"))
        text = _text(claim["text"], "claim text")
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        protein = _text(claim["protein_id"], "claim protein")
        _require(status in POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"},
                 "claim-boundary", "unknown claim status")
        _require(kind in ("descriptive", "associational") and OVERREACH.search(text) is None,
                 "claim-boundary", "claims must state statistical evidence only")
        _require(status != "unavailable" or UNAVAILABLE_POSITIVE.search(text) is None,
                 "claim-boundary", "unavailable claim cannot assert positive evidence")
        support = _items(claim["support"], "claim support", MAX_RECORDS, True)
        _require(bool(support) or status == "unavailable", "unavailable-evidence", "absent records are unavailable, never negative evidence")
        for identity in support:
            evidence = bundle.load(identity, "proteomics-evidence-v1")
            _obj(evidence, "evidence", ("schema", "fixture", "kind", "result", "origin", "protein_id"))
            record_kind = _text(evidence["kind"], "evidence kind")
            record_result = _text(evidence["result"], "evidence result")
            origin = _text(evidence["origin"], "evidence origin")
            _text(evidence["protein_id"], "evidence protein")
            _require(origin in ("study", "external", "independent", "preregistered"), "invalid-record", "unknown evidence origin")
            if origin != "study":
                _require(identity["path"] not in study_paths and identity["sha256"] not in study_hashes,
                         "dependent-evidence", "asserted external evidence aliases study input or output")
            _require("unavailable" not in (record_kind, record_result) or status == "unavailable",
                     "unavailable-evidence", "unavailable records cannot support positive or negative evidence")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(record_kind + " " + record_result) is None
                         and record_kind == "statistical-evidence" and record_result == "protein-level-association"
                         and evidence["protein_id"] == protein,
                         "claim-evidence", "review approval or computed agreement is not association evidence")
        if status in POSITIVE:
            row = by_protein.get(protein)
            _require(row is not None, "claim-evidence", "unknown claim protein")
            _require(not row["decoy"] and not row["contaminant"], "excluded-hit", "decoys and contaminants cannot be hits")
            _require(row["peptides"] >= pack["analysis_spec"]["minimum_peptides"], "peptide-hit", "too few peptides for a hit")
            _require(row["status"] == "tested", "untestable-hit", "untestable protein cannot be significant")
            _require(row["significant"], "claim-evidence", "positive association requires the full-family BH threshold")
            _require(status != "replicated", "claim-boundary", "one synthetic study cannot establish replication")
            _require(not pack["exploratory"] or status == "suggestive", "claim-boundary", "exploratory evidence remains suggestive")


def _analyze(bundle):
    pack, _ = bundle.snapshot(_relative(bundle.entry))
    _obj(pack, "pack", ("schema", "fixture", "stages", "inputs", "frozen_spec", "analysis_spec", "frozen_sha256",
                         "frozen_design_sha256", "freeze_before_intensities", "exploratory", "study_outputs", "claims"))
    _require(pack["schema"] == "proteomics-pack-v1" and pack["fixture"] is True, "invalid-record", "synthetic proteomics pack required")
    _require(pack["stages"] == list(STAGES), "stage-order", "five ordered stage IDs required")
    inputs = _obj(pack["inputs"], "inputs", ("design", "intensities"))
    frozen = _spec(pack["frozen_spec"])
    spec = _spec(pack["analysis_spec"])
    _require(pack["freeze_before_intensities"] is True and pack["frozen_sha256"] == specification_hash(frozen),
             "design-freeze", "specification must be hashed before intensity admission")
    _boolean(pack["exploratory"], "exploratory")
    _require(frozen == spec or pack["exploratory"], "post-hoc-change", "changed normalization, contrast or controls require exploration")
    _require(spec["missing_rule"]["method"] != "constant-log2" or frozen["missing_rule"]["method"] == "constant-log2",
             "undeclared-imputation", "exploration cannot introduce imputation absent from the frozen rule")
    design = bundle.load(inputs["design"], "proteomics-design-v1")
    _require(pack["frozen_design_sha256"] == inputs["design"]["sha256"], "design-freeze", "design identity must be frozen")
    _obj(design, "design", ("schema", "fixture", *IDENTITIES, "samples"))
    for field in IDENTITIES:
        _text(design[field], field)
    samples = _items(design["samples"], "samples", MAX_SAMPLES)
    _names([_obj(sample, "sample").get("id") for sample in samples], "sample IDs", MAX_SAMPLES)
    units = []
    for sample in samples:
        _obj(sample, "sample", ("id", "biological_unit", "replicate_type", "condition", "batch", *IDENTITIES))
        for field in ("biological_unit", "condition", "batch", "replicate_type", *IDENTITIES):
            _text(sample[field], field)
        _require(sample["replicate_type"] == "biological", "technical-replicates", "technical runs cannot increase biological n")
        _require(all(sample[field] == design[field] for field in IDENTITIES), "database-identity", "organism or database version differs between samples")
        units.append(sample["biological_unit"])
    _require(len(set(units)) == len(units), "technical-replicates", "repeated biological units are pseudoreplicates")
    contrast = spec["contrast"]
    _require({sample["condition"] for sample in samples} == set(contrast), "invalid-record", "conditions must match contrast")
    groups = [[i for i, sample in enumerate(samples) if sample["condition"] == condition] for condition in contrast]
    _require(all(len(group) >= spec["minimum_observed_per_group"] for group in groups),
             "insufficient-replicates", "too few biological samples per condition")
    batches = [{samples[i]["batch"] for i in group} for group in groups]
    _require(bool(batches[0] & batches[1]), "batch-confounding", "batch perfectly confounded with condition")
    table = bundle.load(inputs["intensities"], "proteomics-intensities-v1")
    _obj(table, "intensities", ("schema", "fixture", *IDENTITIES, "sample_ids", "proteins", "seed"))
    _number(table["seed"], "seed", -MAX_NUMBER, MAX_NUMBER, True)
    _require(all(table[field] == design[field] for field in IDENTITIES), "database-identity", "table organism or database differs")
    sample_ids = _names(table["sample_ids"], "table sample IDs", MAX_SAMPLES)
    _require(sample_ids == [sample["id"] for sample in samples], "sample-identity", "sample order differs from frozen design")
    proteins = _items(table["proteins"], "proteins", MAX_PROTEINS)
    _require(len(samples) * len(proteins) <= MAX_VALUES, "input-limit", "intensity matrix exceeds MAX_VALUES")
    _names([_obj(row, "protein").get("id") for row in proteins], "protein IDs", MAX_PROTEINS)
    observed_columns = [[] for _ in samples]
    log_rows = []
    masks = []
    for row in proteins:
        _obj(row, "protein", ("id", "peptides", "decoy", "contaminant", "values", "imputed"))
        _number(row["peptides"], "peptides", 0, MAX_ITEMS, True)
        _boolean(row["decoy"], "decoy")
        _boolean(row["contaminant"], "contaminant")
        values = _items(row["values"], "intensities", MAX_SAMPLES)
        flags = _items(row["imputed"], "imputation flags", MAX_SAMPLES)
        _require(len(values) == len(flags) == len(samples), "sample-identity", "intensity dimensions differ")
        logs, mask = [], []
        for i, (value, flag) in enumerate(zip(values, flags)):
            _boolean(flag, "imputed")
            _require(not flag or (spec["missing_rule"]["method"] == "constant-log2"
                     and frozen["missing_rule"]["method"] == "constant-log2"),
                     "undeclared-imputation", "imputation must be declared in the frozen rule")
            if value is not None:
                _number(value, "intensity", 0, MAX_NUMBER)
                _require(value > 0, "zero-abundance", "missing values cannot become zero abundance")
            _require(not flag or value is not None, "invalid-record", "imputed input must have a value")
            observed = value is not None and not flag
            logs.append(math.log2(value) if observed else None)
            mask.append(observed)
            if observed and not row["decoy"] and not row["contaminant"]:
                observed_columns[i].append(value)
        log_rows.append(logs)
        masks.append(mask)
    qc, centers = [], []
    eligible = sum(not row["decoy"] and not row["contaminant"] for row in proteins)
    _require(eligible > 0 and all(observed_columns), "qc-failed", "empty observed protein intensities")
    totals = [math.fsum(column) for column in observed_columns]
    total_center = statistics.median([math.log2(total) for total in totals])
    for i, column in enumerate(observed_columns):
        centers.append(statistics.median([math.log2(value) for value in column]))
        missing_rate = 1 - len(column) / eligible
        deviation = abs(math.log2(totals[i]) - total_center)
        failures = []
        if missing_rate > spec["qc"]["max_missing_rate"]:
            failures.append("missing-rate")
        if deviation > spec["qc"]["max_log2_total_deviation"]:
            failures.append("total-intensity-outlier")
        qc.append({"sample_id": samples[i]["id"], "total_intensity": totals[i], "missing_rate": missing_rate,
                   "log2_total_deviation": deviation, "failures": failures})
    reference = statistics.median(centers)
    offsets = [center - reference if spec["normalization"] == "median-log2" else 0.0 for center in centers]
    normalized, differential = [], []
    qc_failed = any(item["failures"] for item in qc)
    for row, logs, mask in zip(proteins, log_rows, masks):
        adjusted = [value - offsets[i] if value is not None else None for i, value in enumerate(logs)]
        flags = [not observed and spec["missing_rule"]["method"] == "constant-log2" for observed in mask]
        displayed = [spec["missing_rule"]["value"] if flag else value for value, flag in zip(adjusted, flags)]
        normalized.append({"protein_id": row["id"], "log2_intensities": displayed, "observed": mask, "imputed": flags})
        group_values = [[adjusted[i] for i in group if mask[i]] for group in groups]
        reasons = []
        if row["decoy"] or row["contaminant"]:
            reasons.append("decoy-or-contaminant")
        if row["peptides"] < spec["minimum_peptides"]:
            reasons.append("minimum-peptides")
        if any(len(group) < spec["minimum_observed_per_group"] for group in group_values):
            reasons.append("minimum-observed")
        if any(len(group) >= 2 and statistics.variance(group) == 0 for group in group_values):
            reasons.append("zero-variance")
        if qc_failed:
            reasons.append("sample-qc")
        result = {"protein_id": row["id"], "peptides": row["peptides"], "decoy": row["decoy"],
                  "contaminant": row["contaminant"], "observed": [len(group) for group in group_values],
                  "status": "untestable" if reasons else "tested", "reasons": reasons,
                  "log2_fold_change": None, "t": None, "df": None, "p_value": None, "q_value": None, "significant": None}
        if not reasons:
            result.update(welch_test(*group_values, minimum=spec["minimum_observed_per_group"]))
        differential.append(result)
    tested = [row for row in differential if row["status"] == "tested"]
    for row, q_value in zip(tested, benjamini_hochberg([row["p_value"] for row in tested])):
        row.update(q_value=q_value, significant=q_value <= spec["alpha"])
    outputs = _items(pack["study_outputs"], "study outputs", MAX_RECORDS, True)
    for identity in outputs:
        bundle.load(identity)
    _claims(bundle, pack, differential)
    bundle.recheck()
    return {"schema": "proteomics-result-v1", "fixture": True, "stages": list(STAGES),
            "evidence_level": "statistical-only", "review": "unavailable", "exploratory": pack["exploratory"],
            "frozen_sha256": pack["frozen_sha256"], "specification_sha256": specification_hash(spec),
            "input_identities": [{"path": name, "sha256": digest} for name, (_, digest, _) in bundle.cache.items()],
            "qc": qc, "normalization_offsets": offsets, "normalized": normalized, "differential": differential,
            "claims": pack["claims"], "limitations": [
                "Synthetic software fixture; no biological, physical or clinical validity.",
                "Independent unpaired Welch on observed log2 intensities; no batch or covariate adjustment.",
                "Median normalization assumes most eligible proteins do not shift; inspect missingness and batch sensitivity.",
                "Declared imputation is displayed and flagged, never counted as observed or used for Welch testing.",
                "Hashes bind content, not historical timing or actual source independence.",
                "Failed QC, exclusions and null results are preserved; unavailable records are never negative evidence.",
                "Rigor classification and independent science-review remain coordinator responsibilities."]}


def validate_proteomics_pack(path: Path | str) -> dict:
    """Validate a bundle and return unreviewed reference JSON without writing files."""
    _require(isinstance(path, (str, Path)), "input-path", "bundle must be a local text path")
    name = os.fspath(path)
    _require(0 < len(name) <= MAX_TEXT and all(ord(char) >= 32 for char in name),
             "input-path", "bundle path must be bounded text without control characters")
    try:
        with _Bundle(path) as bundle:
            return _analyze(bundle)
    except (OSError, RuntimeError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError(f"input-file: unavailable or changed bounded input ({type(error).__name__})") from error
