"""Offline, read-only dose-response fixture validation and reference computation.

All records are pack-local. Hashes establish identity, not experimental truth or
preregistration time. The reference fitter is deliberately limited to monotone
four-parameter curves and biological-block percentile bootstrap intervals.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import stat
from datetime import datetime
from pathlib import Path, PurePosixPath
from statistics import mean, stdev


STAGES = ("01-assay", "02-qc", "03-fit", "04-uncertainty", "05-review-handoff")
MAX_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_TOTAL_NODES = 4000000
PARAMETERS = ("bottom", "top", "potency", "hill")
POSITIVE = {"supported", "replicated", "suggestive"}
UNAVAILABLE_POSITIVE_WORDING = r"\b(?:supported|replicated|suggestive|significan\w*|potency\s+estimate)\b"
FORBIDDEN_WORDING = (
    r"\b(caus\w*|mechanis\w*|therap\w*|clinical\w*|efficac\w*|safety|safe|"
    r"treat\w*|cure\w*|prevent\w*|recommend\w*|patient\w*|prescri\w*|"
    r"effective\w*|in[ -]vivo|bind\w*|affinit(?:y|ies)|"
    r"inhibit\w*|activat\w*)\b"
)


def _require(condition, code, message):
    if not condition:
        raise ValueError(f"{code}: {message}")


def _object(value, label):
    _require(type(value) is dict, "invalid-record", f"{label} must be an object")
    return value


def _list(value, label, minimum=0, maximum=100000):
    _require(type(value) is list and minimum <= len(value) <= maximum,
             "invalid-record", f"{label} must be a list of length {minimum}..{maximum}")
    return value


def _text(value, label):
    _require(type(value) is str and bool(value.strip()), "invalid-record", f"{label} must be text")
    return value


def _number(value, label, low=-1e100, high=1e100):
    _require(type(value) in (int, float), "invalid-record", f"{label} must be numeric")
    try:
        valid = math.isfinite(value) and low <= value <= high
    except OverflowError:
        valid = False
    _require(valid, "invalid-record", f"{label} must be finite in [{low}, {high}]")
    return float(value)


def _integer(value, label, low, high):
    _require(type(value) is int and low <= value <= high,
             "invalid-record", f"{label} must be an integer in [{low}, {high}]")
    return value


def _boolean(value, label):
    _require(type(value) is bool, "invalid-record", f"{label} must be boolean")
    return value


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "invalid-json", f"duplicate key {key}")
        result[key] = value
    return result


def _constant(value):
    raise ValueError(f"invalid-json: non-finite constant {value}")


def _json_nodes(raw):
    # Upper bound before parsing: root, commas, and each non-empty container's first value.
    return 1 + raw.count(b",") + sum(1 for _ in re.finditer(rb"[\[{](?=\s*[^\s\]}])", raw))


def _parse(raw):
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid-json: malformed, duplicate, non-finite or deeply nested JSON") from error
    # Check even unused values; JSON's float parser can overflow 1e999 to inf.
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        _require(depth <= 64, "invalid-json", "nesting exceeds 64")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) in (int, float):
            _number(item, "JSON number")
    return _object(value, "JSON root")


def _relative(value):
    value = _text(value, "artifact path")
    relative = PurePosixPath(value)
    _require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in value
             and relative.parts and relative.as_posix() == value and ":" not in value
             and all(ord(character) >= 32 and ord(character) != 127 for character in value),
             "invalid-path", "artifact paths must be canonical bundle-relative paths")
    return relative.parts


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
            _require(stat.S_ISDIR(before.st_mode), "unsafe-input", "root ancestors must be real directories")
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


def _safe_bytes(path, *, bundle=None, checked=None):
    absolute = Path(os.path.abspath(path))
    root = absolute.parent if bundle is None else bundle.root
    relative = absolute.relative_to(root)
    directory = _open_root(root)[0] if bundle is None else os.dup(bundle.descriptor)
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    try:
        for part in relative.parts[:-1]:
            before = os.lstat(part, dir_fd=directory)
            _require(stat.S_ISDIR(before.st_mode), "unsafe-input", "parent must be a real directory")
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
        info = os.lstat(relative.name, dir_fd=directory)
        _require(stat.S_ISREG(info.st_mode), "unsafe-input", "input must be a regular non-symlink file")
        descriptor = os.open(relative.name, flags, dir_fd=directory)
        try:
            before = os.fstat(descriptor)
            _require(stat.S_ISREG(before.st_mode), "unsafe-input", "opened input must be regular")
            _require(before.st_size <= MAX_BYTES, "input-too-large", "input exceeds 64 MiB")
            signature = _signature(before)
            _require(_signature(info) == signature, "input-changed", "input changed during open")
            identity = signature[:2]
            cached = bundle.artifacts.get(identity) if bundle is not None else None
            if cached is not None:
                _require(signature == cached[2], "input-changed", "cached input changed")
                if checked is None or identity in checked:
                    return None, signature
            limit = MAX_BYTES
            if bundle is not None and checked is None:
                limit = min(limit, MAX_TOTAL_BYTES - bundle.bytes_read)
                _require(before.st_size <= limit, "input-limit", "total input byte budget exceeded")
            chunks, remaining = [], min(limit, before.st_size) + 1
            while remaining:
                chunk = os.read(descriptor, min(remaining, 1024 * 1024))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(descriptor)
            _require(len(raw) <= MAX_BYTES, "input-too-large", "input grew beyond 64 MiB")
            _require(signature == _signature(after) and len(raw) == after.st_size,
                     "input-changed", "input changed during read")
            if bundle is not None and checked is None:
                bundle.bytes_read += len(raw)
            return raw, signature
        finally:
            os.close(descriptor)
    finally:
        os.close(directory)


class _Bundle:
    def __init__(self, path):
        self.path = Path(os.path.abspath(path))
        self.root = self.path.parent
        self.records = {}
        self.artifacts = {}
        self.bytes_read = 0
        self.nodes_read = 0
        self.descriptor, self.root_identities = _open_root(self.root)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        if self.descriptor is not None:
            os.close(self.descriptor)
            self.descriptor = None

    def read(self, path):
        if path not in self.records:
            raw, signature = _safe_bytes(path, bundle=self)
            identity = signature[:2]
            if raw is not None:
                nodes = _json_nodes(raw)
                _require(nodes <= MAX_TOTAL_NODES - self.nodes_read,
                         "input-limit", "total JSON value budget exceeded")
                self.artifacts[identity] = (_parse(raw), hashlib.sha256(raw).hexdigest(), signature)
                self.nodes_read += nodes
            self.records[path] = self.artifacts[identity]
        return self.records[path]

    def artifact(self, identity, schema=None):
        identity = _object(identity, "artifact identity")
        parts = _relative(identity.get("path"))
        digest = identity.get("sha256")
        _require(type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest) is not None,
                 "invalid-record", "sha256 must be 64 lowercase hex characters")
        record, actual, _ = self.read(self.root.joinpath(*parts))
        _require(actual == digest, "artifact-hash-mismatch", identity["path"])
        if schema:
            _require(record.get("schema") == schema, "invalid-record", f"expected {schema}")
        return record

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.root_identities, "input-changed", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        checked = set()
        for path, (_, digest, signature) in self.records.items():
            raw, current = _safe_bytes(path, bundle=self, checked=checked)
            _require(signature == current and (raw is None or hashlib.sha256(raw).hexdigest() == digest),
                     "input-changed", "input was replaced during validation")
            checked.add(current[:2])
        self._check_root()


def _constraints(value):
    value = _object(value, "constraints")
    _require(set(value) == set(PARAMETERS), "invalid-record", "four parameter bounds required")
    bounds = []
    for name in PARAMETERS:
        pair = _list(value[name], name, 2, 2)
        low, high = (_number(item, name, -1e6, 1e6) for item in pair)
        _require(low < high and (name not in ("potency", "hill") or low > 0),
                 "invalid-record", "bounds must increase; potency and Hill slope must be positive")
        bounds.append((math.log(low), math.log(high)) if name == "potency" else (low, high))
    _require(value["bottom"][1] < value["top"][0], "invalid-record", "plateau bounds must not cross")
    return bounds


def _prediction(x, p, direction):
    sign = 1 if direction == "increasing" else -1
    z = sign * p[3] * (math.log(x) - p[2])
    s = 1 / (1 + math.exp(-max(-700, min(700, z))))
    return p[0] + (p[1] - p[0]) * s, s, sign


def four_parameter_response(concentration, parameters, direction="increasing"):
    """Evaluate a positive-concentration monotone 4PL without claiming validity."""
    _require(direction in ("increasing", "decreasing"), "invalid-record", "unknown direction")
    p = _object(parameters, "parameters")
    values = [_number(p.get(name), name, -1e6, 1e6) for name in PARAMETERS]
    _require(values[0] < values[1] and values[2] > 0 and values[3] > 0,
             "degenerate-data", "ordered plateaus, positive potency and slope required")
    values[2] = math.log(values[2])
    x = _number(concentration, "concentration", 1e-100, 1e100)
    return _prediction(x, values, direction)[0]


def _solve(matrix, vector):
    a = [list(row) + [value] for row, value in zip(matrix, vector)]
    for col in range(4):
        pivot = max(range(col, 4), key=lambda row: abs(a[row][col]))
        if abs(a[pivot][col]) < 1e-18:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        divisor = a[col][col]
        a[col] = [value / divisor for value in a[col]]
        for row in range(4):
            if row != col:
                factor = a[row][col]
                a[row] = [left - factor * right for left, right in zip(a[row], a[col])]
    return [row[4] for row in a]


def fit_four_parameter(concentrations, responses, constraints, *, direction="increasing",
                       max_iterations=120, tolerance=1e-8):
    """Deterministic bounded Levenberg-Marquardt; callers must inspect status."""
    xs = [_number(x, "concentration", 1e-100, 1e100) for x in _list(concentrations, "concentrations", 4, 64)]
    ys = [_number(y, "response", -1e6, 1e6) for y in _list(responses, "responses", 4, 64)]
    _require(len(xs) == len(ys) and len(set(xs)) == len(xs), "degenerate-data", "distinct paired concentrations required")
    _require(max(ys) - min(ys) > 1e-12, "degenerate-data", "zero response variance")
    _require(direction in ("increasing", "decreasing"), "invalid-record", "unknown direction")
    _integer(max_iterations, "max_iterations", 1, 500)
    _number(tolerance, "tolerance", 1e-12, 1e-3)
    bounds = _constraints(constraints)
    midpoint = (min(ys) + max(ys)) / 2
    p = [min(ys), max(ys), math.log(xs[min(range(len(xs)), key=lambda i: abs(ys[i] - midpoint))]), 1.0]
    p = [max(low, min(high, value)) for value, (low, high) in zip(p, bounds)]
    loss = lambda values: sum((y - _prediction(x, values, direction)[0]) ** 2 for x, y in zip(xs, ys))
    current, damping, converged = loss(p), 1e-3, False
    for iteration in range(1, max_iterations + 1):
        matrix, vector = [[0.0] * 4 for _ in range(4)], [0.0] * 4
        for x, y in zip(xs, ys):
            predicted, s, sign = _prediction(x, p, direction)
            common = (p[1] - p[0]) * s * (1 - s) * sign
            jacobian = [1 - s, s, -common * p[3], common * (math.log(x) - p[2])]
            for j in range(4):
                vector[j] += jacobian[j] * (y - predicted)
                for k in range(4):
                    matrix[j][k] += jacobian[j] * jacobian[k]
        if max(map(abs, vector)) <= tolerance:
            converged = True
            break
        for j in range(4):
            matrix[j][j] += damping * max(matrix[j][j], 1e-6)
        delta = _solve(matrix, vector)
        if delta is None:
            break
        trial = [max(low, min(high, value + step)) for value, step, (low, high) in zip(p, delta, bounds)]
        updated = loss(trial)
        if updated < current:
            change = max(abs(new - old) for new, old in zip(trial, p))
            p, current, damping = trial, updated, max(1e-12, damping / 3)
            if change <= tolerance:
                converged = True
                break
        else:
            damping = min(1e12, damping * 10)
    boundary = any(min(abs(value - low), abs(value - high)) <= tolerance * 10
                   for value, (low, high) in zip(p, bounds))
    return {"parameters": dict(zip(PARAMETERS, (p[0], p[1], math.exp(p[2]), p[3]))),
            "converged": converged, "boundary": boundary, "iterations": iteration, "loss": current}


def _optimizer(value):
    value = _object(value, "optimizer")
    _require(value.get("method") == "bounded-lm-v1", "invalid-record", "unknown optimizer")
    return {"max_iterations": _integer(value.get("max_iterations"), "max_iterations", 1, 500),
            "tolerance": _number(value.get("tolerance"), "tolerance", 1e-12, 1e-3)}


def _bootstrap(value):
    value = _object(value, "bootstrap")
    _integer(value.get("seed"), "seed", 0, 2**32 - 1)
    _integer(value.get("resamples"), "resamples", 20, 200)
    _require(value.get("interval_level") == 0.95 and type(value.get("interval_level")) is float,
             "invalid-record", "reference bootstrap supports 95% intervals")
    _number(value.get("minimum_success_fraction"), "minimum_success_fraction", 0.8, 1)


def _assay(record):
    _boolean(record.get("fixture"), "fixture")
    _text(record.get("system"), "system")
    _text(record.get("endpoint"), "endpoint")
    _require(record.get("metric") in ("EC50", "IC50"), "invalid-record", "metric must be EC50 or IC50")
    direction = "increasing" if record["metric"] == "EC50" else "decreasing"
    _require(record.get("direction") == direction, "invalid-record", "metric/direction mismatch")
    _require(record.get("unit") in ("nM", "uM"), "unit-mismatch", "declare nM or uM")
    _require(record.get("normalisation") == "vehicle-positive-linear", "invalid-record", "unknown normalisation")
    concentrations = [_number(x, "concentration", 1e-9, 1e6)
                      for x in _list(record.get("concentrations"), "concentrations", 4, 64)]
    _require(concentrations == sorted(set(concentrations)), "invalid-record", "concentrations must be unique and ordered")
    for key, low, high in (("minimum_concentrations", 4, 64), ("minimum_biological_replicates", 2, 100),
                           ("minimum_technical_replicates", 1, 20), ("minimum_control_replicates", 2, 100)):
        _integer(record.get(key), key, low, high)
    _require(len(concentrations) >= record["minimum_concentrations"], "insufficient-concentrations", "series below declared minimum")
    _number(record.get("control_window_minimum"), "control_window_minimum", 1e-9, 1e6)
    _number(record.get("separation_threshold"), "separation_threshold", 0, 1)
    _number(record.get("plateau_fraction"), "plateau_fraction", 0.9, 0.999)
    _require(record.get("outlier_rule") in ("none", "exclude-flagged-before-fit"), "invalid-record", "unknown outlier rule")
    _require(record.get("model") == "4pl", "invalid-record", "model must be 4pl")
    _constraints(record.get("constraints"))
    _optimizer(record.get("optimizer"))
    _bootstrap(record.get("bootstrap"))
    identifiers = []
    for compound in _list(record.get("compounds"), "compounds", 1, 4):
        compound = _object(compound, "compound")
        identifiers.append(_text(compound.get("id"), "compound.id"))
        _text(compound.get("form"), "compound.form")
    _require(len(set(identifiers)) == len(identifiers), "invalid-record", "compound IDs must be unique")
    _require(record.get("outcomes_seen") is False, "outcome-dependent-freeze", "assay must be frozen before outcomes")
    _time(record.get("frozen_at"))
    return identifiers


def _time(value):
    try:
        stamp = datetime.fromisoformat(_text(value, "timestamp").replace("Z", "+00:00"))
        _require(stamp.utcoffset() is not None, "invalid-record", "timestamp requires timezone")
        return stamp
    except ValueError as error:
        raise ValueError("invalid-record: timezone-aware ISO timestamp required") from error


def _normalise_unit(well, assay):
    unit = well.get("unit")
    _require(unit in ("nM", "uM"), "unit-mismatch", "well unit must be nM or uM")
    x = _number(well.get("concentration"), "well concentration", 1e-12, 1e9)
    if unit != assay["unit"]:
        conversion = _object(well.get("conversion"), "conversion") if well.get("conversion") is not None else {}
        factor = 1000 if unit == "uM" else 0.001
        _require(conversion.get("from") == unit and conversion.get("to") == assay["unit"]
                 and type(conversion.get("factor")) in (int, float) and conversion["factor"] == factor
                 and type(conversion.get("reason")) is str and bool(conversion["reason"].strip()),
                 "unit-mismatch", "unit conversion must record from, to, factor and reason")
        x *= factor
    _require(x in assay["concentrations"], "unit-mismatch", "converted concentration absent from frozen series")
    return x


def _data(assay, plate, compounds, outlier_rule):
    _boolean(plate.get("fixture"), "fixture")
    controls = _object(plate.get("controls"), "controls")
    measured = {}
    failures = []
    for name in ("vehicle", "positive"):
        values = [_number(x, "control", -1e6, 1e6) for x in _list(controls.get(name, []), name, 0, 100)]
        if len(values) < assay["minimum_control_replicates"]:
            failures.append("missing-control")
        measured[name] = values
    vehicle = mean(measured["vehicle"]) if measured["vehicle"] else None
    positive = mean(measured["positive"]) if measured["positive"] else None
    window, separation = None, None
    if not failures:
        window = abs(positive - vehicle)
        separation = 1 - 3 * (stdev(measured["vehicle"]) + stdev(measured["positive"])) / window if window else None
        if window < assay["control_window_minimum"] or separation is None or separation < assay["separation_threshold"]:
            failures.append("controls-failed")
    groups = {compound: {} for compound in compounds}
    identities, excluded, owners = set(), [], {}
    for well in _list(plate.get("wells"), "wells", 1, 50000):
        well = _object(well, "well")
        identifier = _text(well.get("id"), "well.id")
        _require(identifier not in identities, "invalid-record", "duplicate well ID")
        identities.add(identifier)
        compound = well.get("compound")
        _require(type(compound) is str and compound in groups, "invalid-record", "unknown compound")
        x = _normalise_unit(well, assay)
        raw = _number(well.get("response"), "well.response", -1e6, 1e6)
        biological = _text(well.get("biological_id"), "biological_id")
        technical = _text(well.get("technical_id"), "technical_id")
        _require(well.get("replicate_type") == "technical", "pseudoreplication", "wells are technical repeats nested in biological IDs")
        independent = _text(well.get("independent_unit"), "independent_unit")
        owner_key = (compound, independent)
        _require(owner_key not in owners or owners[owner_key] == biological,
                 "pseudoreplication", "one independent unit cannot be counted as multiple biological replicates")
        owners[owner_key] = biological
        flagged = _boolean(well.get("excluded"), "excluded")
        if flagged:
            _require(outlier_rule == "exclude-flagged-before-fit" and type(well.get("reason")) is str
                     and bool(well["reason"].strip()), "outlier-rule", "exclusion requires frozen rule and recorded reason")
            excluded.append({"id": identifier, "reason": well["reason"]})
            continue
        bio = groups[compound].setdefault(biological, {"unit": independent, "doses": {}})
        _require(bio["unit"] == independent, "pseudoreplication", "biological ID changes independent unit")
        repeats = bio["doses"].setdefault(x, {})
        _require(technical not in repeats, "invalid-record", "duplicate technical replicate at concentration")
        repeats[technical] = raw
    curves = {}
    for compound, bios in groups.items():
        _require(len(bios) >= assay["minimum_biological_replicates"], "insufficient-replicates", "too few independent biological units")
        curves[compound] = []
        for bio in bios.values():
            _require(len(bio["doses"]) >= assay["minimum_concentrations"]
                     and set(bio["doses"]) == set(assay["concentrations"]),
                     "insufficient-concentrations", "every biological curve must retain the frozen series")
            curve = []
            for x in assay["concentrations"]:
                values = list(bio["doses"][x].values())
                _require(len(values) >= assay["minimum_technical_replicates"], "insufficient-replicates", "too few technical repeats")
                if not failures:
                    raw = mean(values)
                    curve.append((raw - vehicle) / (positive - vehicle) if assay["direction"] == "increasing"
                                 else (raw - positive) / (vehicle - positive))
            curves[compound].append(curve)
    qc = {"schema": "dose-response-qc-v1", "window": window, "separation": separation,
          "status": "failed" if failures else "passed", "failures": failures, "exclusions": excluded}
    return curves, qc


def _interval(values):
    ordered = sorted(values)
    def quantile(q):
        position = q * (len(ordered) - 1)
        left = int(position)
        right = min(left + 1, len(ordered) - 1)
        return ordered[left] + (ordered[right] - ordered[left]) * (position - left)
    return [quantile(0.025), quantile(0.975)]


def _computation(assay, curves, used):
    options = _optimizer(used["optimizer"])
    fits, intervals = [], []
    bootstrap = assay["bootstrap"]
    for compound, blocks in curves.items():
        ys = [mean(column) for column in zip(*blocks)]
        fit = fit_four_parameter(assay["concentrations"], ys, used["constraints"], direction=assay["direction"], **options)
        fits.append({"compound": compound, **fit})
        _require(fit["converged"] and not fit["boundary"], "unreportable-fit", "reference fit did not converge or hit a constraint")
        _require(any(max(column) - min(column) > 1e-12 for column in zip(*blocks)),
                 "degenerate-data", "biological curves have zero variance")
        rng, draws = random.Random(bootstrap["seed"]), []
        for _ in range(bootstrap["resamples"]):
            sample = [blocks[rng.randrange(len(blocks))] for _ in blocks]
            responses = [mean(column) for column in zip(*sample)]
            try:
                result = fit_four_parameter(assay["concentrations"], responses, used["constraints"], direction=assay["direction"], **options)
            except ValueError as error:
                if not str(error).startswith("degenerate-data: zero response variance"):
                    raise
                continue  # a constant resample is an unsuccessful draw, counted against the success fraction
            if result["converged"] and not result["boundary"]:
                draws.append(result["parameters"])
        _require(len(draws) >= math.ceil(bootstrap["resamples"] * bootstrap["minimum_success_fraction"]),
                 "uncertainty-failed", "insufficient converged biological bootstrap draws")
        intervals.append({"compound": compound, "potency": _interval([draw["potency"] for draw in draws]),
                          "hill": _interval([draw["hill"] for draw in draws]), "successful_resamples": len(draws)})
    return fits, intervals


def reference_computation(assay, plate):
    """Compute offline QC, fit and uncertainty; no I/O or implicit data repair."""
    assay, plate = _object(assay, "assay"), _object(plate, "plate")
    compounds = _assay(assay)
    curves, qc = _data(assay, plate, compounds, assay["outlier_rule"])
    _require(not qc["failures"], qc["failures"][0] if qc["failures"] else "controls-failed", "controls cannot support potency")
    used = {key: assay[key] for key in ("model", "constraints", "outlier_rule", "optimizer")}
    fits, intervals = _computation(assay, curves, used)
    return {"qc": qc, "fits": fits, "intervals": intervals}


def _matching(actual, expected, code):
    if type(expected) is dict:
        _require(type(actual) is dict and set(actual) == set(expected), code, "record fields differ from reference")
        for key, value in expected.items():
            _matching(actual[key], value, code)
    elif type(expected) is list:
        _require(type(actual) is list and len(actual) == len(expected), code, "record list differs from reference")
        for left, right in zip(actual, expected):
            _matching(left, right, code)
    elif type(expected) in (int, float):
        if type(expected) is int:
            _require(type(actual) is int, "invalid-record", "record count must be an integer")
        value = _number(actual, "record number")
        _require(math.isclose(value, expected, rel_tol=1e-7, abs_tol=1e-9), code, "record differs from deterministic reference")
    else:
        _require(type(actual) is type(expected) and actual == expected, code, "record differs from deterministic reference")


def _claims(bundle, record, fits, intervals, pack):
    by_fit = {item["compound"]: item for item in fits}
    by_interval = {item["compound"]: item for item in intervals}
    identifiers = set()
    for claim in _list(record.get("claims"), "claims", 1, 100):
        claim = _object(claim, "claim")
        identifier = _text(claim.get("id"), "claim.id")
        _require(identifier not in identifiers, "invalid-record", "duplicate claim ID")
        identifiers.add(identifier)
        status = _text(claim.get("status"), "claim.status")
        _require(status in ("supported", "replicated", "suggestive", "unavailable", "unsupported", "conflicting", "withdrawn"),
                 "invalid-record", "unknown claim status")
        text = _text(claim.get("text"), "claim.text")
        _require(claim.get("kind") in ("descriptive", "associational"), "claim-boundary", "association is never causality")
        support = _list(claim.get("support"), "claim.support", 0, 100)
        _require(bool(support) or status == "unavailable", "claim-boundary", "missing support requires unavailable status")
        if status in POSITIVE:
            _require(re.search(FORBIDDEN_WORDING, text, re.I) is None, "claim-boundary", "text exceeds in-vitro statistical evidence")
        if status == "unavailable":
            _require(re.search(FORBIDDEN_WORDING + "|" + UNAVAILABLE_POSITIVE_WORDING, text, re.I) is None,
                     "claim-boundary", "unavailable claim cannot assert positive evidence")
        for identity in support:
            evidence = bundle.artifact(identity)
            _require(status == "unavailable" or "unavailable" not in (evidence.get("kind"), evidence.get("result")),
                     "unavailable-evidence", "unavailable evidence requires an unavailable claim")
            if status in POSITIVE:
                declared = str(evidence.get("kind", "")) + " " + str(evidence.get("result", ""))
                _require(re.search(r"comput|numerical|simulat|review|approv", declared, re.I) is None
                         and evidence.get("kind") == "assay-measurement" and evidence.get("result") == "observed",
                         "computed-claim", "computed agreement and review approval are never empirical support")
            if claim.get("origin") in ("external", "independent", "preregistered"):
                own = [pack[name] for name in ("assay", "plate", "qc", "fit", "uncertainty", "claims", "handoff")]
                _require(all(identity["path"] != item["path"] and identity["sha256"] != item["sha256"] for item in own),
                         "own-evidence", "origin label conflicts with this run's output identities")
        _require(claim.get("origin") in ("this-fixture", "this-study", "external", "independent", "preregistered"), "invalid-record", "origin must be explicit")
        _require(status != "replicated", "claim-boundary", "one plate cannot establish independent replication")
    for comparison in _list(record.get("comparisons"), "comparisons", 0, 6):
        comparison = _object(comparison, "comparison")
        left, right = comparison.get("left"), comparison.get("right")
        _require(type(left) is str and type(right) is str and left != right and left in by_fit and right in by_fit,
                 "invalid-record", "comparison must cite two fitted compounds")
        conclusion = comparison.get("conclusion")
        _require(conclusion in ("unranked", "left-more-potent", "right-more-potent"), "invalid-record", "unknown comparison")
        if conclusion != "unranked":
            _require(comparison.get("basis") == "nonoverlapping-95-percent-intervals", "point-ranking", "point estimates cannot rank compounds")
            a, b = by_interval[left]["potency"], by_interval[right]["potency"]
            _require(a[1] < b[0] if conclusion == "left-more-potent" else b[1] < a[0],
                     "overlapping-intervals", "overlapping or touching intervals cannot establish ordering")
    return sorted(identifiers)


def _validate(bundle):
    pack = bundle.read(bundle.path)[0]
    _require(pack.get("schema") == "dose-response-pack-v1", "invalid-record", "dose-response-pack-v1 required")
    _boolean(pack.get("fixture"), "fixture")
    _require(pack.get("stages") == list(STAGES), "stage-order", "five ordered stage IDs required")
    names = ("assay", "plate", "qc", "fit", "uncertainty", "claims", "handoff")
    records = {name: bundle.artifact(pack.get(name), f"dose-response-{name}-v1") for name in names}
    _require(len({pack[name]["path"] for name in names}) == len(names), "invalid-path", "stage artifact paths must be distinct")
    assay, plate, saved_qc, fit, uncertainty, claims, handoff = (records[name] for name in names)
    compounds = _assay(assay)
    _require(assay["fixture"] is pack["fixture"] and plate.get("fixture") is pack["fixture"],
             "invalid-record", "pack, assay and plate fixture labels must agree")
    _require(plate.get("kind") == "assay-measurement" and plate.get("result") == "observed", "invalid-record", "plate must declare measurement origin")
    _require(fit.get("kind") == "computed" and fit.get("result") == "numerical", "invalid-record", "fit is a computed numerical record")
    _require(fit.get("assay") == pack["assay"] and fit.get("plate") == pack["plate"], "artifact-hash-mismatch", "fit must bind frozen inputs")
    _bootstrap(uncertainty.get("bootstrap"))
    _require(uncertainty.get("fit") == pack["fit"] and uncertainty.get("bootstrap") == assay["bootstrap"],
             "artifact-hash-mismatch", "uncertainty must bind fit and frozen bootstrap")
    used = _object(fit.get("used"), "used")
    changed = any(used.get(key) != assay[key] for key in ("model", "constraints", "outlier_rule", "optimizer"))
    _require(fit.get("label") in ("prespecified", "exploratory"), "invalid-record", "fit label required")
    _require(not changed or fit["label"] == "exploratory", "unlabelled-deviation", "changed method requires exploratory label")
    _require(used.get("model") == "4pl", "invalid-record", "reference supports only 4pl")
    _constraints(used.get("constraints"))
    _optimizer(used.get("optimizer"))
    _require(used.get("outlier_rule") in ("none", "exclude-flagged-before-fit"), "invalid-record", "unknown used outlier rule")
    _require(_time(assay["frozen_at"]) <= _time(plate.get("observed_at")) <= _time(fit.get("fitted_at")) <= _time(handoff.get("created_at")),
             "stage-order", "assay freeze, observations, fit and handoff must be ordered")
    curves, qc = _data(assay, plate, compounds, used["outlier_rule"])
    _matching(saved_qc, qc, "qc-mismatch")
    _require(fit.get("status") in ("reported", "unavailable"), "invalid-record", "fit status required")
    results = _list(fit.get("fits"), "fits", 0, 4)
    saved_intervals = _list(uncertainty.get("intervals"), "intervals", 0, 4)
    if fit["status"] == "reported":
        _require(not qc["failures"], qc["failures"][0] if qc["failures"] else "controls-failed", "failed controls cannot support potency")
        _require(len(results) == len(compounds), "invalid-record", "every compound requires a result")
        for item in results:
            item = _object(item, "fit result")
            _require(item.get("converged") is True and item.get("boundary") is False,
                     "unreportable-fit", "nonconverged or boundary-hitting fits cannot be reported")
            parameters = _object(item.get("parameters"), "parameters")
            potency = _number(parameters.get("potency"), "potency", 1e-100, 1e100)
            _require(min(assay["concentrations"]) <= potency <= max(assay["concentrations"]),
                     "potency-extrapolation", "potency lies outside tested concentrations")
        full = _boolean(fit.get("full_efficacy"), "full_efficacy")
        if full:
            x = max(assay["concentrations"]) if assay["direction"] == "increasing" else min(assay["concentrations"])
            for item in results:
                p = item["parameters"]
                values = [_number(p.get(name), name) for name in PARAMETERS]
                _require(values[2] > 0 and values[3] > 0, "invalid-record", "positive potency and slope required")
                values[2] = math.log(values[2])
                _require(_prediction(x, values, assay["direction"])[1] >= assay["plateau_fraction"]
                         and values[1] >= assay["plateau_fraction"],
                         "plateau-not-reached", "upper plateau/full assay response not established")
        expected_fits, expected_intervals = _computation(assay, curves, used)
        _matching(results, expected_fits, "fit-mismatch")
        _require(uncertainty.get("status") == "reported", "uncertainty-failed", "reported potency needs intervals")
        _matching(saved_intervals, expected_intervals, "uncertainty-mismatch")
    else:
        _require(not results and not saved_intervals and uncertainty.get("status") == "unavailable"
                 and fit.get("full_efficacy") is False, "unreportable-fit", "unavailable fit must not carry results")
        _text(fit.get("reason"), "unavailable reason")
        _require(all(_text(_object(item, "claim").get("status"), "claim.status") not in POSITIVE
                     for item in _list(claims.get("claims"), "claims")),
                 "claim-boundary", "unavailable fit cannot support positive claims")
    claim_ids = _claims(bundle, claims, results, saved_intervals, pack)
    _require(handoff.get("status") == "ready-for-independent-review" and handoff.get("reviewed") is False,
             "self-review", "coordinator owns independent review and rigor classification")
    _require(handoff.get("inputs") == {name: pack[name] for name in names if name != "handoff"},
             "artifact-hash-mismatch", "handoff must bind every stage input")
    _require(handoff.get("claim_ids") == claim_ids, "invalid-record", "handoff must cover every claim")
    bundle.finish()
    return {"schema": "dose-response-validation-v1", "status": "ready-for-independent-review",
            "fixture": pack["fixture"], "stages": list(STAGES), "qc": qc, "fit_status": fit["status"],
            "label": fit["label"], "claim_ids": claim_ids, "reviewed": False,
            "evidence_boundary": ("In-vitro statistical evidence only; synthetic fixture, no physical or clinical validation."
                                  if pack["fixture"] else "In-vitro statistical evidence only; no physical or clinical validation.")}


def validate_dose_response_pack(path):
    """Validate a hash-bound offline bundle; emit labelled refusals and write nothing."""
    _require(isinstance(path, (str, Path)) and "\x00" not in str(path),
             "invalid-path", "input path must be text or Path without null characters")
    try:
        with _Bundle(Path(path)) as bundle:
            return _validate(bundle)
    except (OSError, OverflowError, RecursionError) as error:
        raise ValueError("unsafe-input: unavailable, unsafe, oversized or changed input") from error
