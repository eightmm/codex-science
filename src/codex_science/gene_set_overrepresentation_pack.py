"""Offline gene-set over-representation admission and exact reference computation."""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


STAGES = ("01-freeze", "02-identity", "03-testing", "04-redundancy", "05-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4_000_000
MAX_ITEMS = 20000
MAX_DEPTH = 32
MAX_TEXT = 4096
MAX_GENES = 2000
MAX_SETS = 128
MAX_LISTS = 2
MAX_MEMBERSHIPS = 10000
MAX_TESTS = 256
MAX_PAIRS = 32640
MAX_TAIL_TERMS = 200000
MAX_RECORDS = 128
MAX_CLAIMS = 100
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
    _require(type(value) is str and 0 < len(value) <= MAX_TEXT and bool(value.strip())
             and not any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF for c in value),
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
    _require(type(value) is dict and set(value) == set(fields.split()),
             "invalid-record", f"{label} fields differ from its pack-local schema")
    return value


def _items(value, label, limit, empty=False):
    _require(type(value) is list, "invalid-record", f"{label} must be a list")
    _require(len(value) <= limit, "input-limit", f"{label} exceeds its count limit")
    _require(empty or bool(value), "invalid-record", f"{label} must not be empty")
    return value


def _names(value, label, limit, empty=False, code="duplicate-identifier"):
    _items(value, label, limit, empty)
    for item in value:
        _text(item, label)
    _require(len(set(value)) == len(value), code, f"duplicate {label}")
    return value


def _record(value, schema, fields):
    _fields(value, "schema fixture " + fields, schema)
    _require(value["schema"] == schema and value["fixture"] == "synthetic fixture",
             "invalid-record", "named schema and synthetic fixture label required")
    return value


def _pairs(pairs):
    _require(len(pairs) <= MAX_ITEMS, "input-limit", "too many JSON object fields")
    result = {}
    for key, value in pairs:
        _require(key not in result, "invalid-json", "duplicate JSON key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("invalid-json: non-finite JSON number")


def _integer(value):
    _require(len(value.lstrip("-")) <= 101, "invalid-json", "huge JSON integer")
    number = int(value)
    _require(abs(number) <= MAX_NUMBER, "invalid-json", "huge JSON integer")
    return number


def _floating(value):
    number = float(value)
    _require(math.isfinite(number) and abs(number) <= MAX_NUMBER,
             "invalid-json", "non-finite or huge JSON number")
    return number


def _json(raw, allowance):
    # This overestimate also counts commas and brackets inside strings, before
    # allocating a tree. Cached hardlinks consume the bundle allowance once.
    upper = 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))
    _require(upper <= allowance, "input-limit", "aggregate JSON value allowance exceeded")
    try:
        root = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant, parse_int=_integer, parse_float=_floating)
        _require(type(root) is dict, "invalid-json", "JSON root must be an object")
        pending = [(root, 0)]
        while pending:
            value, depth = pending.pop()
            _require(depth <= MAX_DEPTH, "invalid-json", "JSON nesting limit exceeded")
            if type(value) in (dict, list):
                _require(len(value) <= MAX_ITEMS, "input-limit", "JSON container exceeds limit")
                children = value.items() if type(value) is dict else enumerate(value)
                for key, child in children:
                    if type(key) is str:
                        _text(key, "JSON key")
                    pending.append((child, depth + 1))
            elif type(value) is str:
                _text(value, "JSON string")
        return root, upper
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid-json: bounded finite UTF-8 JSON object required") from error
    except json.JSONDecodeError as error:
        raise ValueError("invalid-json: malformed JSON") from error


