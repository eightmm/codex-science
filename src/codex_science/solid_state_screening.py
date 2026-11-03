"""Offline workflow-contract checks for a synthetic tight-binding chain.

The sine-mode Rayleigh quotients check an explicitly supplied toy Hamiltonian.
Neither their agreement with its spectrum nor this validator establishes
materials-property accuracy. This module never writes files or runs a solver.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any

from codex_science.units_runtime import convert_value

CONTRACT_SCHEMA = "solid-state-screening-contract-v1"
STAGE_SCHEMA = "solid-state-screening-stage-v1"
STAGES = (
    ("stage-1", "normalized.json"),
    ("stage-2", "analytic-control.json"),
    ("stage-3", "convergence.json"),
    ("stage-4", "ranking.json"),
    ("stage-5", "review-handoff.json"),
)
REFINEMENTS = [4, 8, 16, 32]
MAX_RECORD_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = (len(STAGES) + 1) * MAX_RECORD_BYTES


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise ValueError(f"{code}: {detail}")


def _number(value: Any) -> float:
    _require(type(value) in (int, float), "SS_NUMBER", "finite JSON number required")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("SS_NUMBER: finite JSON number required") from error
    _require(math.isfinite(result), "SS_NUMBER", "finite JSON number required")
    return result


def _same_number(actual: Any, expected: float) -> bool:
    return math.isclose(_number(actual), expected, rel_tol=1e-12, abs_tol=1e-14)


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    record = {}
    for name, value in items:
        _require(name not in record, "SS_SHAPE", f"duplicate JSON key: {name}")
        record[name] = value
    return record


def _signature(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _open_root(root):
    """Pin every ancestor so a transient pathname swap cannot redirect reads."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
    descriptor = os.open(root.anchor, flags)
    try:
        opened = os.fstat(descriptor)
        _require(stat.S_ISDIR(opened.st_mode), "SS_MISSING_RECORD", "root must be a directory")
        identities = [(opened.st_dev, opened.st_ino)]
        for part in root.parts[1:]:
            before = os.lstat(part, dir_fd=descriptor)
            _require(stat.S_ISDIR(before.st_mode), "SS_MISSING_RECORD", "root ancestors must be real directories")
            child = os.open(part, flags, dir_fd=descriptor)
            try:
                opened = os.fstat(child)
                _require(stat.S_ISDIR(opened.st_mode)
                         and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                         "SS_MISSING_RECORD", "root ancestor changed during pinning")
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
        self.snapshots = {}
        self.cache = {}
        self.total_bytes = 0
        self.fd, self.identities = _open_root(root)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        os.close(self.fd)

    def _read(self, relative, label, checked=None):
        opened_dirs = []
        try:
            directory = self.fd
            flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
            for part in relative.parts[:-1]:
                before = os.lstat(part, dir_fd=directory)
                _require(stat.S_ISDIR(before.st_mode), "SS_MISSING_RECORD", "artifact ancestors must be real directories")
                directory = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
                opened_dirs.append(directory)
                actual = os.fstat(directory)
                _require(stat.S_ISDIR(actual.st_mode)
                         and (before.st_dev, before.st_ino) == (actual.st_dev, actual.st_ino),
                         "SS_MISSING_RECORD", "artifact directory replaced")
            before = os.lstat(relative.name, dir_fd=directory)
            _require(stat.S_ISREG(before.st_mode), "SS_MISSING_RECORD", f"{label} must be a regular file")
            _require(before.st_size <= MAX_RECORD_BYTES, "SS_RECORD_SIZE", f"{label} exceeds 64 MiB")
            descriptor = os.open(relative.name, flags, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as stream:
                actual = os.fstat(stream.fileno())
                _require(stat.S_ISREG(actual.st_mode), "SS_MISSING_RECORD", "input must be a regular file")
                _require(before.st_size == actual.st_size, "SS_RECORD_SIZE", "input size changed during open")
                _require(_signature(before) == _signature(actual),
                         "SS_MISSING_RECORD", "input changed during open")
                signature = _signature(actual)
                identity = signature[:2]
                cached = self.cache.get(identity)
                if cached is not None:
                    _require(signature == cached[1], "SS_MISSING_RECORD", "cached input changed")
                    if checked is None or identity in checked:
                        return cached[0], signature
                limit = MAX_RECORD_BYTES if checked is not None else min(MAX_RECORD_BYTES, MAX_TOTAL_BYTES - self.total_bytes)
                _require(actual.st_size <= limit, "SS_RECORD_SIZE", "aggregate input byte budget exceeded")
                raw = stream.read(limit + 1)
                after = os.fstat(stream.fileno())
            _require(len(raw) <= limit, "SS_RECORD_SIZE", "input grew beyond its byte budget")
            _require(len(raw) == actual.st_size and _signature(actual) == _signature(after),
                     "SS_MISSING_RECORD", "input changed during bounded read")
            return raw, signature
        except OSError as error:
            raise ValueError(f"SS_MISSING_RECORD: {label}: unavailable or unsafe input") from error
        finally:
            for descriptor in reversed(opened_dirs):
                os.close(descriptor)

    def read(self, relative, label):
        name = relative.as_posix()
        if name not in self.snapshots:
            raw, signature = self._read(relative, label)
            identity = signature[:2]
            if identity not in self.cache:
                self.cache[identity] = (raw, signature, hashlib.sha256(raw).hexdigest())
                self.total_bytes += len(raw)
            self.snapshots[name] = self.cache[identity]
        return self.snapshots[name][0]

    def _check_root(self):
        descriptor, identities = _open_root(self.root)
        try:
            _require(identities == self.identities, "SS_MISSING_RECORD", "bundle root replaced")
        finally:
            os.close(descriptor)

    def finish(self):
        self._check_root()
        checked = set()
        for name, (_, signature, digest) in self.snapshots.items():
            raw, current = self._read(PurePosixPath(name), name, checked)
            _require(current == signature and hashlib.sha256(raw).hexdigest() == digest,
                     "SS_MISSING_RECORD", "input replaced during validation")
            checked.add(current[:2])
        self._check_root()


def _load_record(bundle: _Bundle, path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = bundle.read(PurePosixPath(path.name), path.name)
    try:
        record = json.loads(raw, object_pairs_hook=_pairs)
    except ValueError as error:
        raise ValueError(f"SS_SHAPE: {path.name}: invalid JSON screening record: {error}") from error
    _require(isinstance(record, dict), "SS_SHAPE", f"{path.name}: expected an object")
    return raw, record


def encode_record(record: dict[str, Any]) -> bytes:
    """Serialize a reference fixture reproducibly, including its terminal newline."""
    try:
        return (json.dumps(record, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise ValueError("SS_SHAPE: record is not finite JSON") from error


def chain_spectrum(sites: int, onsite: float, hopping: float) -> list[float]:
    """Evaluate H on sine modes, independently of the closed-form eigenvalues.

    The fixed offline envelope is 1..32 sites. Nonnegative hopping makes the
    first sine mode the lowest eigenvalue, including the degenerate zero limit.
    """
    _require(type(sites) is int and 1 <= sites <= 32, "SS_SITES", "sites must be an integer in 1..32")
    onsite, hopping = _number(onsite), _number(hopping)
    _require(hopping >= 0, "SS_MODEL", "hopping must be nonnegative")
    values = []
    for mode in range(1, sites + 1):
        vector = [math.sin(mode * math.pi * j / (sites + 1)) for j in range(1, sites + 1)]
        norm = math.fsum(v * v for v in vector)
        diagonal = onsite * norm
        bonds = -2 * hopping * math.fsum(a * b for a, b in zip(vector, vector[1:]))
        values.append((diagonal + bonds) / norm)
    _require(all(math.isfinite(v) for v in values), "SS_NUMBER", "spectrum overflow")
    return values


def _normalized(contract: dict[str, Any]) -> dict[str, Any]:
    _require(contract["schema"] == CONTRACT_SCHEMA and contract["synthetic"] is True,
             "SS_CONTRACT", "a labelled synthetic contract is required")
    _require(type(contract["seed"]) is int and contract["seed"] == 1729,
             "SS_CONTRACT", "reference fixture seed must be 1729 (no random sampling)")
    model = contract["model"]
    _require(model["name"] == "open-tight-binding-chain" and model["boundary"] == "open"
             and type(model["dimension"]) is int and model["dimension"] == 1,
             "SS_MODEL", "only the offline open one-dimensional chain is executable")
    _require(contract["observable"] == "lowest-energy", "SS_MODEL", "unknown observable")
    _require(contract["refinements"] == REFINEMENTS
             and all(type(n) is int for n in contract["refinements"]),
             "SS_CONVERGENCE_SERIES", "reference schedule must be [4, 8, 16, 32]")
    try:
        energy_unit = contract.get("energy_unit")
        length = model["lattice_spacing"]
        factor = convert_value(1.0, energy_unit, "eV")
        spacing = convert_value(_number(length["value"]), length.get("unit"), "nm")
        _require(spacing > 0, "SS_UNITS", "lattice spacing must be positive")
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        raise ValueError("SS_UNITS: missing or inconsistent energy/length units") from error
    thresholds = contract["thresholds"]
    _require(set(thresholds) == {"analytic_abs", "convergence_abs", "monotone_slack"},
             "SS_THRESHOLDS", "all three predeclared thresholds are required")
    for value in thresholds.values():
        _require(_number(value) >= 0, "SS_THRESHOLDS", "thresholds must be nonnegative eV values")
    candidates = contract["candidates"]
    _require(isinstance(candidates, list) and bool(candidates), "SS_CANDIDATES", "candidate list is empty")
    normalized = []
    ids = []
    for candidate in candidates:
        identifier = candidate["id"]
        _require(isinstance(identifier, str) and bool(identifier.strip()) and identifier not in ids,
                 "SS_CANDIDATES", "candidate IDs must be nonempty and unique")
        ids.append(identifier)
        uncertainty = candidate["uncertainty"]
        _require(set(uncertainty) == {"input", "model"}, "SS_UNCERTAINTY", "input and model components required")
        values = {key: _number(value) * factor for key, value in uncertainty.items()}
        _require(all(v >= 0 and math.isfinite(v) for v in values.values()),
                 "SS_UNCERTAINTY", "uncertainties must be finite and nonnegative")
        hopping = _number(candidate["hopping"]) * factor
        onsite = _number(candidate["onsite"]) * factor
        _require(hopping >= 0 and math.isfinite(hopping) and math.isfinite(onsite),
                 "SS_MODEL", "finite onsite and nonnegative hopping required")
        normalized.append({"id": identifier, "onsite": onsite, "hopping": hopping, "uncertainty": values})
    scenarios = contract["sensitivity"]
    _require(isinstance(scenarios, list) and bool(scenarios), "SS_SENSITIVITY", "declare at least one model sensitivity")
    scenario_ids = []
    for scenario in scenarios:
        name = scenario["id"]
        _require(isinstance(name, str) and bool(name.strip()) and name not in scenario_ids,
                 "SS_SENSITIVITY", "sensitivity IDs must be nonempty and unique")
        scenario_ids.append(name)
        _require(_number(scenario["hopping_scale"]) >= 0, "SS_SENSITIVITY", "hopping scale must be nonnegative")
        _require(set(scenario["onsite_shifts"]) == set(ids), "SS_SENSITIVITY", "every candidate needs an eV shift")
        for shift in scenario["onsite_shifts"].values():
            _number(shift)
    return {"energy_unit": "eV", "length_unit": "nm", "lattice_spacing": spacing, "candidates": normalized,
            "thresholds_used": dict(thresholds), "exploratory": False}


def _rank_rows(candidates: list[dict[str, Any]], series: list[dict[str, Any]],
               scenario: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows = []
    for candidate, record in zip(candidates, series):
        scale = scenario["hopping_scale"] if scenario else 1.0
        shift = scenario["onsite_shifts"][candidate["id"]] if scenario else 0.0
        energy = chain_spectrum(32, candidate["onsite"] + shift, candidate["hopping"] * scale)[0]
        components = dict(candidate["uncertainty"], numerical=record["final_error"] * scale)
        combined = math.hypot(*components.values())
        rows.append({"candidate_id": candidate["id"], "energy": energy, "uncertainty_components": components,
                     "combined_uncertainty": combined, "score": energy + combined})
    return sorted(rows, key=lambda row: (row["score"], row["candidate_id"]))


def reference_bundle(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return deterministic synthetic records in memory; perform no execution I/O."""
    try:
        normalized = _normalized(contract)
        control = {"ran": True, "sites": 2, "observed": chain_spectrum(2, 0, 1), "expected": [-1.0, 1.0]}
        _check_control(control, contract["thresholds"]["analytic_abs"])
        series = []
        for candidate in normalized["candidates"]:
            limit = candidate["onsite"] - 2 * candidate["hopping"]
            points = [{"sites": n, "value": chain_spectrum(n, candidate["onsite"], candidate["hopping"])[0]}
                      for n in REFINEMENTS]
            final_error = abs(points[-1]["value"] - limit)
            series.append({"candidate_id": candidate["id"], "series": points, "reference_limit": limit,
                           "final_error": final_error,
                           "converged": final_error <= contract["thresholds"]["convergence_abs"]})
        _require(all(record["converged"] for record in series), "SS_NOT_CONVERGED", "reference candidates must converge before ranking")
        rows = _rank_rows(normalized["candidates"], series)
        order = [row["candidate_id"] for row in rows]
        sensitivity = []
        for scenario in contract["sensitivity"]:
            alternative = _rank_rows(normalized["candidates"], series, scenario)
            alternative_order = [row["candidate_id"] for row in alternative]
            sensitivity.append({"id": scenario["id"], "rows": alternative, "order": alternative_order,
                                "flips": alternative_order != order})
        data = [normalized,
                control,
                {"candidates": series},
                {"rule": "minimize-energy-plus-standard-uncertainty", "covariance": "independent-components",
                 "rows": rows, "order": order, "sensitivity": sensitivity},
                {"review_status": "pending", "exploratory": False,
                 "claims": [{"id": "C-numerical", "kind": "descriptive", "status": "supported", "basis": "numerical-verification"},
                            {"id": "C-experiment", "kind": "descriptive", "status": "unavailable", "basis": "experiment"}],
                 "experimental_comparison": {"status": "unavailable", "observable": None},
                 "failed_controls": [], "negative_results": [],
                 "next_action": "Independent science-review of the toy workflow contract; obtain matched measurements for physical claims."}]
        records = {"contract.json": contract}
        previous = "contract.json"
        for (stage_id, filename), stage_data in zip(STAGES, data):
            inputs = list(dict.fromkeys(["contract.json", previous]))
            records[filename] = {"schema": STAGE_SCHEMA, "synthetic": True, "stage_id": stage_id,
                                 "inputs": [{"path": name, "sha256": hashlib.sha256(encode_record(records[name])).hexdigest()}
                                            for name in inputs], "data": stage_data}
            previous = filename
        return records
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("SS_SHAPE: malformed reference contract") from error


def _check_control(data: dict[str, Any], tolerance: float) -> None:
    _require(data["ran"] is True, "SS_ANALYTIC_NOT_RUN", "analytic control must run before candidates are scored")
    _require(type(data["sites"]) is int and data["sites"] == 2 and data["expected"] == [-1.0, 1.0],
             "SS_ANALYTIC_REFERENCE", "dimer control must use the fixed closed-form spectrum")
    observed = data["observed"]
    _require(isinstance(observed, list) and len(observed) == 2, "SS_ANALYTIC_REFERENCE", "both eigenvalues required")
    _require(max(abs(_number(v) - e) for v, e in zip(observed, [-1.0, 1.0])) <= tolerance,
             "SS_ANALYTIC_TOLERANCE", "failed analytic control forbids candidate scoring/ranking")


def _check_convergence(data: dict[str, Any], expected: dict[str, Any], thresholds: dict[str, Any]) -> None:
    records = data["candidates"]
    wanted = expected["candidates"]
    _require(isinstance(records, list) and len(records) == len(wanted),
             "SS_CONVERGENCE_SERIES", "all candidate series must be retained")
    for record, reference in zip(records, wanted):
        points = record["series"]
        _require(record["candidate_id"] == reference["candidate_id"]
                 and isinstance(points, list) and [p["sites"] for p in points] == REFINEMENTS
                 and all(type(p["sites"]) is int for p in points),
                 "SS_CONVERGENCE_SERIES", "absent, reordered or truncated refinement series")
        errors = [abs(_number(p["value"]) - reference["reference_limit"]) for p in points]
        _require(all(b <= a + thresholds["monotone_slack"] for a, b in zip(errors, errors[1:])),
                 "SS_NONMONOTONE", "refinement errors increase beyond the predeclared slack")
        _require(errors[-1] <= thresholds["convergence_abs"] and record["converged"] is True,
                 "SS_NOT_CONVERGED", "failed convergence forbids ranking; retain every level")
        _require(_same_number(record["reference_limit"], reference["reference_limit"])
                 and _same_number(record["final_error"], errors[-1])
                 and all(_same_number(p["value"], r["value"]) for p, r in zip(points, reference["series"])),
                 "SS_REFERENCE_VALUES", "recorded refinements do not reproduce the toy Hamiltonian")


def _check_rows(rows: Any, expected: list[dict[str, Any]]) -> None:
    _require(isinstance(rows, list) and len(rows) == len(expected), "SS_UNCERTAINTY", "every candidate needs a ranking row")
    for row, reference in zip(rows, expected):
        _require(row["candidate_id"] == reference["candidate_id"], "SS_RANKING", "uncertainty-aware candidate order differs")
        components = row["uncertainty_components"]
        _require(set(components) == set(reference["uncertainty_components"])
                 and all(_same_number(components[k], v) for k, v in reference["uncertainty_components"].items())
                 and _same_number(row["combined_uncertainty"], reference["combined_uncertainty"])
                 and _same_number(row["score"], reference["score"]),
                 "SS_UNCERTAINTY", "ranking must include every declared uncertainty and numerical error")
        _require(_same_number(row["energy"], reference["energy"]), "SS_REFERENCE_VALUES", "ranking energy differs from model")


def _check_ranking(data: dict[str, Any], expected: dict[str, Any]) -> None:
    _require(data["rule"] == expected["rule"] and data["covariance"] == expected["covariance"],
             "SS_UNCERTAINTY", "declare the scoring rule and independence assumption")
    _check_rows(data["rows"], expected["rows"])
    _require(data["order"] == expected["order"], "SS_RANKING", "ranking order does not follow the declared score")
    scenarios = data["sensitivity"]
    _require(isinstance(scenarios, list) and len(scenarios) == len(expected["sensitivity"]),
             "SS_SENSITIVITY", "every declared sensitivity must be reported")
    for scenario, reference in zip(scenarios, expected["sensitivity"]):
        _require(scenario["id"] == reference["id"] and scenario["order"] == reference["order"]
                 and scenario["flips"] is reference["flips"],
                 "SS_SENSITIVITY", "model-sensitive ranking reversal must be reported")
        _check_rows(scenario["rows"], reference["rows"])


def _check_claims(data: dict[str, Any], exploratory: bool) -> None:
    _require(data["review_status"] == "pending", "SS_REVIEW_TRUTH", "producer cannot attest independent review or truth")
    _require(data["exploratory"] is exploratory, "SS_EXPLORATORY", "handoff must preserve exploratory status")
    comparison = data["experimental_comparison"]
    _require(comparison == {"status": "unavailable", "observable": None},
             "SS_EXPERIMENT", "synthetic numerical evidence has no matched experimental observable")
    claims = data["claims"]
    _require(isinstance(claims, list) and bool(claims), "SS_CLAIMS", "claim dispositions are required")
    ids = []
    for claim in claims:
        _require(isinstance(claim["id"], str) and bool(claim["id"].strip()) and claim["id"] not in ids,
                 "SS_CLAIMS", "claim IDs must be nonempty and unique")
        ids.append(claim["id"])
        _require(claim["kind"] in ("descriptive", "associational"), "SS_CAUSALITY", "association is never causality")
        _require(claim["basis"] in ("numerical-verification", "experiment"),
                 "SS_PHYSICAL_VALIDITY", "numerical agreement is never physical or clinical validity")
        if claim["basis"] == "experiment":
            _require(claim["status"] == "unavailable", "SS_MISSING_EVIDENCE", "absent experiment is unavailable, never negative evidence")
        else:
            _require(claim["status"] in ("supported", "inconclusive", "unavailable"), "SS_CLAIMS", "invalid numerical claim status")
    _require(isinstance(data["failed_controls"], list) and isinstance(data["negative_results"], list)
             and isinstance(data["next_action"], str) and bool(data["next_action"].strip()),
             "SS_CLAIMS", "retain failed controls, negative results and the next falsifiable action")


def validate_bundle(directory: Path) -> dict[str, Any]:
    """Validate one immutable, ordered fixture snapshot; refuse with labelled errors."""
    try:
        with _Bundle(Path(os.path.abspath(directory))) as bundle:
            return _validate_snapshot(bundle)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError, RecursionError) as error:
        raise ValueError("SS_SHAPE: malformed or incomplete screening record") from error
    except (OSError, RuntimeError) as error:
        raise ValueError("SS_MISSING_RECORD: screening evidence unavailable") from error


def _validate_snapshot(bundle: _Bundle) -> dict[str, Any]:
    raw = {}
    records = {}
    for name in ("contract.json", *(name for _, name in STAGES)):
        raw[name], records[name] = _load_record(bundle, Path(name))
    contract = records["contract.json"]
    prespecified = _normalized(contract)
    previous = "contract.json"
    for stage_id, name in STAGES:
        stage = records[name]
        _require(stage["schema"] == STAGE_SCHEMA and stage["stage_id"] == stage_id and stage["synthetic"] is True,
                 "SS_STAGE_ORDER", "fixed ordered stage IDs and schemas are required")
        inputs = list(dict.fromkeys(["contract.json", previous]))
        wanted = [{"path": item, "sha256": hashlib.sha256(raw[item]).hexdigest()} for item in inputs]
        _require(stage["inputs"] == wanted, "SS_IDENTITY", f"{name}: path-plus-hash handoff differs")
        previous = name
    normalized = records["normalized.json"]["data"]
    thresholds = normalized["thresholds_used"]
    _require(set(thresholds) == set(contract["thresholds"])
             and all(_number(v) >= 0 for v in thresholds.values()), "SS_THRESHOLDS", "invalid effective thresholds")
    exploratory = normalized["exploratory"]
    _require(type(exploratory) is bool and (thresholds == contract["thresholds"] or exploratory),
             "SS_POSTHOC_THRESHOLDS", "changed thresholds require an exploratory label")
    _require({k: v for k, v in normalized.items() if k not in ("thresholds_used", "exploratory")}
             == {k: v for k, v in prespecified.items() if k not in ("thresholds_used", "exploratory")},
             "SS_NORMALIZATION", "normalized model/units must preserve the supplied contract")
    _check_control(records["analytic-control.json"]["data"], thresholds["analytic_abs"])
    expected = reference_bundle(dict(contract, thresholds=thresholds))
    _check_convergence(records["convergence.json"]["data"], expected["convergence.json"]["data"], thresholds)
    _check_ranking(records["ranking.json"]["data"], expected["ranking.json"]["data"])
    _check_claims(records["review-handoff.json"]["data"], exploratory)
    bundle.finish()
    return {"status": "exploratory" if exploratory else "contract-validated", "synthetic": True,
            "review_status": "pending", "order": records["ranking.json"]["data"]["order"],
            "evidence_boundary": "Workflow contract only; materials-property accuracy is unvalidated."}
