"""Read-only synthetic enrichment-peak QC and exact standard-library interval sweeps."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

STAGES = ("01-rules", "02-intervals", "03-qc-consensus", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_VALUES = 4000000
MAX_ARTIFACTS = 128
MAX_REPLICATES = 16
MAX_CHROMOSOMES = 64
MAX_PEAKS = 20000
MAX_RECORDS = 128
MAX_ITEMS = 40000
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
MAX_INTEGER = 10**12
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
    r"inhibit\w*|activat\w*|regulat\w*|driv\w*|induc\w*|enhanc\w*|promot\w*|"
    r"truth|physical[\s-]+validity|patient[\s-]+benefit\w*)\b", re.I,
)
ASSERTION = re.compile(r"\b(?:supported|replicated|suggestive|significan\w*)\b", re.I)
NON_EVIDENCE = re.compile(r"review|approv|comput|numer|arithmet|result-v1|agreement|truth|physical|clinic", re.I)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= MAX_STRING and bool(value.strip())
             and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
             "invalid-record", f"{label} must be bounded nonempty text")
    return value


def _number(value, label, low=0, high=MAX_NUMBER, integer=False):
    valid = type(value) is int if integer else type(value) in (int, float)
    _require(valid and -MAX_NUMBER <= value <= MAX_NUMBER and math.isfinite(value)
             and low <= value <= high, "invalid-record", f"{label} has invalid numeric type or range")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _fields(value, fields, label):
    expected = fields.split() if type(fields) is str else fields
    _require(type(value) is dict and set(value) == set(expected),
             "invalid-record", f"{label} fields differ from its pack-local schema")
    return value


def _list(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its declared count limit")
    _require(empty or len(value) > 0, "invalid-record", f"{label} must not be empty")
    return value


def _names(value, label, limit, empty=False):
    value = _list(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), "invalid-record", f"duplicate {label}")
    return value


def _record(value, schema, fields):
    _fields(value, "schema schema_version fixture " + fields, schema)
    _number(value["schema_version"], "schema_version", 1, 1, integer=True)
    _require(value["schema"] == schema, "invalid-record", "wrong pack-local schema")
    _require(value["fixture"] == "synthetic fixture", "invalid-record", "fixture label required")
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
    number = int(value)
    _require(abs(number) <= MAX_NUMBER, "invalid-json", "huge JSON integer")
    return number


def _float(value):
    number = float(value)
    _require(math.isfinite(number) and abs(number) <= MAX_NUMBER,
             "invalid-json", "non-finite or huge JSON number")
    return number


def _json(raw, allowance):
    # This upper bound is checked before the parser allocates a tree.
    count = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(count <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container count exceeded")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _require(len(value) <= MAX_STRING and not any(0xD800 <= ord(c) <= 0xDFFF for c in value),
                         "input-limit", "JSON string length or encoding invalid")
        return root, count
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value
             and all(ord(c) >= 32 for c in value),
             "input-path", "canonical bundle-relative path required")
    return path


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        identities = [(opened.st_dev, opened.st_ino)]
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
        return descriptor, identities
    except BaseException:
        os.close(descriptor)
        raise


class _Bundle:
    def __init__(self, path):
        self.root = path.parent
        self.entry = path.name
        self.fd, self.identities = _open_root(self.root)
        self.paths = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.values_read = 0

    def close(self):
        os.close(self.fd)

    def _read(self, path, checked=None):
        directory = os.dup(self.fd)
        flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
        try:
            for part in path.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "real artifact directory required")
                child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                try:
                    actual = os.fstat(child)
                    _require(stat.S_ISDIR(actual.st_mode) and
                             (before.st_dev, before.st_ino) == (actual.st_dev, actual.st_ino),
                             "input-changed", "artifact directory replaced during open")
                except BaseException:
                    os.close(child)
                    raise
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
                         "input-file", "input replaced during open")
                signature = _signature(actual)
                key = signature[:2]
                cached = self.artifacts.get(key)
                if cached is not None:
                    _require(signature == cached[2], "input-changed", "cached input changed")
                    if checked is None or key in checked:
                        return None, signature
                limit = MAX_BYTES if checked is not None else min(MAX_BYTES, MAX_TOTAL_BYTES - self.bytes_read)
                _require(actual.st_size <= limit, "input-limit", "aggregate artifact bytes exceed allowance")
                raw = handle.read(limit + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= limit and len(raw) == actual.st_size
                     and _signature(actual) == _signature(after),
                     "input-changed", "input grew or changed during bounded read")
            return raw, signature
        finally:
            os.close(directory)

    def snapshot(self, name):
        path = _relative(name)
        if name not in self.paths:
            _require(len(self.paths) < MAX_ARTIFACTS, "input-limit", "too many input artifacts")
            raw, signature = self._read(path)
            key = signature[:2]
            if raw is not None:
                value, count = _json(raw, MAX_TOTAL_VALUES - self.values_read)
                self.artifacts[key] = value, hashlib.sha256(raw).hexdigest(), signature
                self.bytes_read += len(raw)
                self.values_read += count
            self.paths[name] = self.artifacts[key]
        return self.paths[name][0]

    def artifact(self, identity):
        _fields(identity, "path sha256", "artifact identity")
        digest = _text(identity["sha256"], "SHA-256")
        _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None, "input-hash", "invalid SHA-256")
        value = self.snapshot(identity["path"])
        _require(self.paths[identity["path"]][1] == digest, "input-hash", "hash differs from parsed bytes")
        return value

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle ancestor chain replaced")
        finally:
            os.close(descriptor)

    def recheck(self):
        self._check_root()
        checked = set()
        for name, (_, digest, signature) in self.paths.items():
            raw, actual = self._read(_relative(name), checked)
            _require(actual == signature and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input replaced during validation")
            checked.add(actual[:2])
        self._check_root()


def _rules(value):
    _record(value, "peak-qc-rules-v1", "genome_build chromosomes replicates minimum_reads minimum_frip "
            "minimum_replicate_overlap reciprocal_interval_fraction blacklist input_control_required "
            "peak_merge_rule minimum_support")
    _text(value["genome_build"], "genome_build")
    chromosomes = value["chromosomes"]
    _require(type(chromosomes) is dict and 0 < len(chromosomes) <= MAX_CHROMOSOMES,
             "input-limit", "chromosome count outside allowance")
    for name, length in chromosomes.items():
        _text(name, "chromosome")
        _number(length, "chromosome length", 1, MAX_INTEGER, integer=True)
    replicates = _names(value["replicates"], "replicates", MAX_REPLICATES)
    _require(len(replicates) >= 2, "insufficient-replicates", "design needs at least two replicates")
    _number(value["minimum_reads"], "minimum_reads", 1, MAX_INTEGER, integer=True)
    for field in ("minimum_frip", "minimum_replicate_overlap", "reciprocal_interval_fraction"):
        _number(value[field], field, 0, 1)
    _boolean(value["input_control_required"], "input_control_required")
    _text(value["peak_merge_rule"], "peak_merge_rule")
    _require(value["peak_merge_rule"] == "supported-segments", "merge-rule", "unsupported peak merge rule")
    _number(value["minimum_support"], "minimum_support", 2, len(replicates), integer=True)
    _fields(value["blacklist"], "path sha256", "blacklist identity")
    return value


def _intervals(rows, rules, scored=False):
    _list(rows, "intervals", MAX_PEAKS, True)
    previous = None
    for row in rows:
        _fields(row, "chrom start end score" if scored else "chrom start end", "interval")
        chrom = _text(row["chrom"], "chromosome")
        _require(chrom in rules["chromosomes"], "unknown-chromosome", "chromosome outside frozen genome")
        start = _number(row["start"], "start", 0, MAX_INTEGER, integer=True)
        end = _number(row["end"], "end", 0, MAX_INTEGER, integer=True)
        _require(start < end <= rules["chromosomes"][chrom],
                 "interval-bounds", "0-based half-open interval outside chromosome")
        if scored:
            _number(row["score"], "score", 0)
        current = (chrom, start, end)
        _require(previous is None or current >= previous, "interval-order", "intervals must be lexically sorted")
        _require(previous is None or chrom != previous[0] or start >= previous[2],
                 "within-replicate-overlap", "overlapping intervals in one set")
        previous = current
    return rows


def _blacklist(value, rules):
    _record(value, "peak-qc-blacklist-v1", "genome_build intervals")
    _require(_text(value["genome_build"], "genome_build") == rules["genome_build"],
             "genome-build", "blacklist and peaks must share frozen genome build")
    return _intervals(value["intervals"], rules)


def _clean(rows, blacklist):
    clean = []
    j = 0
    for row in rows:
        while j < len(blacklist) and (blacklist[j]["chrom"] < row["chrom"] or
              (blacklist[j]["chrom"] == row["chrom"] and blacklist[j]["end"] <= row["start"])):
            j += 1
        hit = j < len(blacklist) and blacklist[j]["chrom"] == row["chrom"] and blacklist[j]["start"] < row["end"]
        if not hit:
            clean.append(row)
    return clean


def _pair(first, second, fraction, covered=None):
    i = j = intersection = 0
    matched_first, matched_second = set(), set()
    while i < len(first) and j < len(second):
        a, b = first[i], second[j]
        if a["chrom"] < b["chrom"]:
            i += 1
            continue
        if b["chrom"] < a["chrom"]:
            j += 1
            continue
        overlap = min(a["end"], b["end"]) - max(a["start"], b["start"])
        if overlap > 0:
            intersection += overlap
            if overlap / (a["end"] - a["start"]) >= fraction and overlap / (b["end"] - b["start"]) >= fraction:
                matched_first.add(i)
                matched_second.add(j)
        if a["end"] <= b["end"]:
            i += 1
        else:
            j += 1
    if covered is None:
        covered = (sum(r["end"] - r["start"] for r in first), sum(r["end"] - r["start"] for r in second))
    union = covered[0] + covered[1] - intersection
    fractions = [len(matched_first) / len(first) if first else 0, len(matched_second) / len(second) if second else 0]
    return {"n_first": len(first), "n_second": len(second), "intersection_bp": intersection, "union_bp": union,
            "jaccard": intersection / union if union else "unavailable", "directional_fractions": fractions,
            "reciprocal_overlap_fraction": min(fractions)}


def _consensus(clean, eligible, minimum):
    events = []
    for name in eligible:
        for row in clean[name]:
            events.append((row["chrom"], row["start"], 1, name))
            events.append((row["chrom"], row["end"], -1, name))
    events.sort()
    result, active = [], set()
    previous = None
    index = 0
    while index < len(events):
        chrom, position = events[index][:2]
        if previous is not None and previous[0] == chrom and previous[1] < position and len(active) >= minimum:
            support = sorted(active)
            if result and result[-1]["chrom"] == chrom and result[-1]["end"] == previous[1] and result[-1]["replicates"] == support:
                result[-1]["end"] = position
            else:
                result.append({"chrom": chrom, "start": previous[1], "end": position,
                               "replicates": support, "n_support": len(support)})
        while index < len(events) and events[index][:2] == (chrom, position):
            _, _, direction, name = events[index]
            if direction == 1:
                active.add(name)
            else:
                active.discard(name)
            index += 1
        previous = chrom, position
    return result


def compute_peak_qc(table, rules, blacklist):
    """Validate supplied synthetic records and compute descriptive interval/read arithmetic."""
    rules = _rules(rules)
    blocked = _blacklist(blacklist, rules)
    _record(table, "peak-qc-peaks-v1", "genome_build replicates")
    _require(_text(table["genome_build"], "genome_build") == rules["genome_build"],
             "genome-build", "peak table and frozen genome builds differ")
    rows = _list(table["replicates"], "replicate records", MAX_REPLICATES)
    # Bound all dimensions before sweeps, sets, pair construction or event allocation.
    total = len(blocked)
    for row in rows:
        _fields(row, "id status genome_build total_reads reads_in_peaks input_control peaks", "replicate")
        if type(row["peaks"]) is list:
            total += len(_list(row["peaks"], "replicate peaks", MAX_PEAKS, True))
    _require(total <= MAX_PEAKS, "input-limit", "aggregate peak count exceeds allowance")
    clean, summaries, seen = {}, [], set()
    for row in rows:
        name = _text(row["id"], "replicate id")
        _require(name in rules["replicates"] and name not in seen, "replicate-design", "replicate missing or duplicated in design")
        seen.add(name)
        _require(_text(row["genome_build"], "replicate build") == rules["genome_build"],
                 "genome-build", "mixed replicate genome builds")
        status = _text(row["status"], "replicate status")
        _require(status in {"available", "unavailable"}, "invalid-record", "unknown replicate status")
        if status == "unavailable":
            _require(all(row[key] == "unavailable" for key in ("total_reads", "reads_in_peaks", "input_control", "peaks")),
                     "unavailable-replicate", "unavailable replicate cannot be reported with zero peaks or counts")
            summaries.append({"id": name, "status": status, "n_peaks": "unavailable", "blacklist_peak_count": "unavailable",
                              "total_reads": "unavailable", "reads_in_peaks": "unavailable", "frip": "unavailable",
                              "eligible": False, "flags": ["unavailable"]})
            continue
        intervals = _intervals(row["peaks"], rules, True)
        reads = _number(row["total_reads"], "total_reads", 0, MAX_INTEGER, integer=True)
        in_peaks = _number(row["reads_in_peaks"], "reads_in_peaks", 0, MAX_INTEGER, integer=True)
        _require(reads > 0 and in_peaks <= reads, "library-counts", "positive library and bounded reads in peaks required")
        _require(bool(intervals) or in_peaks == 0, "library-counts", "no called peaks cannot contain reads")
        control = row["input_control"]
        _require(control != "unavailable" or not rules["input_control_required"],
                 "missing-input-control", "frozen rule requires supplied input control")
        if control != "unavailable":
            _fields(control, "id genome_build total_reads", "input control")
            _text(control["id"], "control id")
            _require(_text(control["genome_build"], "control build") == rules["genome_build"],
                     "genome-build", "input control genome build differs")
            _number(control["total_reads"], "control total_reads", 1, MAX_INTEGER, integer=True)
        clean[name] = _clean(intervals, blocked)
        frip = in_peaks / reads
        flags = []
        if reads < rules["minimum_reads"]:
            flags.append("low-reads")
        if frip < rules["minimum_frip"]:
            flags.append("low-frip")
        summaries.append({"id": name, "status": status, "n_peaks": len(intervals),
                          "blacklist_peak_count": len(intervals) - len(clean[name]),
                          "total_reads": reads, "reads_in_peaks": in_peaks, "frip": frip,
                          "eligible": False, "flags": flags})
    _require(seen == set(rules["replicates"]), "replicate-design", "every frozen replicate needs an explicit record")
    _require(len(clean) >= 2, "insufficient-replicates", "at least two available libraries required")
    available = [r for r in summaries if r["status"] == "available"]
    covered = {name: sum(row["end"] - row["start"] for row in intervals) for name, intervals in clean.items()}
    pairs = []
    for i, first in enumerate(available):
        for second in available[i + 1:]:
            pair = {"first": first["id"], "second": second["id"],
                    **_pair(clean[first["id"]], clean[second["id"]], rules["reciprocal_interval_fraction"],
                            (covered[first["id"]], covered[second["id"]]))}
            pairs.append(pair)
            if pair["reciprocal_overlap_fraction"] < rules["minimum_replicate_overlap"]:
                for row in (first, second):
                    if "low-overlap" not in row["flags"]:
                        row["flags"].append("low-overlap")
    eligible = []
    for row in available:
        row["eligible"] = not row["flags"]
        if row["eligible"]:
            eligible.append(row["id"])
    consensus = _consensus(clean, eligible, rules["minimum_support"])
    return {"n_replicates": len(summaries), "n_available": len(available), "n_eligible": len(eligible),
            "n_pairs": len(pairs), "n_consensus": len(consensus), "replicates": summaries,
            "pairs": pairs, "consensus": consensus}


def _compare(actual, expected):
    if type(expected) is dict:
        _fields(actual, expected, "reported computation")
        for key in expected:
            _compare(actual[key], expected[key])
    elif type(expected) is list:
        _list(actual, "reported rows", MAX_ITEMS, True)
        _require(len(actual) == len(expected), "report-mismatch", "reported row count differs")
        for left, right in zip(actual, expected):
            _compare(left, right)
    elif type(expected) is float:
        _number(actual, "reported fraction")
        _require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
                 "report-mismatch", "reported numerical fraction differs")
    else:
        _require(type(actual) is type(expected) and actual == expected,
                 "report-mismatch", "reported value or integer type differs")


def _claims(claims, records):
    seen = set()
    for claim in _list(claims, "claims", MAX_RECORDS, True):
        _fields(claim, "id kind status text evidence", "claim")
        name = _text(claim["id"], "claim id")
        _require(name not in seen, "invalid-record", "duplicate claim id")
        seen.add(name)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "claims must remain offline interval/read arithmetic")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "evidence ids", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in records, "missing-evidence", "unknown cited evidence")
            record = records[identity]
            labels = record["labels"]
            _require("unavailable" not in labels or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires unavailable claim")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(label) for label in labels),
                     "non-evidence-support", "review approval or computed agreement is not positive evidence")
        _require(status != "replicated", "claim-replication", "a synthetic fixture cannot establish replication")


def _evidence(store, document, own_paths, own_hashes):
    _record(document, "peak-qc-evidence-v1", "records")
    records = {}
    for record in _list(document["records"], "evidence records", MAX_RECORDS, True):
        _fields(record, "id kind result origin source", "evidence record")
        name = _text(record["id"], "evidence id")
        _require(name not in records, "invalid-record", "duplicate evidence id")
        for field in ("kind", "result", "origin"):
            _text(record[field], field)
        _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                 "invalid-record", "unknown evidence origin")
        source = store.artifact(record["source"])
        if record["origin"] != "internal":
            _require(record["source"]["path"] not in own_paths and record["source"]["sha256"] not in own_hashes,
                     "external-alias", "non-internal source aliases a study artifact")
        _record(source, "peak-qc-source-v1", "kind result note")
        for field in ("kind", "result", "note"):
            _text(source[field], field)
        records[name] = {"labels": [record["kind"], record["result"], source["kind"], source["result"]]}
    return records


def _validate(store):
    pack = _record(store.snapshot(store.entry), "peak-qc-pack-v1",
                   "rules frozen_rules_sha256 frozen_before_peaks_read peaks report evidence")
    rules = _rules(store.artifact(pack["rules"]))
    frozen = _text(pack["frozen_rules_sha256"], "frozen_rules_sha256")
    _require(frozen == pack["rules"]["sha256"] and
             _boolean(pack["frozen_before_peaks_read"], "frozen_before_peaks_read"),
             "rule-freeze", "rules must be hash-frozen before peaks are read")
    blacklist = store.artifact(rules["blacklist"])
    _blacklist(blacklist, rules)
    table = store.artifact(pack["peaks"])
    # Validate all frozen controls before a claimed output or wording can mask them.
    computation = compute_peak_qc(table, rules, blacklist)
    report = _record(store.artifact(pack["report"]), "peak-qc-report-v1",
                     "rules_sha256 minimum_replicate_overlap exploratory headline computation claims")
    _require(_text(report["rules_sha256"], "rules_sha256") == frozen,
             "rule-freeze", "report uses different frozen rule identity")
    threshold = _number(report["minimum_replicate_overlap"], "minimum_replicate_overlap", 0, 1)
    exploratory = _boolean(report["exploratory"], "exploratory")
    _require(threshold == rules["minimum_replicate_overlap"] or exploratory,
             "post-hoc-overlap", "changed overlap threshold requires exploratory label")
    if threshold != rules["minimum_replicate_overlap"]:
        revised = dict(rules, minimum_replicate_overlap=threshold)
        computation = compute_peak_qc(table, revised, blacklist)
    supplied = _fields(report["computation"], computation, "computation")
    summaries = _list(supplied["replicates"], "reported replicates", MAX_REPLICATES)
    expected_rows = {r["id"]: r for r in computation["replicates"]}
    for row in summaries:
        _fields(row, computation["replicates"][0], "replicate summary")
        name = _text(row["id"], "replicate id")
        _require(name in expected_rows, "replicate-design", "unknown reported replicate")
        if expected_rows[name]["status"] == "unavailable":
            _require(row["n_peaks"] == "unavailable", "unavailable-replicate", "missing peaks are unavailable, never zero")
    reported_consensus = _list(supplied["consensus"], "reported consensus", MAX_ITEMS, True)
    for row in reported_consensus:
        _fields(row, "chrom start end replicates n_support", "consensus interval")
        _intervals([{key: row[key] for key in ("chrom", "start", "end")}], rules)
    ordered_consensus = sorted(reported_consensus, key=lambda row: (row["chrom"], row["start"], row["end"]))
    _require(len(_clean(ordered_consensus, blacklist["intervals"])) == len(reported_consensus),
             "blacklist-consensus", "blacklist-hit interval retained in consensus")
    for row in reported_consensus:
        support = _names(row["replicates"], "supporting replicates", MAX_REPLICATES)
        _number(row["n_support"], "n_support", 0, MAX_REPLICATES, integer=True)
        _require(all(name in expected_rows and expected_rows[name]["eligible"] for name in support),
                 "excluded-consensus", "failed or unavailable replicate retained in consensus")
    _compare(supplied, computation)
    headline = _text(report["headline"], "headline")
    _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds arithmetic evidence")
    own_paths = set(store.paths)
    own_hashes = {entry[1] for entry in store.paths.values()}
    # The evidence table is also one of the study's own outputs.
    document = store.artifact(pack["evidence"])
    own_paths.add(pack["evidence"]["path"])
    own_hashes.add(pack["evidence"]["sha256"])
    records = _evidence(store, document, own_paths, own_hashes)
    _claims(report["claims"], records)
    store.recheck()
    return {"schema": "peak-qc-result-v1", "schema_version": 1, "fixture": "synthetic fixture",
            "status": "arithmetic-only", "review": "unavailable", "stages": list(STAGES),
            "exploratory": exploratory, "computation": computation, "claims": report["claims"],
            "inputs": [{"path": name, "sha256": entry[1]} for name, entry in sorted(store.paths.items())],
            "limitations": ["Synthetic fixtures check arithmetic only; read counts and interval calls are supplied.",
                            "Hashes do not prove historical freeze timing or experimental independence.",
                            "English lexical claim checks are conservative and incomplete.",
                            "Independent source, method and record review remains unavailable."]}


def validate_peak_replicate_qc_pack(bundle):
    """Validate one immutable, offline JSON bundle without writing any artifact."""
    store = None
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value) and ".." not in Path(value).parts,
                 "input-path", "invalid bundle path")
        path = Path(os.path.abspath(value))
        store = _Bundle(path)
        return _validate(store)
    except OSError as error:
        raise ValueError("input-file: unavailable file or unsafe directory component") from error
    except (TypeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-record: malformed bounded input required") from error
    finally:
        if store is not None:
            store.close()
