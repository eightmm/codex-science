"""Read-only GWAS summary QC fixture validation and stdlib reference computation."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from statistics import median


STAGES = ("01-freeze", "02-harmonization", "03-consistency", "04-signals", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_ROWS = 10000
MAX_ARTIFACTS = 128
MAX_ITEMS = 20000
MAX_JSON_VALUES = 4000000
MAX_RECORDS = 128
MAX_STRING = 4096
MAX_DEPTH = 32
MAX_NUMBER = 1e100
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
    r"physical[\s-]+validity|patient[\s-]+benefit\w*)\b", re.I,
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
    _fields(value, "schema fixture " + fields, schema)
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


def _json(raw, allowance=None):
    allowance = MAX_JSON_VALUES if allowance is None else allowance
    estimate = 1 + raw.count(b",")
    for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw):
        estimate += 1
        _require(estimate <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    _require(estimate <= allowance, "input-limit", "bundle JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_int, parse_float=_float)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) is dict:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON object too large")
                children = list(value.keys()) + list(value.values())
            elif type(value) is list:
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON list too large")
                children = value
            else:
                if type(value) is str:
                    _text(value, "JSON string")
                continue
            pending.extend((child, depth + 1) for child in children)
        return root, estimate
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
        self.total_bytes = 0
        self.json_values = 0
        self.parsed = {}
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
            _require(len(self.snapshots) < MAX_ARTIFACTS, "input-limit", "too many artifacts")
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
            document, count = _json(raw, MAX_JSON_VALUES - self.json_values)
            self.json_values += count
            self.parsed[identity] = document
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


def _protocol(value):
    _record(value, "gwas-summary-qc-protocol-v1",
            "schema_version genome_build trait ancestry effect_allele_convention "
            "p_threshold inflation_limit minimum_n window_bp minimum_frequency p_relative_tolerance")
    _number(value["schema_version"], "schema_version", 1, 1, True)
    for field in ("genome_build", "trait", "ancestry"):
        _text(value[field], field)
    _require(value["effect_allele_convention"] == "beta refers to effect_allele",
             "allele-convention", "explicit effect allele convention required")
    _number(value["p_threshold"], "p_threshold", 0, 1)
    _require(value["p_threshold"] > 0, "invalid-record", "positive p threshold required")
    _number(value["inflation_limit"], "inflation_limit", 1, 100)
    _number(value["minimum_n"], "minimum_n", 2, 10**9, True)
    _number(value["window_bp"], "window_bp", 0, 10**9, True)
    _number(value["minimum_frequency"], "minimum_frequency", 0, 0.5)
    _number(value["p_relative_tolerance"], "p_relative_tolerance", 0, 0.1)
    return value


def reference_computation(table, protocol, *, p_threshold=None, window_bp=None):
    """Compute normal-tail QC and greedy positional signals; never repair rows.

    The frozen relative tolerance compares p to erfc(abs(beta/se)/sqrt(2)).
    Ambiguous strands cannot enter frequency checks, validated rows or signals.
    """
    protocol = _protocol(protocol)
    _record(table, "gwas-summary-qc-table-v1", "schema_version genome_build rows")
    _number(table["schema_version"], "schema_version", 1, 1, True)
    _text(table["genome_build"], "table genome_build")
    _require(table["genome_build"] == protocol["genome_build"], "genome-build", "table differs from freeze")
    rows = _list(table["rows"], "variant rows", MAX_ROWS)
    threshold = protocol["p_threshold"] if p_threshold is None else _number(p_threshold, "p_threshold", 0, 1)
    _require(threshold > 0, "invalid-record", "positive p threshold required")
    window = protocol["window_bp"] if window_bp is None else _number(window_bp, "window_bp", 0, 10**9, True)
    seen, accepted, excluded, ambiguous, checked = set(), [], [], [], []
    fields = ("id chromosome position effect_allele other_allele original_effect_allele "
              "original_other_allele flip_declared beta se p n frequency")
    for row in rows:
        _fields(row, fields, "variant row")
        identity = _text(row["id"], "variant id")
        _require(identity not in seen, "duplicate-variant", "variant IDs must be unique")
        seen.add(identity)
        _text(row["chromosome"], "chromosome")
        _number(row["position"], "position", 1, 10**9, True)
        for field in ("effect_allele", "other_allele", "original_effect_allele", "original_other_allele"):
            _text(row[field], field)
            _require(row[field] in {"A", "C", "G", "T"}, "allele-record", "reference supports biallelic SNVs only")
        pair = (row["effect_allele"], row["other_allele"])
        original = (row["original_effect_allele"], row["original_other_allele"])
        _require(pair[0] != pair[1] and original[0] != original[1], "allele-record", "alleles must differ")
        flipped = _boolean(row["flip_declared"], "flip_declared")
        _require((not flipped and pair == original) or (flipped and pair == original[::-1]),
                 "undeclared-flip", "allele orientation changed without matching declared flip")
        for field in ("beta", "se", "p", "frequency"):
            _number(row[field], field, -MAX_NUMBER)
        _number(row["n"], "n", 0, 10**9, True)
        _require(row["p"] != 0, "p-zero", "zero or underflowed reported p is refused")
        reasons = []
        if frozenset(pair) in (frozenset("AT"), frozenset("CG")):
            ambiguous.append(identity)
            reasons.append("ambiguous-strand")
        if row["se"] <= 0:
            reasons.append("standard-error")
        if not 0 < row["p"] <= 1:
            reasons.append("p-range")
        if row["n"] < protocol["minimum_n"]:
            reasons.append("sample-size")
        if "ambiguous-strand" not in reasons:
            checked.append(identity)
            if not 0 <= row["frequency"] <= 1:
                reasons.append("frequency-range")
            if min(row["frequency"], 1 - row["frequency"]) < protocol["minimum_frequency"]:
                reasons.append("low-frequency")
        chi = None
        if row["se"] > 0:
            z = row["beta"] / row["se"]
            _require(math.isfinite(z) and abs(z) <= math.sqrt(MAX_NUMBER),
                     "numerical-range", "z is outside the finite reference envelope")
            expected = math.erfc(abs(z) / math.sqrt(2))
            _require(expected > 0, "p-underflow", "normal-tail underflow cannot become exact zero evidence")
            if abs(row["p"] - expected) > protocol["p_relative_tolerance"] * max(row["p"], expected):
                reasons.append("p-inconsistent")
            chi = z * z
        if reasons:
            excluded.append({"id": identity, "reasons": reasons})
        else:
            accepted.append((row, chi))
    _require(len(accepted) >= 2, "degenerate-input", "at least two QC-passing variants required")
    chis = [chi for _, chi in accepted]
    _require(max(chis) > min(chis), "degenerate-input", "zero-variance chi-square inputs refused")
    inflation = median(chis) / 0.4549
    risk = inflation > protocol["inflation_limit"]
    leads = []
    candidates = sorted((row for row, _ in accepted if row["p"] <= threshold), key=lambda r: (r["p"], r["id"]))
    for row in candidates:
        if all(row["chromosome"] != lead["chromosome"] or abs(row["position"] - lead["position"]) > window
               for lead in leads):
            leads.append({"id": row["id"], "chromosome": row["chromosome"], "position": row["position"],
                          "p": row["p"], "label": "positional signal", "inflated_risk": risk})
    return {"lambda_gc": inflation, "inflated": risk, "signals": leads, "excluded": excluded,
            "ambiguous": ambiguous, "frequency_checked": checked,
            "validated": [row["id"] for row, _ in accepted]}


def _claims(claims, evidence):
    seen = set()
    for claim in _list(claims, "claims", MAX_RECORDS, True):
        _fields(claim, "id kind status text evidence", "claim")
        identity = _text(claim["id"], "claim id")
        _require(identity not in seen, "invalid-record", "duplicate claim id")
        seen.add(identity)
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        _require(status in STATUSES and kind in {"descriptive", "associational"},
                 "claim-kind", "only descriptive or associational claims with known statuses")
        text = _text(claim["text"], "claim text")
        _require(not OVERREACH.search(text), "claim-overreach", "wording exceeds statistical association evidence")
        ids = _names(claim["evidence"], "claim evidence", MAX_RECORDS, True)
        _require(ids or status == "unavailable", "missing-evidence", "empty evidence requires unavailable status")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claims cannot assert positive evidence")
        for name in ids:
            _require(name in evidence, "missing-evidence", "unknown evidence identity")
            record = evidence[name]
            _require("unavailable" not in (record["kind"], record["result"]) or status == "unavailable",
                     "unavailable-evidence", "any unavailable citation requires unavailable status")
            _require(status not in POSITIVE or not any(NON_EVIDENCE.search(record[key]) for key in ("kind", "result")),
                     "non-evidence-support", "computed agreement and review approval cannot support positive claims")
        _require(status != "replicated", "claim-replication", "a single synthetic fixture cannot establish replication")


def _report_check(report, computed):
    for name in ("ambiguous", "frequency_checked", "validated"):
        _names(report[name], name, MAX_ROWS, True)
    ambiguous = set(computed["ambiguous"])
    _require(not ambiguous.intersection(report["frequency_checked"]) and not ambiguous.intersection(report["validated"]),
             "ambiguous-frequency", "ambiguous strands cannot enter frequency checks or validated counts")
    signals = _list(report["signals"], "signals", MAX_ROWS, True)
    exclusion = {item["id"]: item["reasons"] for item in computed["excluded"]}
    for signal in signals:
        _fields(signal, "id chromosome position p label inflated_risk", "positional signal")
        identity = _text(signal["id"], "signal id")
        _text(signal["chromosome"], "signal chromosome")
        _number(signal["position"], "signal position", 1, 10**9, True)
        _number(signal["p"], "signal p", 0, 1)
        _text(signal["label"], "signal label")
        _require(not OVERREACH.search(signal["label"]), "claim-overreach", "positional signal is never a causal gene")
        _require("sample-size" not in exclusion.get(identity, []), "sample-size-signal", "low-n rows cannot contribute signals")
        _require("p-inconsistent" not in exclusion.get(identity, []), "p-inconsistent", "inconsistent p rows cannot contribute signals")
        flag = _boolean(signal["inflated_risk"], "inflated_risk")
        _require(not computed["inflated"] or flag, "inflation-flag", "inflated signals require inflated-risk flags")
    _require(not computed["inflated"] or _boolean(report["inflated"], "inflated"),
             "inflation-flag", "lambda above frozen limit requires inflation flag")
    _boolean(report["inflated"], "inflated")
    _number(report["lambda_gc"], "lambda_gc")
    _require(math.isclose(report["lambda_gc"], computed["lambda_gc"], rel_tol=1e-12, abs_tol=0),
             "inflation-mismatch", "reported lambda differs from median chi-square / 0.4549")
    # These checks are independent of the generic report comparison, retaining
    # specific refusal codes for each seeded scientific control.
    listed = _list(report["excluded"], "excluded", MAX_ROWS, True)
    for item in listed:
        _fields(item, "id reasons", "excluded row")
        _text(item["id"], "excluded id")
        _names(item["reasons"], "excluded reasons", MAX_RECORDS)
    for item in computed["excluded"]:
        if "p-inconsistent" in item["reasons"]:
            _require(item in listed and item["id"] not in report["validated"],
                     "p-inconsistent", "inconsistent rows must be listed and excluded")
    _require(all(report[field] == computed[field] for field in computed),
             "report-mismatch", "QC exclusions, flags or positional signals differ from reference")


def validate_gwas_summary_qc_pack(bundle):
    """Validate one hash-bound synthetic pack JSON; return JSON-compatible data."""
    try:
        value = _text(os.fspath(bundle), "bundle path")
        _require(all(ord(c) >= 32 for c in value), "input-path", "control character in bundle path")
        path = Path(os.path.abspath(value))
    except (TypeError, ValueError) as error:
        raise ValueError("input-path: invalid bundle path") from error
    store = _Bundle(path.parent)
    try:
        pack = _record(store.load(path.name), "gwas-summary-qc-pack-v1",
                       "protocol frozen_protocol_sha256 frozen_before_table_read table report evidence stages")
        _require(pack["stages"] == list(STAGES), "stage-order", "five fixed ordered stage IDs required")
        protocol = _protocol(store.artifact(pack["protocol"]))
        _require(_text(pack["frozen_protocol_sha256"], "frozen_protocol_sha256") == pack["protocol"]["sha256"]
                 and _boolean(pack["frozen_before_table_read"], "frozen_before_table_read"),
                 "protocol-freeze", "protocol must be hash-frozen before the table is read")
        report = _record(store.artifact(pack["report"]), "gwas-summary-qc-report-v1",
                         "protocol_sha256 p_threshold window_bp exploratory headline claims "
                         "lambda_gc inflated signals excluded ambiguous frequency_checked validated")
        _require(_text(report["protocol_sha256"], "protocol_sha256") == pack["protocol"]["sha256"],
                 "protocol-freeze", "report refers to a different protocol")
        threshold = _number(report["p_threshold"], "p_threshold", 0, 1)
        window = _number(report["window_bp"], "window_bp", 0, 10**9, True)
        exploratory = _boolean(report["exploratory"], "exploratory")
        _require((threshold == protocol["p_threshold"] and window == protocol["window_bp"]) or exploratory,
                 "post-hoc-change", "changed threshold or window requires an exploratory label")
        computed = reference_computation(store.artifact(pack["table"]), protocol,
                                         p_threshold=threshold, window_bp=window)
        _report_check(report, computed)
        _require(not OVERREACH.search(_text(report["headline"], "headline")),
                 "claim-overreach", "headline exceeds statistical association evidence")
        descriptors = _list(pack["evidence"], "evidence artifacts", MAX_RECORDS, True)
        own_paths = {path.name}
        own_hashes = {store.snapshots[path.name][2]}
        for descriptor in (pack["protocol"], pack["table"], pack["report"], *descriptors):
            _fields(descriptor, "path sha256", "artifact identity")
            own_paths.add(str(_relative(descriptor["path"])))
            own_hashes.add(_text(descriptor["sha256"], "sha256"))
        evidence = {}
        for descriptor in descriptors:
            document = _record(store.artifact(descriptor), "gwas-summary-qc-evidence-v1", "records")
            records = _list(document["records"], "evidence records", MAX_RECORDS, True)
            _require(len(evidence) + len(records) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in records:
                _fields(record, "id kind result origin source", "evidence record")
                identity = _text(record["id"], "evidence id")
                _require(identity not in evidence, "invalid-record", "duplicate evidence id")
                for name in ("kind", "result", "origin"):
                    _text(record[name], name)
                _require(record["origin"] in {"internal", "external", "independent", "preregistered"},
                         "invalid-record", "unknown evidence origin")
                digest = store.artifact(record["source"], parse=False)
                if record["origin"] != "internal":
                    _require(record["source"]["path"] not in own_paths and digest not in own_hashes,
                             "external-alias", "independence label aliases the study's own artifacts")
                evidence[identity] = record
        _claims(report["claims"], evidence)
        store.finish()
        return {"schema": "gwas-summary-qc-result-v1", "fixture": "synthetic fixture",
                "status": "statistical-association-evidence-only", "review": "unavailable", "stages": list(STAGES),
                "exploratory": exploratory, "computation": computed, "claims": report["claims"],
                "inputs": [{"path": name, "sha256": item[2]} for name, item in sorted(store.snapshots.items())],
                "limitations": ["Synthetic fixtures establish software behavior only.",
                                "Positional signals use no LD reference and identify no genes.",
                                "Hash declarations cannot prove historical freezing or real independence.",
                                "Genomic inflation may reflect confounding, structure or polygenicity.",
                                "Independent review remains unavailable; numerical agreement is not physical validity."]}
    finally:
        store.close()
