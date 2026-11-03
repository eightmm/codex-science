#!/usr/bin/env python3
"""Check pack-local binder records without executing models or accepting science."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys

AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def positive_int(value):
    return type(value) is int and value > 0


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def unique(rows, label):
    require(isinstance(rows, list), f"{label}: expected list")
    ids = [row.get("id") if isinstance(row, dict) else None for row in rows]
    require(all(text(value) for value in ids) and len(ids) == len(set(ids)),
            f"{label}: missing or duplicate identity")


def read_artifact(root, record):
    require(isinstance(record, dict), "artifact reference must be an object")
    name, digest = record.get("path"), record.get("sha256")
    require(text(name) and "\\" not in name, "invalid artifact path")
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and ".." not in relative.parts,
            "artifact path must stay inside campaign directory")
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(), "artifact escapes or is missing")
    content = path.read_bytes()
    require(isinstance(digest, str) and hashlib.sha256(content).hexdigest() == digest,
            f"artifact hash mismatch: {name}")
    return path, content


def residue_table(payload, binder_format, scaffold=False):
    require(isinstance(payload, dict), "antibody residue artifact must be an object")
    rows = payload.get("residues")
    require(isinstance(rows, list) and bool(rows), "antibody residues required")
    chains = {"H", "L"} if binder_format == "paired_fv" else {"H"}
    require(all(isinstance(row, dict) for row in rows), "invalid residue row")
    require({row.get("chain") for row in rows} == chains, "wrong H/L chain composition")
    known, counts = {}, {}
    for chain in sorted(chains):
        positions = [row.get("position") for row in rows if row["chain"] == chain]
        require(all(positive_int(p) for p in positions)
                and positions == list(range(1, len(positions) + 1)), "invalid residue numbering")
        segments = []
        for row in rows:
            if row["chain"] == chain and (not segments or segments[-1] != row.get("region")):
                segments.append(row.get("region"))
        require(segments == ["framework", chain + "1", "framework", chain + "2",
                             "framework", chain + "3", "framework"], "invalid framework/CDR segment order")
    for row in rows:
        chain, region, source = row["chain"], row.get("region"), row.get("source_id")
        require(region in {"framework", chain + "1", chain + "2", chain + "3"}, "invalid CDR region")
        require(row.get("aa") in AA and type(row.get("protected")) is bool, "invalid amino acid/protection")
        if region != "framework":
            counts[region] = counts.get(region, 0) + 1
        if source is None:
            require(not scaffold and region != "framework" and not row["protected"],
                    "new framework/protected residue")
        else:
            require(text(source) and source not in known, "missing or duplicate source residue")
            known[source] = row
    require(set(counts) == {c + str(i) for c in chains for i in (1, 2, 3)}, "missing CDR definition")
    return known, counts


def validate_campaign(path):
    path = Path(path).resolve()
    root = path.parent
    campaign = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(campaign, dict) and campaign.get("schema") == "binder-campaign-v1", "unsupported campaign")
    mode = campaign.get("mode")
    require(mode in ("synthetic_fixture", "recorded_campaign"), "invalid execution mode")
    contract_path, contract_bytes = read_artifact(root, campaign.get("contract"))
    contract = json.loads(contract_bytes)
    require(isinstance(contract, dict), "contract must be an object")
    fmt, route = contract.get("binder_format"), contract.get("route")
    require(fmt in ("minibinder", "paired_fv", "vhh") and text(route), "invalid binder format/route")
    budget = contract.get("budget", {})
    require(isinstance(budget, dict) and positive_int(budget.get("max_attempts"))
            and positive_int(budget.get("max_sequences_per_backbone")), "invalid campaign budget")
    seeds = contract.get("seeds")
    require(isinstance(seeds, list) and bool(seeds)
            and all(type(seed) is int and seed >= 0 for seed in seeds), "invalid seeds")
    filters = contract.get("filters")
    require(isinstance(filters, dict) and bool(filters), "filters required")
    for name, rule in filters.items():
        require(text(name) and isinstance(rule, dict) and rule.get("direction") in ("min", "max")
                and finite(rule.get("threshold")) and text(rule.get("unit")), "invalid filter")
    models = contract.get("models", {})
    require(isinstance(models, dict), "models required")
    for role in ("design", "validation"):
        model = models.get(role, {})
        require(isinstance(model, dict) and text(model.get("family")) and text(model.get("revision"))
                and isinstance(model.get("sha256"), str) and len(model["sha256"]) == 64
                and all(c in "0123456789abcdef" for c in model["sha256"])
                and type(model.get("conditioned")) is bool, "invalid model identity")
    support = contract.get("validation_support")
    require(support in ("shared-model", "distinct-model"), "invalid validation support")
    if support == "distinct-model":
        design, validation = models["design"], models["validation"]
        require(design["family"] != validation["family"] and design["sha256"] != validation["sha256"]
                and not validation["conditioned"], "false distinct-model support")

    artifacts = campaign.get("artifacts")
    require(isinstance(artifacts, dict) and all(text(key) for key in artifacts), "artifact table required")
    loaded, paths = {}, {contract_path, path}
    for identifier, record in artifacts.items():
        artifact_path, content = read_artifact(root, record)
        require(artifact_path not in paths, "duplicate artifact path")
        paths.add(artifact_path)
        loaded[identifier] = content
        try:
            payload = json.loads(content)
        except (ValueError, UnicodeError):
            payload = None
        if isinstance(payload, dict) and payload.get("synthetic") is True:
            require(mode == "synthetic_fixture", "synthetic artifact mislabeled as recorded campaign")

    def artifact(identifier):
        require(isinstance(identifier, str) and identifier in loaded, "unknown artifact identity")
        return loaded[identifier]

    method = json.loads(artifact(contract.get("method_artifact")))
    require(isinstance(method, dict) and method.get("id") == route, "method identity mismatch")
    formats = method.get("formats")
    require(isinstance(formats, list) and all(f in ("minibinder", "paired_fv", "vhh") for f in formats)
            and fmt in formats, "incompatible binder format/route")
    require(method.get("review_state") in ("documented", "pilot_verified")
            and method.get("sequence_stage") in ("integrated", "separate", "cdr-aware")
            and type(method.get("framework_cdr_aware")) is bool, "method not admitted for planning")
    require(method.get("execution") in ("not_run", "pilot_verified"), "method execution state required")
    if method["review_state"] == "pilot_verified":
        require(mode != "synthetic_fixture" and method["execution"] == "pilot_verified",
                "synthetic or unexecuted method cannot be pilot verified")
        artifact(method.get("pilot_receipt_artifact"))
    if fmt != "minibinder":
        require(method["framework_cdr_aware"], "antibody route must preserve framework/CDR constraints")
    for field in ("input_contract", "output_contract", "terms", "resource_notes", "checked_at"):
        require(text(method.get(field)), f"method {field} required")
    sources = method.get("sources")
    require(isinstance(sources, list) and bool(sources)
            and all(isinstance(source, str) and source.startswith("https://") for source in sources),
            "official method sources required")
    artifact(contract.get("target_artifact"))
    mapping = json.loads(artifact(contract.get("mapping_artifact")))
    require(isinstance(mapping, dict) and isinstance(mapping.get("removed_residues"), list)
            and text(mapping.get("preparation_notes")), "preparation record required")
    for row in mapping["removed_residues"]:
        require(isinstance(row, dict) and text(row.get("source_id")) and text(row.get("reason")),
                "removal reason required")
    map_sources = {}
    for name in (["target_residue_map", "scaffold_residue_map"] if fmt != "minibinder" else ["target_residue_map"]):
        rows = mapping.get(name)
        require(isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) for row in rows), "residue map required")
        for key in ("source_id", "prepared_id"):
            values = [row.get(key) for row in rows]
            require(all(text(value) for value in values) and len(values) == len(set(values)), "invalid residue map")
        map_sources[name] = {row["source_id"] for row in rows}
    scaffold, lengths = {}, {}
    if fmt != "minibinder":
        require(text(contract.get("numbering_scheme")), "antibody numbering scheme required")
        scaffold, _ = residue_table(json.loads(artifact(contract.get("scaffold_artifact"))), fmt, True)
        require(set(scaffold) == map_sources["scaffold_residue_map"], "scaffold mapping loss")
        for row in mapping["scaffold_residue_map"]:
            original = scaffold[row["source_id"]]
            require(row["prepared_id"] == f"{original['chain']}:{original['position']}", "prepared scaffold mapping changed")
        lengths = contract.get("cdr_lengths", {})
        expected = {c + str(i) for c in ({"H", "L"} if fmt == "paired_fv" else {"H"}) for i in (1, 2, 3)}
        require(isinstance(lengths, dict) and set(lengths) == expected, "invalid CDR length contract")
        for bounds in lengths.values():
            require(isinstance(bounds, list) and len(bounds) == 2 and all(positive_int(n) for n in bounds)
                    and bounds[0] <= bounds[1], "invalid CDR length bounds")

    attempts, candidates, controls = (campaign.get(key) for key in ("attempts", "candidates", "controls"))
    for label, rows in (("attempts", attempts), ("candidates", candidates), ("controls", controls)):
        unique(rows, label)
        refs = [row.get("artifact") for row in rows]
        require(all(text(ref) for ref in refs) and len(refs) == len(set(refs)), f"{label}: duplicate artifact identity")
    require(len(attempts) <= budget["max_attempts"], "attempt budget exceeded")
    parents = {}
    counts = dict(attempted=len(attempts), generated=0, failed=0, candidates=len(candidates),
                  retained=0, excluded=0, unevaluable=0)
    for attempt in attempts:
        require(attempt.get("status") in ("generated", "failed"), "invalid attempt status")
        artifact(attempt.get("artifact"))
        counts[attempt["status"]] += 1
        parents[attempt["id"]] = attempt
    children = {key: 0 for key in parents}
    for candidate in candidates:
        parent = parents.get(candidate.get("attempt_id"))
        require(parent is not None and parent["status"] == "generated"
                and candidate.get("parent_artifact") == parent["artifact"], "broken candidate parent lineage")
        children[parent["id"]] += 1
        require(children[parent["id"]] <= budget["max_sequences_per_backbone"], "sequence budget exceeded")
        payload = json.loads(artifact(candidate.get("artifact")))
        require(isinstance(payload, dict) and isinstance(payload.get("metrics"), dict), "candidate metrics required")
        metrics = payload["metrics"]
        missing = any(metrics.get(name) is None for name in filters)
        failed = False
        for name, rule in filters.items():
            value = metrics.get(name)
            if value is None:
                continue
            require(finite(value), "non-finite candidate metric")
            failed |= value < rule["threshold"] if rule["direction"] == "min" else value > rule["threshold"]
        status = candidate.get("status")
        require(status in ("retained", "excluded", "unevaluable") and text(candidate.get("reason")), "candidate status/reason required")
        require((status == "unevaluable") if missing else (status == "excluded" if failed else status in ("retained", "excluded")),
                "candidate status conflicts with frozen filters")
        counts[status] += 1
        if fmt != "minibinder":
            residues, cdr_counts = residue_table(payload, fmt)
            require(all(bounds[0] <= cdr_counts[label] <= bounds[1] for label, bounds in lengths.items()), "CDR length violation")
            for chain in {row["chain"] for row in residues.values()}:
                original_positions = [scaffold[source]["position"] for source, row in residues.items()
                                      if source in scaffold and row["chain"] == chain]
                require(original_positions == sorted(original_positions), "candidate source residue order changed")
            for source, row in residues.items():
                require(source in scaffold and row["chain"] == scaffold[source]["chain"]
                        and row["region"] == scaffold[source]["region"], "candidate residue mapping changed")
            for source, row in scaffold.items():
                if row["region"] == "framework" or row["protected"]:
                    require(source in residues and residues[source]["aa"] == row["aa"]
                            and residues[source]["protected"] == row["protected"], "framework/protected residue changed")
    funnel = campaign.get("funnel")
    require(isinstance(funnel, dict) and set(funnel) == set(counts)
            and all(type(funnel[key]) is int and funnel[key] == value for key, value in counts.items()), "funnel denominator mismatch")
    require(all(parent["status"] == "failed" or children[key] > 0 for key, parent in parents.items()), "generated attempt lost all candidate records")
    control_kinds, blocked = set(), False
    for control in controls:
        require(control.get("kind") in ("positive", "negative") and type(control.get("required")) is bool
                and control.get("status") in ("passed", "failed", "unavailable"), "invalid control")
        evidence = json.loads(artifact(control.get("artifact")))
        require(isinstance(evidence, dict) and evidence.get("kind") == control["kind"]
                and evidence.get("status") == control["status"], "control evidence mismatch")
        control_kinds.add(control["kind"])
        blocked |= control["required"] and control["status"] != "passed"
    require(control_kinds == {"positive", "negative"}
            and any(c["kind"] == "positive" and c["required"] for c in controls), "essential positive and negative controls required")
    claims = campaign.get("claims")
    require(isinstance(claims, list), "claim table required")
    for claim in claims:
        require(isinstance(claim, dict) and claim.get("kind") in ("workflow_integrity", "computational_screen")
                and claim.get("status") in ("supported", "contradicted", "inconclusive", "unavailable"), "unsupported claim class/status")
        if claim["kind"] == "computational_screen" and claim["status"] == "supported":
            require(mode != "synthetic_fixture" and not blocked and counts["retained"] > 0,
                    "unsupported computational screen claim")
    outcome = ("synthetic_only" if mode == "synthetic_fixture" else "controls_failed" if blocked
               else "no_survivors" if not counts["retained"] else "exploratory_candidates")
    return {"status": "contract_checks_passed", "outcome": outcome, "controls_blocked": blocked,
            "binder_format": fmt, "route": route, "funnel": counts,
            "limitations": "Declared record checks only; no coordinate, execution, review or binding validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    args = parser.parse_args()
    try:
        report = validate_campaign(args.campaign)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
