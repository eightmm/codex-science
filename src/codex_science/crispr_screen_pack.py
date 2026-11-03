"""Read-only arithmetic checks for offline synthetic pooled CRISPR count fixtures."""
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


STAGES = ("01-freeze", "02-count-qc", "03-guide-changes", "04-gene-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
MAX_ARTIFACTS = 128
MAX_DEPTH = 32
MAX_TEXT = 4096
MAX_ITEMS = 20000
MAX_GUIDES = 10000
MAX_GENES = 2000
MAX_SAMPLES = 64
MAX_VALUES = 200000
MAX_DRAWS = 2000
MAX_DRAW_WORK = 2000000
MAX_CLAIMS = 100
MAX_SUPPORT = 100
MAX_NUMBER = 1e100
MAX_COUNT = 10**12
POSITIVE = {"supported", "replicated", "suggestive"}
WORDING_FAMILIES = (
    "caus", "mechanis", "therap", "clinic", "efficac", "effective", "treat", "cure",
    "prevent", "recommend", "prescri", "bind", "affinit", "inhibit", "activat",
    "regulat", "driv", "induc",
)
OVERREACH = re.compile(
    r"\b(?:" + "|".join(word + r"\w*" for word in WORDING_FAMILIES)
    + r"|essential\w*|drug[\s-]+target\w*|physical[\s-]+validity|biological[\s-]+validity|truth)\b", re.I,
)
UNAVAILABLE_POSITIVE = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|physical|clinic|truth", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _obj(value, label, fields=None):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    if fields is not None:
        _require(len(value) == len(fields) and set(value) == set(fields),
                 "invalid-record", f"{label} has missing or unknown fields")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds {limit}")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip()),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value) and low <= value <= high,
             "invalid-record", f"{label} must have its declared numeric type and finite range [{low}, {high}]")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")


def _record(value, schema, fields):
    _obj(value, schema, ("schema", "schema_version", "fixture", *fields))
    _number(value["schema_version"], "schema version", 1, 1, True)
    _require(value["schema"] == schema and value["fixture"] is True,
             "invalid-record", f"expected synthetic fixture {schema}")
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