def _relative(value):
    value = _text(value, "artifact path")
    path = PurePosixPath(value)
    _require(not path.is_absolute() and ".." not in path.parts and "\\" not in value
             and path.as_posix() == value and value != "." and ":" not in value,
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
        self.paths = {}
        self.cache = {}
        self.total_bytes = 0
        self.total_nodes = 0
        try:
            self.fd, self.identities = _open_root(root)
        except OSError as error:
            raise ValueError("input-root: cannot pin bundle directory") from error

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _read(self, name, rechecked=None):
        relative = _relative(name)
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "input-file", "real artifact directories required")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require((actual.st_dev, actual.st_ino) == (before.st_dev, before.st_ino),
                         "input-file", "artifact directory replaced")
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_BYTES,
                     "input-file", "regular input at most 64 MiB required")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as handle:
                actual = os.fstat(handle.fileno())
                signature = _signature(actual)
                _require(stat.S_ISREG(actual.st_mode) and actual.st_size <= MAX_BYTES
                         and signature == _signature(before),
                         "input-file", "input changed before descriptor validation")
                identity = signature[:2]
                if rechecked is not None:
                    _require(signature == self.paths[name][0], "input-changed", "input replaced")
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[0], "input-changed", "cached input changed")
                    if rechecked is None or identity in rechecked:
                        return cached[1], signature
                if rechecked is None:
                    _require(self.total_bytes + actual.st_size <= MAX_TOTAL_BYTES,
                             "input-limit", "aggregate artifact bytes exceed limit")
                raw = handle.read(min(MAX_BYTES, actual.st_size) + 1)
                after = os.fstat(handle.fileno())
            _require(len(raw) == actual.st_size and signature == _signature(after),
                     "input-file", "input grew or changed during bounded read")
            return raw, signature
        except (OSError, UnicodeError) as error:
            raise ValueError("input-file: unavailable input or symlinked component") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def load(self, name, digest=None):
        _relative(name)
        if name not in self.paths:
            _require(len(self.paths) < MAX_RECORDS, "input-limit", "too many artifact paths")
            raw, signature = self._read(name)
            identity = signature[:2]
            if identity not in self.cache:
                parsed, nodes = _json(raw, MAX_TOTAL_NODES - self.total_nodes)
                self.cache[identity] = (signature, raw, hashlib.sha256(raw).hexdigest(), parsed)
                self.total_bytes += len(raw)
                self.total_nodes += nodes
            self.paths[name] = self.cache[identity]
        _, _, actual, parsed = self.paths[name]
        if digest is not None:
            _require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
                     and digest == actual, "input-hash", "artifact hash differs from parsed bytes")
        return parsed

    def artifact(self, descriptor):
        _fields(descriptor, "path sha256", "artifact identity")
        _require(type(descriptor["sha256"]) is str
                 and re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is not None,
                 "input-hash", "lowercase 64-hex SHA-256 required")
        return self.load(descriptor["path"], descriptor["sha256"])

    def _check_root(self):
        try:
            descriptor, identities = _open_root(self.root)
        except OSError as error:
            raise ValueError("input-root: root unavailable at final recheck") from error
        try:
            _require(identities == self.identities, "input-root", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        rechecked = set()
        for name, (signature, _, digest, _) in self.paths.items():
            raw, current = self._read(name, rechecked)
            _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                     "input-changed", "input replaced during validation")
            rechecked.add(current[:2])
        self._check_root()


def _rules(value):
    _record(value, "gso-rules-v1", "namespace organism selection_rule selected_before_sets exploratory "
            "directional min_set_size max_set_size alpha overlap_limit collection_version upstream genes collection")
    namespace = _text(value["namespace"], "namespace")
    _require(namespace in {"gene_symbol", "ensembl_gene_id"}, "identifier-namespace", "unsupported namespace")
    for key in ("organism", "selection_rule", "collection_version"):
        _text(value[key], key)
    for key in ("selected_before_sets", "exploratory", "directional"):
        _boolean(value[key], key)
    _require(value["selected_before_sets"] or value["exploratory"],
             "post-selection", "selection after seeing sets requires an exploratory label")
    minimum = _number(value["min_set_size"], "min_set_size", 1, MAX_GENES, True)
    _number(value["max_set_size"], "max_set_size", minimum, MAX_GENES, True)
    _number(value["alpha"], "alpha", 0, 1)
    _number(value["overlap_limit"], "overlap_limit", 0, 1)


