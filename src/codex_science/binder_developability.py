"""Sequence observations and assay-bound selectivity; no developability predictor."""

from __future__ import annotations

import math
import re

from codex_science.virtual_screening import fingerprint


AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _sequence(value):
    _require(_text(value) and set(value) <= AA, "sequence must use uppercase canonical amino acids")
    return value


def _positions(values, length):
    _require(isinstance(values, list) and all(type(i) is int and 1 <= i <= length for i in values)
             and len(values) == len(set(values)), "protected positions must be unique one-based integers")
    return values


def analyze_binder_developability(payload):
    """Keep chain-local sequence observations separate from matched panel results."""
    _require(isinstance(payload, dict) and type(payload.get("schema_version")) is int and payload["schema_version"] == 1,
             "unsupported binder developability schema")
    fingerprint(payload)
    contract = payload.get("contract")
    _require(isinstance(contract, dict) and payload.get("contract_sha256") == fingerprint(contract), "frozen contract hash mismatch")
    binder_class = contract.get("binder_class")
    _require(binder_class in ("minibinder", "VHH", "paired_Fv"), "binder class required")
    _require(_text(contract.get("target_id")), "on-target identity required")
    sources = contract.get("source_chains", {})
    _require(isinstance(sources, dict), "source_chains must be an object")
    required = {"H", "L"} if binder_class == "paired_Fv" else {"H"} if binder_class == "VHH" else None
    if required is not None:
        _require(set(sources) == required, "antibody source H/L chain identities required")
    for chain, source in sources.items():
        _require(_text(chain) and isinstance(source, dict), "source chain invalid")
        sequence = _sequence(source.get("sequence"))
        positions = _positions(source.get("protected_positions"), len(sequence))
        _require(bool(positions), "source protected framework/disulfide positions required")
    limits = contract.get("limits", {})
    allowed_limits = {"max_nglyco_sequons", "max_aromatic_fraction", "max_basic_minus_acidic_count"}
    _require(isinstance(limits, dict) and set(limits) <= allowed_limits, "unknown sequence limit")
    _require(all(_finite(value) for value in limits.values()), "sequence limits must be finite")
    if "max_nglyco_sequons" in limits:
        _require(type(limits["max_nglyco_sequons"]) is int and limits["max_nglyco_sequons"] >= 0,
                 "sequon count limit must be a non-negative integer")
    if "max_aromatic_fraction" in limits:
        _require(0 <= limits["max_aromatic_fraction"] <= 1, "aromatic fraction limit must be in [0,1]")
    panel = contract.get("panel")
    if panel is not None:
        _require(isinstance(panel, dict), "panel contract must be an object")
        targets = panel.get("off_target_ids")
        _require(isinstance(targets, list) and bool(targets) and all(_text(t) for t in targets)
                 and len(set(targets)) == len(targets) and contract["target_id"] not in targets, "off-target identities invalid")
        _require(all(_text(panel.get(f)) for f in ("assay_id", "unit", "metric")), "panel endpoint identity required")
        _require(panel.get("source_kind") in ("measured", "predicted", "computed"), "panel source kind required")
        _require(panel.get("direction") in ("higher", "lower") and _finite(panel.get("minimum_margin")), "panel direction and finite margin required")
    controls = payload.get("controls")
    _require(isinstance(controls, list) and all(isinstance(row, dict) and _text(row.get("id")) and type(row.get("passed")) is bool for row in controls), "control identities/outcomes required")
    _require(len({row["id"] for row in controls}) == len(controls), "duplicate control identity")
    controls_passed = bool(controls) and all(row["passed"] for row in controls)
    candidates = payload.get("candidates")
    _require(isinstance(candidates, list) and bool(candidates), "candidate inventory required")
    ids, constructs, sequence_ids, records = set(), set(), set(), []
    for row in candidates:
        _require(isinstance(row, dict) and _text(row.get("id")) and row["id"] not in ids, "duplicate or missing candidate identity")
        ids.add(row["id"])
        construct = row.get("construct_id")
        _require(_text(construct) and construct not in constructs, "duplicate or missing construct identity")
        constructs.add(construct)
        chains = row.get("chains")
        _require(isinstance(chains, dict) and bool(chains) and all(_text(c) for c in chains), "candidate chain identities required")
        _require(required is None or set(chains) == required, "antibody candidate chain identity mismatch")
        _require(not sources or set(chains) == set(sources), "source/candidate chain mismatch")
        sequence_identity = tuple(sorted((chain, _sequence(sequence)) for chain, sequence in chains.items()))
        molecular_sequence_identity = tuple(sorted(sequence for _, sequence in sequence_identity))
        _require(molecular_sequence_identity not in sequence_ids, "duplicate binder sequence identity")
        sequence_ids.add(molecular_sequence_identity)
        observations = []
        for chain, sequence in sequence_identity:
            source = sources.get(chain)
            if source:
                _require(len(sequence) == len(source["sequence"]), "length-changing designs require residue-map validation by binder-design-campaign")
                _require(all(sequence[i - 1] == source["sequence"][i - 1] for i in source["protected_positions"]), "protected framework/disulfide residue changed")
            sequons = [{"position": match.start() + 1, "sequence": sequence[match.start():match.start() + 3]} for match in re.finditer(r"(?=(N[^P][ST]))", sequence)]
            observations.append({"chain": chain, "length": len(sequence), "nglyco_sequons": sequons,
                "cysteine_positions": [i + 1 for i, aa in enumerate(sequence) if aa == "C"],
                "aromatic_count": sum(aa in "FWY" for aa in sequence),
                "basic_minus_acidic_count": sum(aa in "KR" for aa in sequence) - sum(aa in "DE" for aa in sequence)})
        length = sum(item["length"] for item in observations)
        sequon_count = sum(len(item["nglyco_sequons"]) for item in observations)
        aromatic_fraction = sum(item["aromatic_count"] for item in observations) / length
        basic_minus_acidic_count = sum(item["basic_minus_acidic_count"] for item in observations)
        metrics = {"max_nglyco_sequons": sequon_count, "max_aromatic_fraction": aromatic_fraction,
                   "max_basic_minus_acidic_count": basic_minus_acidic_count}
        reasons = [name for name, threshold in limits.items() if metrics[name] > threshold]
        panel_result = {"status": "unavailable", "reason": "no panel contract"}
        supplied = row.get("panel_results", [])
        _require(isinstance(supplied, list), "panel_results must be a list")
        if panel is None:
            _require(not supplied, "panel results require frozen panel contract")
        else:
            values = {}
            expected = {contract["target_id"], *panel["off_target_ids"]}
            for result in supplied:
                _require(isinstance(result, dict), "panel row must be an object")
                target = result.get("target_id")
                _require(target in expected and target not in values, "unknown or duplicate panel target")
                _require(result.get("construct_id") == construct, "panel construct identity mismatch")
                _require(all(result.get(f) == panel[f] for f in ("assay_id", "unit", "metric", "source_kind")), "panel endpoint identity mismatch")
                _require(_finite(result.get("value")), "panel value must be finite")
                values[target] = result["value"]
            missing = sorted(expected - set(values))
            if missing:
                panel_result = {"status": "unavailable", "missing_targets": missing}
                reasons.append("incomplete-panel")
            else:
                sign = 1 if panel["direction"] == "higher" else -1
                margins = {target: sign * (values[contract["target_id"]] - values[target]) for target in panel["off_target_ids"]}
                _require(all(_finite(v) for v in margins.values()), "panel margin overflow")
                passed = all(value >= panel["minimum_margin"] for value in margins.values())
                panel_result = {"status": "computed", "source_kind": panel["source_kind"], "margins": margins,
                                "unit": panel["unit"], "passes_declared_margin": passed,
                                "qualified_margin_comparison": passed and controls_passed}
                if not passed:
                    reasons.append("panel-margin")
        if not controls_passed:
            reasons.append("controls-not-passed")
        records.append({"id": row["id"], "construct_id": construct, "chain_observations": observations,
            "nglyco_sequon_count": sequon_count, "aromatic_fraction": aromatic_fraction,
            "basic_minus_acidic_count": basic_minus_acidic_count, "panel": panel_result,
            "retained": not reasons, "exclusion_reasons": reasons})
    result = {"schema": "binder-developability-result-v1", "contract_sha256": payload["contract_sha256"],
        "engine_executed": False, "controls_passed": controls_passed, "controls": controls,
        "candidate_count": len(records), "retained_count": sum(row["retained"] for row in records), "candidates": records,
        "evidence_boundary": "Sequence counts and potential sequons are observations, not TAP/TNP scores, net charge, solubility, aggregation, expression or immunogenicity predictions. Supplied panels retain their source kind; no assay or binding is established by this helper."}
    fingerprint(result)
    return result
