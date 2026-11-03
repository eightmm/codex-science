"""Read-only scientific views of a cycle and existing independent review receipts."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from codex_science.cli_io import load_json_object
from codex_science.research_cycle import _confined_file, _file_hash, _refs, _text, _validate_cycle_hash, validate_cycle
from codex_science.review_receipts import review_receipt_findings, validate_review_receipt


def _cycle_refs(cycle: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}

    def collect(value: Any, location: str) -> None:
        if isinstance(value, Mapping):
            if "path" in value and "sha256" in value:
                path, digest = value["path"], value["sha256"]
                if not isinstance(path, str):
                    raise ValueError(f"cycle evidence path must be a string at {location or 'cycle'}")
                if path in result and result[path] != digest:
                    raise ValueError("cycle contains conflicting evidence identities")
                result[path] = digest
            for key, child in value.items():
                collect(child, f"{location}.{key}" if location else str(key))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect(child, f"{location}[{index}]")

    collect(cycle, "")
    return result


_REVISION_CATEGORIES = ("insufficient_evidence", "repetition", "necessary_repair_candidate",
                        "substantive_progress_candidate")


def classify_revisions(cycle: Mapping[str, Any]) -> dict[str, Any]:
    """Project each recorded revise event into a category from recorded fields only.

    Categories are not judgments of scientific substance; the first matching rule wins.
    """
    states = {item.get("id"): item.get("state") for item in cycle.get("experiments", [])
              if isinstance(item, Mapping)}
    outcomes = []
    for index, event in enumerate(cycle.get("events", [])):
        if not isinstance(event, Mapping) or event.get("kind") != "revise":
            continue
        source = event.get("source_experiment_id")
        state = states.get(source)
        lesson = isinstance(event.get("lesson"), Mapping)
        definitions = [name for name in ("assumptions", "hypotheses", "methods")
                       if isinstance(event.get(name), list) and event[name]]
        added = [item for item in event.get("experiments") or [] if isinstance(item, Mapping)] \
            if isinstance(event.get("experiments"), list) else []
        new_experiments = [item for item in added if not item.get("retry_of")]
        basis = [f"source_state={state}", "lesson=" + ("present" if lesson else "absent"),
                 "appended=" + (",".join(definitions + (["experiments"] if added else [])) or "nothing")]
        if not lesson or not (definitions or added):
            category = "insufficient_evidence"
        elif not definitions and not new_experiments:
            category = "repetition"
            basis.append("every appended experiment has retry_of")
        elif state == "failed":
            category = "necessary_repair_candidate"
        elif state == "completed":
            category = "substantive_progress_candidate"
            basis.append("changed definition" if definitions else "new non-retry experiment")
        else:
            category = "insufficient_evidence"
            basis.append("source experiment state is not resolved in the current cycle")
        outcomes.append({"event_index": index, "source_experiment_id": source, "source_state": state,
                         "category": category, "basis": basis})
    return {"revisions": outcomes,
            "counts": {name: sum(item["category"] == name for item in outcomes) for name in _REVISION_CATEGORIES},
            "evidence_boundary": "Categories are projections of recorded fields, not judgments of scientific substance or score change; candidate labels require review."}


def assess_cycle(cycle: Mapping[str, Any], run_dir: Path,
                 payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Project review coverage without promoting recorded observations to truth.

    A review must cover the current snapshot and its scientific evidence. Multiple
    registered receipts are included, including disagreements. Supplemental
    caller-supplied receipts are scoped to this view, not persisted. Independence
    is the reviewer's attestation, and completeness beyond the bundle is unknown.
    """
    run_dir = Path(run_dir)
    validate_cycle(cycle, run_dir)
    payload = payload or {}
    unknown = sorted(str(key) for key in payload if key not in {"review_refs", "novelty_comparison"})
    if unknown:
        raise ValueError(f"assessment payload has unknown key{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)} "
                         "(expected review_refs or novelty_comparison)")
    refs = _cycle_refs(cycle)
    _refs([{"path": path, "sha256": digest} for path, digest in refs.items()], "cycle evidence", run_dir)
    revision = cycle.get("revision", 0)
    if not cycle.get("cycle_hash") or revision < 1:
        raise ValueError("assessment requires a saved cycle snapshot")
    _validate_cycle_hash(cycle)
    snapshot_path = f"discovery/revisions/{revision:06d}.json"
    snapshot = load_json_object(_confined_file(run_dir, snapshot_path))
    if snapshot != cycle:
        raise ValueError("assessment cycle differs from saved snapshot")
    from codex_science.artifact_store import stream_sha256
    refs[snapshot_path] = stream_sha256(run_dir / snapshot_path)[0]
    axes: dict[str, list[dict[str, Any]]] = {mode: [] for mode in ("record", "source", "method", "reproduction")}
    review_refs = _refs(payload.get("review_refs", []), "review_refs", run_dir)
    supplied_review_refs = list(review_refs)
    registered_reviews = []
    artifact_hashes: dict[str, str] = {}
    registry_digest = None
    if (run_dir / "manifest.json").exists():
        from codex_science.artifacts import validate_bundle
        from codex_science.model_registry_v2 import load_registry_v2, registry_sha256
        manifest = load_json_object(_confined_file(run_dir, "manifest.json"))
        bundle = validate_bundle(manifest, run_dir)
        artifact_hashes = bundle["artifact_hashes"]
        registry_path = Path(__file__).resolve().parents[2] / "models" / "registry-v2.json"
        if registry_path.is_file():
            registry_digest = registry_sha256(load_registry_v2(registry_path))
        registered_reviews = [{"path": item["path"], "sha256": item["sha256"]}
                              for item in manifest["artifacts"]
                              if item["kind"] in {"review-receipt", "review-receipt-v2"}]
        for ref in registered_reviews:
            if ref not in review_refs:
                review_refs.append(ref)
    seen: set[str] = set()
    for ref in review_refs:
        receipt = load_json_object(_confined_file(run_dir, ref["path"]))
        validate_review_receipt(receipt)
        if receipt["review_id"] in seen:
            raise ValueError("duplicate review identity")
        seen.add(receipt["review_id"])
        # Receipts can cover older snapshots too. Validate every declared file,
        # then require coverage of the current scientific state and references.
        # A receipt whose files changed is stale, not fatal: shape is checked
        # here, current hashes are compared by review_receipt_findings.
        covered = _refs([{"path": item["path"], "sha256": str(item["sha256"]).lower()}
                         for item in receipt["covered_artifacts"]], "review covered_artifacts")
        hashes = {item["path"]: item["sha256"] for item in covered}
        current = dict(artifact_hashes)
        evidence_paths = {str(entry.get("artifact_path", ""))
                          for item in receipt.get("findings", []) if isinstance(item.get("evidence"), list)
                          for entry in item["evidence"] if isinstance(entry, Mapping) and "artifact_sha256" in entry}
        has_bundle = (run_dir / "manifest.json").exists()
        for path in set(hashes) | (evidence_paths if has_bundle else set()):
            current.pop(path, None)
            try:
                current[path] = _file_hash(_confined_file(run_dir, path))
            except (ValueError, OSError):
                pass
        findings = review_receipt_findings(receipt, current, registry_sha256=registry_digest,
                                         require_evidence_hashes=has_bundle)
        missing = sorted(path for path, digest in refs.items() if hashes.get(path) != digest)
        qualified = receipt["independent"] and not missing and not findings
        entry = {"review_id": receipt["review_id"], "receipt_ref": ref,
                 "status": receipt["status"], "independent_attested": receipt["independent"],
                 "qualified_coverage": qualified, "missing_paths": missing,
                 "integrity_findings": findings, "findings": receipt.get("findings", []),
                 "limitations": receipt.get("limitations", [])}
        for mode in set(receipt["review_modes"]):
            axes[mode].append(entry)
    review_axes = {}
    for mode, entries in axes.items():
        qualified = [entry for entry in entries if entry["qualified_coverage"]]
        statuses = {entry["status"] for entry in qualified}
        state = ("conflicting" if "passed" in statuses and statuses & {"findings", "blocked"}
                 else "findings" if "findings" in statuses
                 else "blocked" if "blocked" in statuses
                 else "passed_in_review_scope" if "passed" in statuses else "pending")
        review_axes[mode] = {"status": state, "receipts": entries}
    novelty: dict[str, Any] = {"status": "unassessed"}
    if "novelty_comparison" in payload:
        comparison = payload["novelty_comparison"]
        if not isinstance(comparison, Mapping):
            raise ValueError("novelty_comparison must be an object")
        recorded = {key: _text(comparison.get(key), f"novelty comparison {key}")
                    for key in ("scope", "search_cutoff", "difference", "limitations")}
        sources = _refs(comparison.get("source_refs"), "novelty source_refs", run_dir)
        if not sources:
            raise ValueError("novelty comparison requires primary-source records")
        novelty = {"status": "comparison_recorded", "comparison": dict(recorded, source_refs=sources),
                   "evidence_boundary": "Source identity checked; attribution, search completeness and novelty require scientific review."}
    return {"schema_version": 1, "cycle_hash": cycle["cycle_hash"], "revision": revision,
            "execution_integrity": "recorded_identities_validated",
            "review_axes": review_axes, "novelty": novelty,
            "review_scope": {"registered_receipts": registered_reviews, "supplied_receipts": supplied_review_refs,
                             "complete_beyond_registered_bundle": "unknown", "authoritative_overall_pass": False},
            "method_effects": [{"experiment_id": item["id"], "method_effect": item.get("method_effect", "not_assessed"),
                                "explanation_support": item.get("explanation_support", {})}
                               for item in cycle["experiments"]],
            "revision_outcomes": classify_revisions(cycle),
            "evidence_boundary": "Hashes and receipts do not authenticate execution or reviewer independence. Record, source, method and reproduction reviews are separate; none proves novelty or a causal mechanism."}