def _identifiers(value, rules, label, empty=False, code="duplicate-identifier"):
    _names(value, label, MAX_GENES, empty, code)
    for gene in value:
        if rules["namespace"] == "ensembl_gene_id":
            valid = re.fullmatch(r"ENS[A-Z]*G[0-9]+(?:\.[0-9]+)?", gene)
        else:
            valid = (re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", gene)
                     and not re.fullmatch(r"ENS[A-Z]*G[0-9]+(?:\.[0-9]+)?", gene))
        _require(bool(valid), "identifier-namespace", f"{label} identifier differs from frozen namespace")
    return set(value)


def _identity(value, rules):
    for key in ("namespace", "organism"):
        _text(value[key], key)
        _require(value[key] == rules[key], "identifier-namespace", "mixed namespace or organism")


def hypergeometric_upper_tail(population, set_size, list_size, overlap):
    """One-sided Fisher/hypergeometric tail, with one final float conversion."""
    n = _number(population, "population", 1, MAX_GENES, True)
    k = _number(set_size, "set_size", 1, n, True)
    draws = _number(list_size, "list_size", 1, n - 1, True)
    observed = _number(overlap, "overlap", max(0, draws - (n - k)), min(k, draws), True)
    _require(min(k, draws) - observed + 1 <= MAX_TAIL_TERMS,
             "input-limit", "hypergeometric tail term limit exceeded")
    numerator = sum(math.comb(k, x) * math.comb(n - k, draws - x)
                    for x in range(observed, min(k, draws) + 1))
    return float(Fraction(numerator, math.comb(n, draws)))


def benjamini_hochberg(values):
    """Adjust the complete tested family, retaining its original order."""
    _items(values, "tested p-values", MAX_TESTS, empty=True)
    for value in values:
        _number(value, "p-value", 0, 1)
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [1.0] * len(values)
    ceiling = 1.0
    for rank in range(len(order), 0, -1):
        index = order[rank - 1]
        ceiling = min(ceiling, values[index] * len(values) / rank)
        adjusted[index] = ceiling
    return adjusted


