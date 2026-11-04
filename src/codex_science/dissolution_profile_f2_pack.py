"""Read-only synthetic dissolution profiles and mean-based f1/f2 arithmetic."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import statistics


STAGES = ("01-rule-freeze", "02-table-qc", "03-factors", "04-summary", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_UNITS = 1024
MAX_TIME_POINTS = 128
MAX_PRODUCTS = 2
MAX_NODES = 4000000
MAX_RECORDS = 128
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
REL_TOL = 1e-8
EDGE_TOL = 1e-12
REL_DEGENERATE = 1e-12
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*|bioequiv\w*|interchange\w*|"
    r"product[\s-]+quality|accept\w*)\b", re.I,
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
    _require(type(value) is dict and len(value) == len(expected) and set(value) == set(expected),
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
    _fields(value, "schema fixture " + fields, schema)
    _require(value["schema"] == schema, "invalid-record", "wrong pack-local schema")
    _require(value["fixture"] == "synthetic fixture", "invalid-record", "fixture label required")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ROWS, "input-limit", "JSON object exceeds container limit")
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


def _json(raw, allowance=None):
    allowance = MAX_NODES if allowance is None else allowance
    _require(1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw)) <= allowance,
             "input-limit", "bundle JSON value allowance exceeded before parsing")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        nodes = 0
        while pending:
            value, depth = pending.pop()
            nodes += 1
            _require(nodes <= allowance, "input-limit", "bundle JSON value allowance exceeded")
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ROWS, "input-limit", "JSON container exceeds limit")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _text(value, "JSON string")
        return root, nodes
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
    def __init__(self, root):
        self.root = root
        self.fd = None
        self.snapshots = {}
        self.cache = {}
        self.parsed = {}
        self.nodes = 0
        self.total_bytes = 0
        self.rechecked = None
        try:
            self.fd, self.identities = _open_root(root)
        except (OSError, ValueError) as error:
            self.close()
            if isinstance(error, ValueError):
                raise
            raise ValueError("input-root: cannot pin bundle directory") from error

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self, name):
        relative = _relative(name)
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                info = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(info.st_mode), "input-file", "symlinked directory refused")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino),
                         "input-file", "artifact directory replaced")
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                actual = os.fstat(handle.fileno())
                _require(stat.S_ISREG(actual.st_mode) and actual.st_size <= MAX_BYTES
                         and _signature(before) == _signature(actual),
                         "input-file", "input changed before descriptor validation")
                identity = actual.st_dev, actual.st_ino
                signature = _signature(actual)
                if self.rechecked is not None:
                    _require(signature == self.snapshots[name][1],
                             "input-changed", "input replaced during validation")
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[1], "input-changed", "cached input changed")
                    if self.rechecked is None or identity in self.rechecked:
                        return cached[0], signature
                if self.rechecked is None:
                    _require(self.total_bytes + actual.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate artifact bytes exceed 256 MiB")
                raw = handle.read(actual.st_size + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) <= MAX_BYTES and len(raw) == actual.st_size
                     and _signature(actual) == _signature(after),
                     "input-file", "input grew or changed during bounded read")
            return raw, _signature(after)
        except (OSError, UnicodeError) as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def load(self, name, digest=None, parse=True):
        _relative(name)
        if name not in self.snapshots:
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        raw, _, actual = self.snapshots[name]
        if digest is not None:
            _text(digest, "sha256")
            _require(re.fullmatch(r"[0-9a-f]{64}", digest) is not None and digest == actual,
                     "input-hash", "artifact hash differs from parsed bytes")
        if not parse:
            return actual
        identity = self.snapshots[name][1][:2]
        if identity not in self.parsed:
            record, nodes = _json(raw, MAX_NODES - self.nodes)
            self.nodes += nodes
            self.parsed[identity] = record
        return self.parsed[identity]

    def artifact(self, descriptor, parse=True):
        _fields(descriptor, "path sha256", "artifact identity")
        _require(type(descriptor["sha256"]) is str
                 and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None,
                 "input-hash", "artifact requires a lowercase 64-hex SHA-256")
        return self.load(descriptor["path"], descriptor["sha256"], parse)

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "input-root", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        try:
            self._check_root()
            self.rechecked = set()
            for name, (_, signature, digest) in self.snapshots.items():
                raw, current = self._read(name)
                _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                         "input-changed", "input replaced during validation")
                self.rechecked.add(current[:2])
            self._check_root()
        except OSError as error:
            raise ValueError("input-root: root unavailable at final recheck") from error
        finally:
            self.rechecked = None

def _close(actual, expected):
    return math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=0)


def _edge(actual, expected):
    return math.isclose(actual, expected, rel_tol=EDGE_TOL, abs_tol=0)


def _times(value, label, empty=False):
    values = _list(value, label, MAX_TIME_POINTS, empty)
    for item in values:
        _number(item, label, 0, 1e9)
    _require(all(b > a and not _close(a, b) for a, b in zip(values, values[1:])),
             "time-points", "time points must increase distinctly under relative tolerance")
    return values


def _selection(value, times):
    selected = _times(value, "selected time points", True)
    indices = []
    for time in selected:
        _require(time > 0, "time-zero", "time point zero must be excluded")
        matches = [i for i, frozen in enumerate(times) if _close(time, frozen)]
        _require(len(matches) == 1, "time-points", "selection must use shared frozen time points")
        indices.append(matches[0])
    return selected, indices


def _rules(value):
    _record(value, "dissolution-rules-v1", "product_ids units_per_product time_points selected_time_points "
            "minimum_time_points first_cv_limit later_cv_limit late_percent_limit maximum_late_points "
            "f2_threshold averaging_rule")
    ids = _names(value["product_ids"], "product identities", MAX_PRODUCTS)
    _require(len(ids) == 2, "product-identity", "exactly reference then test identities required")
    _fields(value["units_per_product"], ids, "units per product")
    for product in ids:
        _number(value["units_per_product"][product], "frozen unit count", 1, MAX_UNITS, True)
    times = _times(value["time_points"], "shared time points")
    _selection(value["selected_time_points"], times)
    _number(value["minimum_time_points"], "minimum time points", 3, MAX_TIME_POINTS, True)
    _number(value["maximum_late_points"], "maximum late points", 1, 1, True)
    for field, expected in (("first_cv_limit", 20), ("later_cv_limit", 10),
                            ("late_percent_limit", 85), ("f2_threshold", 50)):
        _number(value[field], field)
        _require(_close(value[field], expected), "frozen-threshold", "fixed arithmetic threshold changed")
    _require(value["averaging_rule"] == "product-means-per-time-point",
             "mean-rule", "f1 and f2 must use product means, never individual unit pairs")
    return value


def compute_dissolution(profiles, rules, selected_time_points=None):
    """Return descriptive f1/f2 and sample-CV controls for synthetic profiles."""
    rules = _rules(rules)
    selected, indices = _selection(rules["selected_time_points"] if selected_time_points is None
                                   else selected_time_points, rules["time_points"])
    _record(profiles, "dissolution-profiles-v1", "products")
    products = _list(profiles["products"], "products", MAX_PRODUCTS)
    _require(len(products) == 2, "product-identity", "both frozen products required")
    by_id = {}
    means, cvs, counts = {}, {}, {}
    selected_indices = set(indices)
    for product in products:
        _fields(product, "product_id time_points units", "product profiles")
        identity = _text(product["product_id"], "product id")
        _require(identity in rules["product_ids"] and identity not in by_id,
                 "product-identity", "unknown or duplicate product identity")
        times = _times(product["time_points"], "product time points")
        _require(len(times) == len(rules["time_points"]) and
                 all(_close(a, b) for a, b in zip(times, rules["time_points"])),
                 "unequal-time-points", "products must share every frozen time point")
        units = _list(product["units"], "product units", MAX_UNITS)
        _require(len(units) >= rules["units_per_product"][identity],
                 "insufficient-units", "fewer units than frozen count")
        seen = set()
        columns = [[] for _ in times]
        for unit in units:
            _fields(unit, "unit_id percentages", "unit profile")
            unit_id = _text(unit["unit_id"], "unit id")
            _require(unit_id not in seen, "duplicate-unit", "unit identities must be unique within product")
            seen.add(unit_id)
            values = _list(unit["percentages"], "percentages", MAX_TIME_POINTS)
            _require(len(values) == len(times), "unequal-time-points", "each unit needs every time point")
            for column, value in zip(columns, values):
                _number(value, "percent dissolved", 0, 100)
                column.append(value)
        by_id[identity] = product
        counts[identity] = len(units)
        means[identity] = [math.fsum(column) / len(column) for column in columns]
        cvs[identity] = []
        for i, column in enumerate(columns):
            if i not in selected_indices:
                cvs[identity].append("unavailable")
                continue
            scale = max(column)
            _require(scale > 0 and means[identity][i] > scale * REL_DEGENERATE,
                     "degenerate-numerics", "selected mean cannot define a relative CV")
            cvs[identity].append(100 * statistics.stdev(column) / means[identity][i]
                                  if len(column) >= 2 else "unavailable")
    reference, test = rules["product_ids"]
    late = [i for i in indices if any(means[p][i] > rules["late_percent_limit"]
                                     and not _edge(means[p][i], rules["late_percent_limit"])
                                     for p in rules["product_ids"])]
    _require(len(late) <= rules["maximum_late_points"],
             "multiple-late-points", "at most one selected point after 85 percent in either product")
    controls = []
    for product in rules["product_ids"]:
        for order, i in enumerate(indices):
            cv = cvs[product][i]
            limit = rules["first_cv_limit"] if order == 0 else rules["later_cv_limit"]
            passed = cv <= limit or _edge(cv, limit) if type(cv) in (int, float) else "unavailable"
            controls.append({"product_id": product, "time_point": rules["time_points"][i],
                             "cv": cv, "limit": limit, "passed": passed})
    enough = all(counts[p] >= 12 and rules["units_per_product"][p] >= 12 for p in counts)
    available = enough and len(indices) >= rules["minimum_time_points"]
    status = ("unavailable" if not available else
              "variability-too-high" if any(row["passed"] is False for row in controls) else "computed")
    f1, f2 = "unavailable", "unavailable"
    threshold_result = "unavailable"
    if indices:
        r = [means[reference][i] for i in indices]
        t = [means[test][i] for i in indices]
        denominator = math.fsum(r)
        _require(max(r) > 0 and denominator > max(r) * len(r) * REL_DEGENERATE,
                 "degenerate-numerics", "relative reference sum is degenerate")
        f1 = 100 * math.fsum(abs(a - b) for a, b in zip(r, t)) / denominator
        if available:
            squared = math.fsum((a - b) ** 2 for a, b in zip(r, t)) / len(r)
            f2 = 50 * math.log10(100 / math.sqrt(1 + squared))
            if status == "computed":
                threshold_result = "at-or-above-50" if f2 >= 50 or _edge(f2, 50) else "below-50"
    return {"unit_counts": counts, "selected_time_points": selected,
            "means": {p: [means[p][i] for i in indices] for p in rules["product_ids"]},
            "cv_controls": controls, "f1": f1, "f2": f2, "f2_status": status,
            "threshold_result": threshold_result,
            "summary": {"selected_points": len(indices), "late_points": len(late),
                        "failed_cv_controls": sum(row["passed"] is False for row in controls)}}


def _same(actual, expected, label):
    if type(expected) in (int, float):
        _number(actual, label, -MAX_NUMBER)
        _require(_close(actual, expected), "reported-number", f"reported {label} disagrees with reference")
    elif type(expected) is dict:
        _fields(actual, expected, label)
        if label in {"unit_counts", "summary"}:
            for value in actual.values():
                _number(value, "reported count", 1 if label == "unit_counts" else 0,
                        MAX_UNITS if label == "unit_counts" else MAX_ROWS, True)
        for key in expected:
            _same(actual[key], expected[key], key)
    elif type(expected) is list:
        _list(actual, label, MAX_ROWS, True)
        _require(len(actual) == len(expected), "reported-result", "reported result count differs")
        for a, b in zip(actual, expected):
            _same(a, b, label)
    else:
        _require(type(actual) is type(expected) and actual == expected,
                 "reported-result", f"reported {label} differs from reference")


def _claims(claims, evidence):
    claims = _list(claims, "claims", MAX_RECORDS, True)
    seen = set()
    for claim in claims:
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "invalid-record", "duplicate claim id")
        seen.add(identity)
        kind = _text(claim["kind"], "claim kind")
        status = _text(claim["status"], "claim status")
        text = _text(claim["text"], "claim text")
        _require(kind in {"descriptive", "associational"} and not OVERREACH.search(text),
                 "claim-overreach", "claim exceeds bounded synthetic arithmetic")
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim asserts positive evidence")
        for identity in ids:
            _require(identity in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[identity]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "unavailable records require unavailable claims")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "review approval and computed agreement are not positive evidence")
        _require(status != "replicated", "claim-replication", "one synthetic fixture cannot establish replication")


def validate_dissolution_profile_f2_pack(bundle):
    """Validate one immutable offline fixture bundle; write nothing."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value) and ".." not in Path(value).parts and "\\" not in value,
                 "input-path", "bundle path must be canonical without traversal")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "dissolution-pack-v1",
                       "rules frozen_rules_sha256 frozen_before_percentages_read profiles report evidence")
        rules = _rules(store.artifact(pack["rules"]))
        _require(_text(pack["frozen_rules_sha256"], "frozen rules hash") == pack["rules"]["sha256"]
                 and _boolean(pack["frozen_before_percentages_read"], "frozen before percentages read"),
                 "rule-freeze", "rules must be hash-frozen before percentages are opened")
        report = _record(store.artifact(pack["report"]), "dissolution-report-v1",
                         "rules_sha256 exploratory selected_time_points averaging_rule computation headline claims")
        _require(_text(report["rules_sha256"], "rules hash") == pack["rules"]["sha256"],
                 "rule-freeze", "report cites a different frozen rule revision")
        exploratory = _boolean(report["exploratory"], "exploratory")
        selected, indices = _selection(report["selected_time_points"], rules["time_points"])
        _, frozen_indices = _selection(rules["selected_time_points"], rules["time_points"])
        _require(indices == frozen_indices or exploratory,
                 "post-hoc-selection", "post-outcome time-point change requires exploratory label")
        _require(report["averaging_rule"] == rules["averaging_rule"],
                 "mean-rule", "factors must use per-time-point product means")
        headline = _text(report["headline"], "headline")
        _require(not OVERREACH.search(headline), "claim-overreach", "headline exceeds synthetic arithmetic")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["rules"], pack["profiles"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "dissolution-evidence-v1", "records")
            records = _list(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence identity")
                for key in ("kind", "result", "origin"):
                    _text(record[key], key)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                         "invalid-record", "unknown source origin")
                digest = store.artifact(record["source"], parse=False)
                if record["origin"] != "internal":
                    _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                             "external-alias", "independence label aliases own artifacts")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        result = compute_dissolution(store.artifact(pack["profiles"]), rules, selected)
        _fields(report["computation"], result, "reported computation")
        _require(report["computation"]["f2_status"] == result["f2_status"],
                 "cv-status", "CV failures and insufficient inputs must retain their non-comparison status")
        _require(report["computation"]["threshold_result"] == result["threshold_result"],
                 "arithmetic-threshold", "threshold is unavailable unless all frozen controls pass")
        if result["f2_status"] != "computed":
            wording = [headline] + [claim["text"] for claim in report["claims"]]
            _require(not any(re.search(r"\bsimilar\w*\b", text, re.I) for text in wording),
                     "similarity-wording", "failed controls or unavailable factors prohibit similarity wording")
        _same(report["computation"], result, "computation")
        store.finish()
        return {"schema": "dissolution-result-v1", "fixture": "synthetic fixture", "status": "arithmetic-only",
                "review": "unavailable", "stages": list(STAGES), "exploratory": exploratory,
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "computation": result, "claims": report["claims"],
                "limitations": ["Synthetic profiles establish arithmetic only.",
                                "Numerical agreement cannot establish physical or clinical validity.",
                                "Hash declarations cannot establish historical freeze timing or independence.",
                                "Independent record, source and method review remains unavailable."]}
    finally:
        store.close()