def _integer(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    return _number(int(value), "JSON integer", -MAX_NUMBER)


def _json(raw, allowance):
    # This conservative bound counts punctuation inside strings as well.
    nodes = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = _obj(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_int=_integer,
                              parse_float=lambda value: _number(float(value), "JSON number", -MAX_NUMBER),
                              parse_constant=_constant), "JSON root")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            if type(value) is str:
                _require(len(value) <= MAX_TEXT, "input-limit", "JSON text exceeds MAX_TEXT")
            elif type(value) in (dict, list):
                _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting exceeds MAX_DEPTH")
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds MAX_ITEMS")
                if type(value) is dict:
                    for key in value:
                        _require(len(key) <= MAX_TEXT, "input-limit", "JSON key exceeds MAX_TEXT")
                children = value.values() if type(value) is dict else value
                pending.extend((child, depth + 1) for child in children)
        return root, nodes
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and path.as_posix() == value and value != "."
             and ".." not in path.parts and "\\" not in value and "\x00" not in value
             and not re.match(r"^[A-Za-z]:", value) and all(ord(char) >= 32 for char in value),
             "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_root(root):
    """Pin and remember EVERY ancestor, including directory swaps at open time."""
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_DIRECTORY
    descriptor = os.open(root.anchor, flags)
    chain = [_signature(os.fstat(descriptor))[:2]]
    try:
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "input-root", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            opened = os.fstat(child)
            if _signature(before)[:2] != _signature(opened)[:2]:
                os.close(child)
                raise ValueError("input-root: root ancestor changed during open")
            os.close(descriptor)
            descriptor = child
            chain.append(_signature(opened)[:2])
        return descriptor, chain
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        absolute = Path(os.path.abspath(path))
        self.root, self.entry = absolute.parent, absolute.name
        self.cache, self.artifacts = {}, {}
        self.bytes_read = self.nodes_read = 0
        self.descriptor, self.chain = _open_root(self.root)

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
                _require(stat.S_ISDIR(before.st_mode), "input-file", "artifact ancestors must be real directories")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened = os.fstat(child)
                if _signature(before)[:2] != _signature(opened)[:2]:
                    os.close(child)
                    raise ValueError("input-file: artifact ancestor changed during open")
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
                cached = self.artifacts.get(signature[:2])
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached artifact modified")
                    if checked is None or signature[:2] in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(opened.st_size <= limit, "input-limit", "bundle raw byte allowance exceeded")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == opened.st_size and _signature(opened) == _signature(after),
                     "input-file", "input grew or changed during read")
            if checked is None:
                self.bytes_read += len(raw)
            return raw, _signature(after)
        finally:
            os.close(directory)

    def snapshot(self, path):
        name = path.as_posix()
        if name not in self.cache:
            _require(len(self.cache) < MAX_ARTIFACTS, "input-limit", "too many artifacts")
            raw, signature = self.read(path)
            identity = signature[:2]
            if raw is not None:
                value, nodes = _json(raw, MAX_TOTAL_NODES - self.nodes_read)
                self.artifacts[identity] = (value, hashlib.sha256(raw).hexdigest(), signature)
                self.nodes_read += nodes
            self.cache[name] = self.artifacts[identity]
        return self.cache[name][:2]

    def load(self, identity):
        _obj(identity, "artifact identity", ("path", "sha256"))
        path = _relative(identity["path"])
        digest = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "input-hash", "invalid SHA-256")
        value, actual = self.snapshot(path)
        _require(actual == digest, "input-hash", "artifact hash mismatch")
        return value

    def recheck_root(self):
        descriptor, chain = _open_root(self.root)
        try:
            _require(chain == self.chain, "input-changed", "bundle root or ancestor replaced")
        finally:
            os.close(descriptor)

    def recheck(self):
        self.recheck_root()
        checked = set()
        for name, (_, digest, signature) in self.cache.items():
            raw, current = self.read(_relative(name), checked=checked)
            _require(current == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced or modified during validation")
            checked.add(current[:2])
        self.recheck_root()


def _rules(value):
    _record(value, "crispr-rules-v1", (
        "contrast", "minimum_total_reads", "minimum_detection_fraction", "normalization", "pseudocount",
        "aggregation", "minimum_guides", "minimum_controls", "minimum_replicates", "concordance_threshold",
        "fold_change_threshold", "alpha", "multiple_testing", "permutation_seed", "permutation_count"))
    contrast = _items(value["contrast"], "contrast", 2)
    for item in contrast:
        _text(item, "condition")
    _require(len(contrast) == 2 and contrast[0] != contrast[1], "invalid-record", "two distinct conditions required")
    for key, low, high in (("minimum_total_reads", 1, MAX_COUNT * MAX_GUIDES),
                           ("minimum_guides", 1, MAX_GUIDES), ("minimum_controls", 2, MAX_GUIDES),
                           ("minimum_replicates", 2, MAX_SAMPLES // 2),
                           ("permutation_seed", 0, 2**32 - 1), ("permutation_count", 1, MAX_DRAWS)):
        _number(value[key], key, low, high, True)
    _number(value["minimum_detection_fraction"], "detection fraction", 0, 1)
    _number(value["concordance_threshold"], "concordance threshold", -1, 1)
    _number(value["pseudocount"], "pseudocount", 1e-12, MAX_COUNT)
    _number(value["fold_change_threshold"], "fold change threshold", 1e-12, 100)
    _number(value["alpha"], "alpha", 1e-12, 1)
    _text(value["normalization"], "normalization")
    _require(value["normalization"] in ("total-count", "median-of-ratios"), "normalization-rule", "unsupported normalization")
    _require(value["aggregation"] == "median-guide-log2", "aggregation-rule", "only median guide log2 change is supported")
    _require(value["multiple_testing"] == "benjamini-hochberg", "multiple-testing", "full-family BH correction required")
    return value


def pearson(first, second, minimum=3):
    """Scale centered vectors to avoid zero-variance underflow on tiny finite values."""
    _number(minimum, "minimum pairs", 3, MAX_GUIDES, True)
    _items(first, "first vector", MAX_GUIDES)
    _items(second, "second vector", MAX_GUIDES)
    _require(len(first) == len(second) and len(first) >= minimum,
             "degenerate-concordance", "too few paired guides")
    vectors = []
    for values in (first, second):
        for value in values:
            _number(value, "fold change", -MAX_NUMBER)
        center = math.fsum(value / len(values) for value in values)
        centered = [value - center for value in values]
        scale = max(abs(value) for value in centered)
        _require(scale > 0, "degenerate-concordance", "zero variance in guide changes")
        vectors.append([value / scale for value in centered])
    a, b = vectors
    correlation = math.fsum(x * y for x, y in zip(a, b)) / math.sqrt(math.fsum(x*x for x in a) * math.fsum(y*y for y in b))
    return max(-1.0, min(1.0, correlation))


def benjamini_hochberg(values):
    _items(values, "p values", MAX_GENES, True)
    for value in values:
        _number(value, "p value", 0, 1)
    order = sorted(range(len(values)), key=values.__getitem__)
    result, running = [0.0] * len(values), 1.0
    for rank in range(len(order), 0, -1):
        index = order[rank - 1]
        running = min(running, values[index] * len(values) / rank)
        result[index] = running
    return result


def _tables(library, design, counts, rules):
    _record(library, "crispr-library-v1", ("guides",))
    guides = _items(library["guides"], "library guides", MAX_GUIDES)
    by_guide, genes, controls = {}, {}, []
    for guide in guides:
        _obj(guide, "guide", ("id", "gene", "non_targeting"))
        name = _text(guide["id"], "guide ID")
        _require(name not in by_guide, "duplicate-guide", "duplicate library guide ID")
        _boolean(guide["non_targeting"], "non-targeting flag")
        if guide["non_targeting"]:
            _require(guide["gene"] is None, "invalid-record", "control guide cannot map to a gene")
            controls.append(name)
        else:
            gene = _text(guide["gene"], "gene ID")
            if gene not in genes:
                _require(len(genes) < MAX_GENES, "input-limit", "too many genes")
                genes[gene] = []
            genes[gene].append(name)
        by_guide[name] = guide
    _require(len(controls) >= rules["minimum_controls"], "non-targeting-controls", "too few library controls")
    _require(bool(genes), "invalid-record", "library must include a gene")
    _record(design, "crispr-design-v1", ("samples",))
    samples = _items(design["samples"], "samples", MAX_SAMPLES)
    _require(len(samples) * len(guides) <= MAX_VALUES, "input-limit", "guide by sample matrix exceeds MAX_VALUES")
    sample_ids, groups, times = set(), {condition: {} for condition in rules["contrast"]}, {}
    for sample in samples:
        _obj(sample, "sample", ("id", "condition", "replicate", "timepoint"))
        name = _text(sample["id"], "sample ID")
        condition = _text(sample["condition"], "sample condition")
        replicate = _text(sample["replicate"], "replicate ID")
        _number(sample["timepoint"], "timepoint", 0, MAX_COUNT, True)
        _require(name not in sample_ids and condition in groups and replicate not in groups[condition],
                 "sample-design", "duplicate sample/replicate or unknown condition")
        _require(condition not in times or times[condition] == sample["timepoint"],
                 "sample-design", "condition timepoints must agree")
        times[condition] = sample["timepoint"]
        sample_ids.add(name)
        groups[condition][replicate] = len(sample_ids) - 1
    baseline, selected = (groups[condition] for condition in rules["contrast"])
    _require(set(baseline) == set(selected) and len(baseline) >= rules["minimum_replicates"],
             "sample-design", "matched replicates below the frozen minimum")
    _require(len(times) == 2 and times[rules["contrast"][0]] < times[rules["contrast"][1]],
             "sample-design", "contrast must progress between frozen timepoints")
    _record(counts, "crispr-counts-v1", ("sample_ids", "rows"))
    names = _items(counts["sample_ids"], "count sample IDs", MAX_SAMPLES)
    _require(names == [sample["id"] for sample in samples], "sample-design", "count columns differ from frozen design")
    rows = _items(counts["rows"], "count rows", MAX_GUIDES)
    by_count = {}
    for row in rows:
        _obj(row, "count row", ("guide_id", "counts"))
        name = _text(row["guide_id"], "count guide ID")
        _require(name not in by_count, "duplicate-guide", "duplicate count guide ID")
        _require(name in by_guide, "unknown-guide", "count guide missing from library")
        values = _items(row["counts"], "counts", MAX_SAMPLES)
        _require(len(values) == len(samples), "sample-design", "count row dimensions differ")
        for value in values:
            _require(type(value) is int and 0 <= value <= MAX_COUNT,
                     "invalid-count", "counts must be bounded non-negative integers")
        by_count[name] = values
    _require(all(name in by_count and all(value > 0 for value in by_count[name]) for name in controls),
             "non-targeting-controls", "controls must be present and detected in every sample")
    return guides, genes, controls, samples, baseline, selected, by_count


def reference_computation(rules, library, design, counts):
    """Compute synthetic QC and a two-condition summary, never essentiality or efficacy."""
    rules = _rules(rules)
    guides, genes, controls, samples, baseline, selected, table = _tables(library, design, counts, rules)
    width = len(samples)
    matrix = {guide["id"]: table.get(guide["id"], [0] * width) for guide in guides}
    columns = [list(column) for column in zip(*matrix.values())]
    totals = [sum(column) for column in columns]
    qc = []
    for sample, column, total in zip(samples, columns, totals):
        detection = sum(value > 0 for value in column) / len(guides)
        failures = []
        if total < rules["minimum_total_reads"]:
            failures.append("minimum-reads")
        if detection < rules["minimum_detection_fraction"]:
            failures.append("guide-detection")
        skew = (math.fsum((2*i - len(guides) - 1) * value for i, value in enumerate(sorted(column), 1))
                / (len(guides) * total)) if total else None
        qc.append({"sample_id": sample["id"], "total_reads": total, "detection_fraction": detection,
                   "zero_fraction": 1 - detection, "gini": skew, "failures": failures})
    failed_qc = any(item["failures"] for item in qc)
    factors, changes, concordance = [None] * width, [], []
    pooled = False
    if not failed_qc:
        if rules["normalization"] == "total-count":
            center = statistics.median(totals)
            factors = [total / center for total in totals]
        else:
            usable = [row for row in matrix.values() if all(row)]
            _require(bool(usable), "normalization-rule", "no all-positive rows for geometric means")
            means = [math.exp(math.fsum(math.log(value) for value in row) / width) for row in usable]
            factors = [statistics.median([row[i] / mean for row, mean in zip(usable, means)]) for i in range(width)]
        normalized = {name: [value / factor for value, factor in zip(row, factors)]
                      for name, row in matrix.items() if name in table}
        replicates = sorted(baseline)
        raw = {name: [math.log2((row[selected[rep]] + rules["pseudocount"]) /
                               (row[baseline[rep]] + rules["pseudocount"])) for rep in replicates]
               for name, row in normalized.items()}
        null_centers = [statistics.median([raw[name][i] for name in controls]) for i in range(len(replicates))]
        adjusted = {name: [value - null_centers[i] for i, value in enumerate(row)] for name, row in raw.items()}
        changes = [{"guide_id": name, "replicate_log2_changes": row, "log2_fold_change": statistics.median(row)}
                   for name, row in adjusted.items()]
        vectors = list(zip(*adjusted.values()))
        for i in range(len(replicates)):
            for j in range(i + 1, len(replicates)):
                correlation = pearson(list(vectors[i]), list(vectors[j]))
                concordance.append({"contrast": rules["contrast"], "replicates": [replicates[i], replicates[j]],
                                    "pearson": correlation, "passed": correlation >= rules["concordance_threshold"]})
        pooled = all(row["passed"] for row in concordance)
    by_change = {row["guide_id"]: row["log2_fold_change"] for row in changes}
    eligible = {gene: [name for name in names if name in table and all(table[name])] for gene, names in genes.items()}
    work = sum(len(names) for names in eligible.values()) * rules["permutation_count"]
    _require(work <= MAX_DRAW_WORK, "input-limit", "permutation work exceeds MAX_DRAW_WORK")
    null = [by_change[name] for name in controls] if pooled else []
    if pooled:
        _require(max(null) > min(null), "degenerate-null", "control null has zero variance")
    generator = random.Random(rules["permutation_seed"])
    summaries = []
    for gene, names in eligible.items():
        reasons = []
        if len(names) < rules["minimum_guides"]:
            reasons.append("minimum-guides")
        if failed_qc:
            reasons.append("sample-qc")
        elif not pooled:
            reasons.append("replicate-concordance")
        if len(names) > len(controls):
            reasons.append("insufficient-null")
        row = {"gene_id": gene, "guide_count": len(names), "status": "unavailable" if reasons else "observed",
               "reasons": reasons, "log2_fold_change": None, "p_value": None, "q_value": None, "significant": None}
        if not reasons:
            statistic = statistics.median([by_change[name] for name in names])
            exceed = 0
            for _ in range(rules["permutation_count"]):
                draw = statistics.median(generator.sample(null, len(names)))
                # A median-centered null can differ at roundoff for exact mathematical ties.
                exceed += abs(draw) >= abs(statistic) or math.isclose(abs(draw), abs(statistic), rel_tol=1e-12, abs_tol=1e-12)
            row.update(log2_fold_change=statistic, p_value=(1 + exceed) / (1 + rules["permutation_count"]))
        summaries.append(row)
    tested = [row for row in summaries if row["status"] == "observed"]
    for row, q in zip(tested, benjamini_hochberg([row["p_value"] for row in tested])):
        row.update(q_value=q, significant=q <= rules["alpha"] and abs(row["log2_fold_change"]) >= rules["fold_change_threshold"])
    return {"schema": "crispr-report-v1", "schema_version": 1, "fixture": True,
            "multiple_testing": "benjamini-hochberg", "library_coverage": len(table) / len(guides),
            "qc": qc, "normalization_factors": factors, "guide_fold_changes": changes,
            "concordance": concordance, "pooled": pooled, "genes": summaries}


def _same(actual, expected):
    if type(expected) is dict:
        return type(actual) is dict and set(actual) == set(expected) and all(_same(actual[key], value) for key, value in expected.items())
    if type(expected) is list:
        return type(actual) is list and len(actual) == len(expected) and all(_same(a, b) for a, b in zip(actual, expected))
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    return type(actual) is type(expected) and actual == expected


def _report(actual, expected):
    _record(actual, "crispr-report-v1", ("multiple_testing", "library_coverage", "qc", "normalization_factors",
                                       "guide_fold_changes", "concordance", "pooled", "genes"))
    _require(actual["multiple_testing"] == "benjamini-hochberg", "multiple-testing", "significance requires BH correction")
    _boolean(actual["pooled"], "pooled flag")
    for key, limit in (("qc", MAX_SAMPLES), ("normalization_factors", MAX_SAMPLES),
                       ("guide_fold_changes", MAX_GUIDES), ("concordance", MAX_SAMPLES * MAX_SAMPLES)):
        _items(actual[key], key, limit, True)
    genes = _items(actual["genes"], "reported genes", MAX_GENES)
    expected_genes = {row["gene_id"]: row for row in expected["genes"]}
    seen = set()
    for row in genes:
        _obj(row, "reported gene", ("gene_id", "guide_count", "status", "reasons", "log2_fold_change", "p_value", "q_value", "significant"))
        name = _text(row["gene_id"], "reported gene ID")
        _number(row["guide_count"], "guide count", 0, MAX_GUIDES, True)
        _text(row["status"], "reported gene status")
        _require(name in expected_genes and name not in seen, "report-mismatch", "unknown or duplicate reported gene")
        seen.add(name)
        target = expected_genes[name]
        if "minimum-guides" in target["reasons"]:
            _require(row["status"] == "unavailable" and row["significant"] is None,
                     "insufficient-guides", "too few guides are unavailable, never negative")
        if "sample-qc" in target["reasons"]:
            _require(row["status"] == "unavailable" and row["significant"] is None,
                     "failed-sample-summary", "failed-QC sample cannot contribute a summary")
        if target["status"] == "observed":
            _require(row["q_value"] is not None, "multiple-testing", "BH q values required for every observed gene")
    _require(not actual["pooled"] or expected["pooled"], "discordant-pooling", "failed replicates cannot be pooled")
    _require(_same(actual, expected), "report-mismatch", "reported arithmetic differs from frozen reference")


def _claims(bundle, pack, report):
    claims = _items(pack["claims"], "claims", MAX_CLAIMS, True)
    outputs = _items(pack["study_outputs"], "study outputs", MAX_ARTIFACTS, True)
    own = list(pack["inputs"].values()) + outputs
    for identity in outputs:
        bundle.load(identity)
    own_paths = {identity["path"] for identity in own}
    own_hashes = {identity["sha256"] for identity in own}
    by_gene = {row["gene_id"]: row for row in report["genes"]}
    seen = set()
    for claim in claims:
        _obj(claim, "claim", ("id", "kind", "text", "status", "support", "gene_id"))
        name = _text(claim["id"], "claim ID")
        _require(name not in seen, "invalid-record", "duplicate claim ID")
        seen.add(name)
        text = _text(claim["text"], "claim text")
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        gene = _text(claim["gene_id"], "claim gene")
        _require(status in POSITIVE | {"planned", "conflicting", "unsupported", "withdrawn", "unavailable"},
                 "claim-boundary", "unknown claim status")
        _require(kind in ("descriptive", "associational") and OVERREACH.search(text) is None,
                 "claim-boundary", "only bounded arithmetic observations are permitted")
        _require(status != "unavailable" or UNAVAILABLE_POSITIVE.search(text) is None,
                 "claim-boundary", "unavailable claim cannot assert positive evidence")
        support = _items(claim["support"], "claim support", MAX_SUPPORT, True)
        _require(bool(support) or status == "unavailable", "unavailable-evidence", "absent evidence is unavailable, never negative")
        for identity in support:
            evidence = bundle.load(identity)
            _record(evidence, "crispr-evidence-v1", ("kind", "result", "origin", "gene_id"))
            record_kind = _text(evidence["kind"], "evidence kind")
            result = _text(evidence["result"], "evidence result")
            origin = _text(evidence["origin"], "evidence origin")
            _text(evidence["gene_id"], "evidence gene")
            _require(origin in ("study", "external", "independent", "preregistered"), "invalid-record", "unknown evidence origin")
            if origin != "study":
                _require(identity["path"] not in own_paths and identity["sha256"] not in own_hashes,
                         "dependent-evidence", "declared external evidence aliases a study input/output")
            _require("unavailable" not in (record_kind, result) or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires an unavailable claim")
            if status in POSITIVE:
                _require(NON_EVIDENCE.search(record_kind + " " + result) is None
                         and record_kind == "guide-count-observation" and result == "gene-level-association"
                         and evidence["gene_id"] == gene,
                         "claim-evidence", "review approval and computed agreement cannot support positive claims")
        if status in POSITIVE:
            _require(status != "replicated", "claim-replication", "one synthetic study cannot establish replication")
            _require(gene in by_gene and by_gene[gene]["significant"] is True,
                     "claim-evidence", "positive association requires the full-family BH and fold-change thresholds")
            _require(not pack["exploratory"] or status == "suggestive", "claim-boundary", "exploratory changes stay suggestive")


def _validate(bundle):
    pack, _ = bundle.snapshot(_relative(bundle.entry))
    _record(pack, "crispr-pack-v1", ("stages", "inputs", "frozen_sha256", "frozen_library_sha256",
                                    "frozen_design_sha256", "exploratory", "study_outputs", "claims"))
    _require(pack["stages"] == list(STAGES), "stage-order", "five ordered stages required")
    _boolean(pack["exploratory"], "exploratory flag")
    inputs = _obj(pack["inputs"], "inputs", ("frozen_rules", "rules", "library", "design", "counts", "report"))
    frozen = bundle.load(inputs["frozen_rules"])
    _rules(frozen)
    _require(pack["frozen_sha256"] == inputs["frozen_rules"]["sha256"], "rule-freeze", "frozen rule identity differs")
    rules = bundle.load(inputs["rules"])
    _require(frozen == rules or pack["exploratory"], "post-outcome-rule", "changed rules require an exploratory label")
    _rules(rules)
    library = bundle.load(inputs["library"])
    design = bundle.load(inputs["design"])
    _require(pack["frozen_library_sha256"] == inputs["library"]["sha256"]
             and pack["frozen_design_sha256"] == inputs["design"]["sha256"],
             "rule-freeze", "library and design identities must be frozen before counts")
    counts = bundle.load(inputs["counts"])
    result = reference_computation(rules, library, design, counts)
    _report(bundle.load(inputs["report"]), result)
    _claims(bundle, pack, result)
    bundle.recheck()
    return {"schema": "crispr-result-v1", "schema_version": 1, "fixture": True, "stages": list(STAGES),
            "evidence_level": "offline-arithmetic-only", "review": "unavailable", "exploratory": pack["exploratory"],
            "input_identities": [{"path": name, "sha256": digest} for name, (_, digest, _) in bundle.cache.items()],
            "report": result, "claims": pack["claims"], "limitations": [
                "Synthetic fixtures only; numerical agreement never establishes physical or clinical validity.",
                "Control-null permutations are an arithmetic reference, never gene essentiality or target evidence.",
                "Hash identities cannot prove historical freezing or source independence.",
                "Failed controls, negative results and unavailable evidence remain explicit.",
                "Conservative English lexical checks are incomplete; independent science-review remains coordinator-owned."]}


def validate_crispr_screen_pack(path: Path | str) -> dict:
    """Validate one hash-bound synthetic bundle, return JSON-compatible data, write nothing."""
    _require(isinstance(path, (str, Path)), "input-path", "bundle must be a local text path")
    name = os.fspath(path)
    _require(0 < len(name) <= MAX_TEXT and "\x00" not in name and all(ord(char) >= 32 for char in name),
             "input-path", "bundle path must be bounded text without control characters")
    _require(".." not in Path(name).parts, "input-path", "bundle path cannot contain parent traversal")
    try:
        with _Bundle(path) as bundle:
            return _validate(bundle)
    except (OSError, RuntimeError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError(f"input-file: unavailable or changed bounded input ({type(error).__name__})") from error