def reference_computation(rules, upstream, genes, collection):
    """Validate frozen identities, then compute the complete synthetic family."""
    _rules(rules)
    _record(upstream, "gso-upstream-v1", "namespace organism rows")
    _record(genes, "gso-list-v1", "namespace organism universe lists")
    _record(collection, "gso-collection-v1", "namespace organism version sets")
    for record in (upstream, genes, collection):
        _identity(record, rules)
    _text(collection["version"], "collection version")
    _require(collection["version"] == rules["collection_version"],
             "collection-version", "collection version differs from freeze")
    rows = _items(upstream["rows"], "tested upstream genes", MAX_GENES)
    tested = {}
    selected = {}
    for row in rows:
        _fields(row, "gene selected direction", "upstream gene")
        gene = _text(row["gene"], "gene")
        _require(gene not in tested, "duplicate-identifier", "upstream genes must be unique")
        direction = _text(row["direction"], "direction")
        _require(direction in {"up", "down", "none"}, "direction-lists", "invalid upstream direction")
        tested[gene] = direction
        if _boolean(row["selected"], "selected"):
            selected[gene] = direction
    _identifiers(list(tested), rules, "tested upstream genes")
    universe = _identifiers(genes["universe"], rules, "universe")
    _require(universe == set(tested), "tested-universe", "universe must equal exactly the tested upstream genes")
    lists = _items(genes["lists"], "gene lists", MAX_LISTS)
    directions = []
    admitted = []
    all_selected = set()
    for entry in lists:
        _fields(entry, "direction genes", "gene list")
        direction = _text(entry["direction"], "direction")
        members = _identifiers(entry["genes"], rules, "list genes", code="duplicate-list")
        _require(members <= universe, "outside-universe", "list genes must be inside the tested universe")
        _require(not members & all_selected, "duplicate-list", "a selected gene occurs in multiple lists")
        _require(len(members) < len(universe), "degenerate-list", "list cannot equal the universe")
        all_selected.update(members)
        directions.append(direction)
        admitted.append((direction, members))
    required = ["up", "down"] if rules["directional"] else ["combined"]
    _require(directions == required, "direction-lists", "frozen directional lists must be tested separately")
    if rules["directional"]:
        _require(all(selected.get(gene) == direction for direction, members in admitted for gene in members),
                 "direction-lists", "list membership ignores upstream direction")
    _require(all_selected == set(selected), "selection-rule", "list differs from upstream frozen selection flags")
    sets = _items(collection["sets"], "gene sets", MAX_SETS)
    _require(len(sets) * len(admitted) <= MAX_TESTS, "input-limit", "tested family exceeds limit")
    membership_count = 0
    for entry in sets:
        _fields(entry, "id genes", "gene set")
        _items(entry["genes"], "set genes", MAX_GENES, empty=True)
        membership_count += len(entry["genes"])
        _require(membership_count <= MAX_MEMBERSHIPS, "input-limit", "collection membership budget exceeded")
    intersected = {}
    for entry in sets:
        _fields(entry, "id genes", "gene set")
        name = _text(entry["id"], "set id")
        _require(bool(re.fullmatch(r"[A-Za-z0-9_-]+", name)), "invalid-record", "invalid set id")
        _require(name not in intersected, "duplicate-identifier", "set ids must be unique")
        intersected[name] = _identifiers(entry["genes"], rules, "set genes", empty=True) & universe
    output = []
    indices = []
    tail_terms = 0
    for direction, members in admitted:
        for name, set_members in intersected.items():
            size = len(set_members)
            overlap = len(members & set_members)
            tested_set = rules["min_set_size"] <= size <= rules["max_set_size"]
            p = None
            if tested_set:
                tail_terms += min(size, len(members)) - overlap + 1
                _require(tail_terms <= MAX_TAIL_TERMS, "input-limit", "aggregate tail term limit exceeded")
                p = hypergeometric_upper_tail(len(universe), size, len(members), overlap)
                indices.append(len(output))
            output.append({"id": direction + ":" + name, "size": size, "overlap": overlap,
                           "tested": tested_set, "p_value": p, "q_value": None,
                           "status": "non-significant" if tested_set else "untested"})
    for index, q in zip(indices, benjamini_hochberg([output[i]["p_value"] for i in indices])):
        output[index]["q_value"] = q
        if output[index]["overlap"] > 0 and q <= rules["alpha"]:
            output[index]["status"] = "significant"
    significant = [row["id"] for row in output if row["status"] == "significant"]
    _require(len(significant) * (len(significant) - 1) // 2 <= MAX_PAIRS,
             "input-limit", "pairwise redundancy budget exceeded")
    neighbours = {name: set() for name in significant}
    pairs = []
    for index, first in enumerate(significant):
        a = intersected[first.split(":", 1)[1]]
        for second in significant[index + 1:]:
            b = intersected[second.split(":", 1)[1]]
            jaccard = float(Fraction(len(a & b), len(a | b)))
            pairs.append({"first": first, "second": second, "jaccard": jaccard})
            if jaccard > rules["overlap_limit"]:
                neighbours[first].add(second)
                neighbours[second].add(first)
    findings = []
    seen = set()
    for name in significant:
        if name in seen:
            continue
        pending = [name]
        component = set()
        while pending:
            current = pending.pop()
            if current not in component:
                component.add(current)
                pending.extend(neighbours[current] - component)
        seen.update(component)
        findings.append(sorted(component))
    return {"namespace": rules["namespace"], "organism": rules["organism"],
            "universe_size": len(universe), "list_sizes": {direction: len(members) for direction, members in admitted},
            "collection_version": collection["version"], "rows": output, "jaccard": pairs, "findings": findings,
            "correction": "BH-all-tested-sets", "exploratory": rules["exploratory"]}