def cycle_graph(cycle: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    """Reuse evidence graph v2, with edges scoped to preregistered predictions."""
    from codex_science.evidence_graph_v2 import graph_records, validate_typed_graph

    validate_cycle(cycle, run_dir)
    nodes, edges = [], []
    for hypothesis in cycle["hypotheses"]:
        nodes.append({"id": "hypothesis:" + hypothesis["id"], "type": "claim", "status": "conjecture",
                      "statement": hypothesis["statement"], "conditions": hypothesis["conditions"],
                      "falsifier": hypothesis["falsifier"]})
    for method in cycle["methods"]:
        nodes.append({"id": "method:" + method["id"], "type": "model", "definition": method["definition"],
                      "code_refs": method.get("code_refs", [])})
    for experiment in cycle["experiments"]:
        identity = "experiment:" + experiment["id"]
        nodes.append({"id": identity, "type": "execution", "state": experiment.get("state", "planned"),
                      "predictions": experiment["predictions"], "resolution": experiment["resolution"],
                      "controls": experiment["controls"], "observations": experiment.get("observations", []),
                      "execution_refs": experiment.get("execution_refs", [])})
        edges.append({"source": identity, "target": "method:" + experiment["method_id"], "relation": "depends_on"})
        for hypothesis, support in experiment.get("explanation_support", {}).items():
            if support in {"consistent", "contradicted"}:
                edges.append({"source": identity, "target": "hypothesis:" + hypothesis,
                              "relation": "supports" if support == "consistent" else "contradicts",
                              "scope": "preregistered_prediction_only", "mechanism_confirmed": False})
    result = {"schema_version": 2, "cycle_hash": cycle.get("cycle_hash"), "nodes": nodes, "edges": edges,
              "evidence_boundary": "Prediction compatibility under recorded conditions; no causal confirmation, novelty, or independent replication implied."}
    findings = validate_typed_graph(*graph_records(result))
    if findings:
        raise ValueError(f"invalid cycle graph: {findings}")
    return result