def _report(value, expected, rules_hash):
    _record(value, "gso-report-v1", "rules_sha256 namespace organism universe_size list_sizes collection_version "
            "rows jaccard findings correction exploratory")
    _require(value["rules_sha256"] == rules_hash, "rule-freeze", "report must cite frozen rules bytes")
    for key in ("namespace", "organism", "collection_version"):
        _text(value[key], key)
        _require(value[key] == expected[key], "reference-computation", "reported identity differs from frozen input")
    _number(value["universe_size"], "universe_size", 1, MAX_GENES, True)
    _fields(value["list_sizes"], " ".join(expected["list_sizes"]), "list_sizes")
    for size in value["list_sizes"].values():
        _number(size, "list size", 1, MAX_GENES, True)
    _require(value["universe_size"] == expected["universe_size"] and value["list_sizes"] == expected["list_sizes"],
             "reference-computation", "reported denominators differ from frozen input")
    _require(value["correction"] == "BH-all-tested-sets", "multiple-testing", "BH across all tested sets required")
    rows = _items(value["rows"], "reported sets", MAX_TESTS)
    _require(len(rows) == len(expected["rows"]), "tested-family", "every set must be reported once per list")
    for row, correct in zip(rows, expected["rows"]):
        _fields(row, "id size overlap tested p_value q_value status", "reported set")
        _text(row["id"], "reported set id")
        _text(row["status"], "set status")
        _number(row["size"], "size", 0, MAX_GENES, True)
        _number(row["overlap"], "overlap", 0, MAX_GENES, True)
        _boolean(row["tested"], "tested")
        if not correct["tested"]:
            _require(row["tested"] is False and row["status"] == "untested"
                     and row["p_value"] is None and row["q_value"] is None,
                     "set-size-bounds", "sets outside frozen size bounds must be untested")
        else:
            _require(row["tested"] is True, "tested-family", "all sets within bounds must be tested")
            _number(row["p_value"], "p_value", 0, 1)
            _number(row["q_value"], "q_value", 0, 1)
        _require(correct["overlap"] > 0 or row["status"] != "significant",
                 "empty-overlap", "empty overlap cannot be enriched")
        _require(row["q_value"] == correct["q_value"] and row["status"] == correct["status"],
                 "multiple-testing", "raw p-values cannot replace full-family BH decisions")
        _require(row == correct, "reference-computation", "reported counts or exact upper tail differ")
    _items(value["jaccard"], "Jaccard pairs", MAX_PAIRS, empty=True)
    _items(value["findings"], "findings", MAX_TESTS, empty=True)
    for pair in value["jaccard"]:
        _fields(pair, "first second jaccard", "Jaccard pair")
        _text(pair["first"], "first set")
        _text(pair["second"], "second set")
        _number(pair["jaccard"], "jaccard", 0, 1)
    for finding in value["findings"]:
        _names(finding, "finding members", MAX_TESTS)
    _require(value["jaccard"] == expected["jaccard"] and value["findings"] == expected["findings"],
             "redundant-findings", "overlapping significant sets are one finding, never independent confirmations")
    _require(_boolean(value["exploratory"], "exploratory") == expected["exploratory"],
             "post-selection", "report must preserve exploratory status")


def _claims(claims, records):
    _items(claims, "claims", MAX_CLAIMS, empty=True)
    ids = set()
    for claim in claims:
        _fields(claim, "id kind text status evidence", "pack-local claim")
        name = _text(claim["id"], "claim id")
        status = _text(claim["status"], "claim status")
        kind = _text(claim["kind"], "claim kind")
        text = _text(claim["text"], "claim text")
        _require(name not in ids, "invalid-record", "duplicate claim id")
        ids.add(name)
        _require(status in STATUSES, "invalid-record", "unknown claim status")
        _require(not OVERREACH.search(text) and kind in {"descriptive", "associational"},
                 "claim-overreach", "output states statistical over-representation only")
        support = _names(claim["evidence"], "claim evidence", MAX_RECORDS, empty=True)
        _require(all(name in records for name in support), "evidence-unavailable", "cited evidence record absent")
        cited = [records[name] for name in support]
        unavailable = not cited or any(r["kind"] == "unavailable" or r["result"] == "unavailable" for r in cited)
        _require(not unavailable or status == "unavailable", "evidence-unavailable", "unavailable evidence requires unavailable claim")
        _require(status != "unavailable" or not ASSERTION.search(text),
                 "unavailable-positive", "unavailable claim cannot assert positive evidence")
        if status in POSITIVE:
            _require(not any(NON_EVIDENCE.search(r["kind"]) or NON_EVIDENCE.search(r["result"]) for r in cited),
                     "non-evidence", "review approval or computed agreement cannot support positive claims")
        _require(status != "replicated", "replication", "this single synthetic study cannot establish replication")


def validate_gene_set_overrepresentation_pack(path):
    """Return a read-only result, or a labelled ValueError; never attest review."""
    _require(isinstance(path, (str, Path)), "input-path", "bundle must be a path")
    _text(str(path), "bundle path")
    entry = Path(os.path.abspath(path))
    bundle = _Bundle(entry.parent)
    try:
        pack = bundle.load(entry.name)
        _record(pack, "gso-pack-v1", "stages frozen_rules_sha256 rules report evidence claims")
        _require(pack["stages"] == list(STAGES), "stage-order", "five ordered stages required")
        rules = bundle.artifact(pack["rules"])
        _require(pack["frozen_rules_sha256"] == pack["rules"]["sha256"],
                 "rule-freeze", "rules hash must be frozen before reading the collection")
        _rules(rules)
        upstream = bundle.artifact(rules["upstream"])
        genes = bundle.artifact(rules["genes"])
        collection = bundle.artifact(rules["collection"])
        computation = reference_computation(rules, upstream, genes, collection)
        report = bundle.artifact(pack["report"])
        _report(report, computation, pack["rules"]["sha256"])
        own_paths = set(bundle.paths)
        own_hashes = {value[2] for value in bundle.paths.values()}
        evidence_files = _items(pack["evidence"], "evidence artifacts", MAX_RECORDS, empty=True)
        for identity in evidence_files:
            _fields(identity, "path sha256", "evidence artifact identity")
            _relative(identity["path"])
            _text(identity["sha256"], "evidence artifact hash")
            own_paths.add(identity["path"])
            own_hashes.add(identity["sha256"])
        records = {}
        for identity in evidence_files:
            evidence = bundle.artifact(identity)
            _record(evidence, "gso-evidence-v1", "records")
            entries = _items(evidence["records"], "evidence records", MAX_RECORDS)
            _require(len(records) + len(entries) <= MAX_RECORDS, "input-limit", "too many evidence records")
            for record in entries:
                _fields(record, "id kind result origin source", "evidence record")
                for key in ("id", "kind", "result", "origin"):
                    _text(record[key], key)
                _require(record["id"] not in records, "invalid-record", "duplicate evidence id")
                _require(record["origin"] in {"study", "external", "independent", "preregistered"},
                         "invalid-record", "unknown evidence origin")
                bundle.artifact(record["source"])
                if record["origin"] != "study":
                    _require(record["source"]["path"] not in own_paths
                             and record["source"]["sha256"] not in own_hashes,
                             "external-alias", "external labels cannot alias this study's inputs or outputs")
                records[record["id"]] = record
        _claims(pack["claims"], records)
        bundle.finish()
        return {"schema": "gso-result-v1", "fixture": "synthetic fixture", "stages": list(STAGES),
                "status": "statistical-overrepresentation-only", "review": "unavailable",
                "rules_sha256": pack["rules"]["sha256"], "computation": computation,
                "claims": pack["claims"],
                "input_identities": [{"path": name, "sha256": value[2]} for name, value in bundle.paths.items()]}
    finally:
        bundle.close()
