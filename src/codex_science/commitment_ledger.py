"""Optional protocol commitment ledger validation (v1)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SUPPORTED_TARGET_SETS = {
    ("record", "screening.json", "included"),
    ("record", "screening.json", "all"),
    ("study", "studies.json", "included"),
}


def resolve_target_ids(
    procedure_target_set: dict[str, Any],
    studies_payload: dict[str, Any],
    screening_payload: dict[str, Any] | None,
    *,
    procedure_id: str = "unknown",
) -> list[str]:
    """Resolve membership from validated source payloads."""
    if procedure_target_set["unit"] == "record":
        rows = (screening_payload or {}).get("records", [])
        field = "record_id"
    else:
        rows = studies_payload.get("studies", [])
        field = "study_id"
    for row in rows:
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"procedure {procedure_id}: {field} must be a non-empty string; "
                f"expected: string; actual: {_bounded_repr(value)}"
            )
    if field == "record_id":
        selected = [
            row for row in rows
            if procedure_target_set["selection"] == "all" or row.get("decision") == "include"
        ]
    else:
        selected = [row for row in rows if row.get("included", False) is True]
    return sorted({row[field].strip() for row in selected})


def _supported_target_set_message() -> str:
    return (
        "Supported target_set forms: "
        '{"unit":"record","source_artifact":"screening.json","selection":"included"}, '
        '{"unit":"record","source_artifact":"screening.json","selection":"all"}, '
        '{"unit":"study","source_artifact":"studies.json","selection":"included"}. '
        "Expected: one of these; actual: unsupported combination."
    )


def validate_ledger(
    ledger: dict[str, Any],
    *,
    study_table_payload: dict[str, Any] | None,
    screening_payload: dict[str, Any] | None,
    claim_ids: set[str],
    verified: dict[str, Path],
    report_path: Path | None,
    study_table_artifact: str | None = "studies.json",
    screening_artifact: str | None = "screening.json",
) -> dict[str, Any]:
    """Check closure using validated payloads bound to their verified artifact paths."""
    context_procedures: list[dict[str, Any]] = []

    if ledger.get("schema_version") != 1:
        raise ValueError(
            f"commitment_ledger schema_version must be 1: expected: 1; actual: {_bounded_repr(ledger.get('schema_version'))}"
        )
    procedures = ledger.get("procedures")
    if not isinstance(procedures, list):
        raise ValueError(
            f"commitment_ledger procedures must be a list: expected: list; actual: {type(procedures).__name__}; procedure: unknown"
        )
    if len(procedures) == 0:
        return {"procedures": []}

    procedure_ids = set()
    artifact_paths = set(verified)
    report_text: str | None = None
    for index, procedure in enumerate(procedures):
        if not isinstance(procedure, dict):
            raise ValueError(f"procedure index {index}: must be an object; actual: {type(procedure).__name__}")
        label = f"procedure {procedure.get('id', f'index {index}')}"
        proc_id = procedure.get("id") if isinstance(procedure.get("id"), str) and procedure.get("id", "").strip() else None
        if proc_id is None:
            raise ValueError(f"{label}: id must be a non-empty string; expected: non-empty string; actual: {_bounded_repr(procedure.get('id'))}")
        if proc_id in procedure_ids:
            raise ValueError(f"{label}: duplicate procedure id: {proc_id}; expected: unique; actual: duplicate of {proc_id}")
        procedure_ids.add(proc_id)

        target_set = procedure.get("target_set")
        if not isinstance(target_set, dict):
            raise ValueError(
                f"{label}: target_set must be an object; expected: object; actual: {type(target_set).__name__}; {_supported_target_set_message()}"
            )
        unit = target_set.get("unit")
        source = target_set.get("source_artifact")
        selection = target_set.get("selection")
        if (
            not all(isinstance(value, str) for value in (unit, source, selection))
            or (unit, source, selection) not in SUPPORTED_TARGET_SETS
        ):
            raise ValueError(
                f"{label}: unsupported target_set; expected: one of {sorted({str(s) for s in SUPPORTED_TARGET_SETS})}; actual: (unit={unit}, source_artifact={source}, selection={selection}); {_supported_target_set_message()}"
            )

        target_ids_raw = procedure.get("target_ids")
        denominator_raw = procedure.get("denominator")
        if target_ids_raw is None:
            raise ValueError(f"{label}: target_ids must be resolved at closure; expected: list; actual: null; field: target_ids")
        if denominator_raw is None:
            raise ValueError(f"{label}: denominator must be resolved at closure; expected: integer; actual: null; field: denominator")

        if not isinstance(target_ids_raw, list) or any(
            not isinstance(item, str) or not item.strip() for item in target_ids_raw
        ):
            raise ValueError(f"{label}: target_ids must be a list of non-empty strings; actual: {_bounded_repr(target_ids_raw)}")
        target_ids = [item.strip() for item in target_ids_raw]
        if len(set(target_ids)) != len(target_ids):
            raise ValueError(f"{label}: target_ids must be unique; actual: {_bounded_repr(target_ids_raw)}")

        source_payload = screening_payload if unit == "record" else study_table_payload
        payload_artifact = screening_artifact if unit == "record" else study_table_artifact
        if source_payload is None or source not in artifact_paths or source != payload_artifact:
            raise ValueError(
                f"{label}: missing source_artifact {source}; expected: registered, hash-verified source artifact; "
                f"actual payload artifact: {_bounded_repr(payload_artifact)}"
            )
        resolved_ids = resolve_target_ids(target_set, study_table_payload or {}, screening_payload, procedure_id=proc_id)
        if unit == "study" and screening_payload is not None:
            included_screen_ids = set(resolve_target_ids({"unit": "record", "selection": "included"}, {}, screening_payload, procedure_id=proc_id))
            extracted_ids = {
                study["record_id"].strip() for study in source_payload["studies"]
                if study.get("included", False) is True
                and isinstance(study.get("record_id"), str) and study["record_id"].strip()
            }
            unextracted = sorted(included_screen_ids - extracted_ids)
            if unextracted:
                raise ValueError(
                    f"{label}: study denominator blocked by unextracted included records in screening.json: {unextracted}; "
                    "expected: all included screening records extracted in studies.json; field: denominator"
                )

        if sorted(target_ids) != sorted(resolved_ids):
            raise ValueError(
                f"{label}: target_ids does not match resolved membership from source_artifact; expected: {sorted(resolved_ids)}; actual: {sorted(target_ids)}; field: target_ids"
            )

        if isinstance(denominator_raw, bool):
            raise ValueError(
                f"{label}: denominator must be an integer, not bool; expected: integer; actual: bool; field: denominator"
            )
        if not isinstance(denominator_raw, int):
            raise ValueError(
                f"{label}: denominator must be an integer; expected: integer; actual: {type(denominator_raw).__name__}; field: denominator"
            )
        denominator = denominator_raw
        if denominator != len(target_ids):
            raise ValueError(
                f"{label}: denominator does not equal len(target_ids); expected: {len(target_ids)}; actual: {denominator}; field: denominator"
            )

        completed_raw = procedure.get("completed")
        if completed_raw is None:
            completed_raw = []
        if not isinstance(completed_raw, list):
            raise ValueError(
                f"{label}: completed must be a list; expected: list; actual: {type(completed_raw).__name__}; field: completed"
            )
        completed_items = []
        completed_target_ids = set()
        for c_index, c_item in enumerate(completed_raw):
            c_label = f"{label} completed[{c_index}]"
            if not isinstance(c_item, dict):
                raise ValueError(f"{c_label}: must be an object; expected: object; actual: {type(c_item).__name__}")
            target_id = c_item.get("target_id")
            evidence_artifact = c_item.get("evidence_artifact")
            if not isinstance(target_id, str) or not target_id.strip():
                raise ValueError(f"{c_label}: target_id must be a non-empty string; expected: non-empty string; actual: {_bounded_repr(target_id)}")
            target_id = target_id.strip()
            if target_id not in target_ids:
                raise ValueError(
                    f"{c_label}: target_id is not a member of target_ids; expected: one of {sorted(target_ids)}; actual: {target_id}; field: completed[].target_id"
                )
            if target_id in completed_target_ids:
                raise ValueError(
                    f"{c_label}: duplicate target_id in completed; expected: unique; actual: duplicate of {target_id}"
                )
            completed_target_ids.add(target_id)
            if not isinstance(evidence_artifact, str) or not evidence_artifact.strip():
                raise ValueError(
                    f"{c_label}: evidence_artifact must be a non-empty string; expected: non-empty string; actual: {_bounded_repr(evidence_artifact)}"
                )
            if evidence_artifact not in artifact_paths:
                raise ValueError(
                    f"{c_label}: evidence_artifact is not a registered, hash-verified artifact path; expected: one of {sorted(artifact_paths)}; actual: {evidence_artifact}; field: completed[].evidence_artifact"
                )
            completed_items.append({"target_id": target_id, "evidence_artifact": evidence_artifact})

        completed_count_raw = procedure.get("completed_count")
        if completed_count_raw is None:
            raise ValueError(f"{label}: completed_count is required; expected: integer; actual: missing; field: completed_count")
        if isinstance(completed_count_raw, bool):
            raise ValueError(f"{label}: completed_count must be an integer, not bool; expected: integer; actual: bool; field: completed_count")
        if not isinstance(completed_count_raw, int):
            raise ValueError(
                f"{label}: completed_count must be an integer; expected: integer; actual: {type(completed_count_raw).__name__}; field: completed_count"
            )
        completed_count = completed_count_raw
        if completed_count != len(completed_items):
            raise ValueError(
                f"{label}: completed_count does not equal len(completed); expected: {len(completed_items)}; actual: {completed_count}; field: completed_count"
            )

        deviation = procedure.get("deviation")
        if completed_count < denominator and deviation is None:
            raise ValueError(
                f"{label}: deviation is required when completed_count < denominator; missing target ids: {sorted(set(target_ids) - completed_target_ids)}; expected: non-empty deviation object; actual: missing; field: deviation"
            )
        if deviation is not None:
            if not isinstance(deviation, dict):
                raise ValueError(
                    f"{label}: deviation must be an object; expected: object; actual: {type(deviation).__name__}; field: deviation"
                )
            reason = deviation.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(
                    f"{label}: deviation reason must be a non-empty string; expected: non-empty text; actual: {_bounded_repr(reason)}; field: deviation.reason"
                )
            affected_claims = deviation.get("affected_claims")
            no_claim_impact_reason = deviation.get("no_claim_impact_reason")
            has_affected = isinstance(affected_claims, list) and len(affected_claims) > 0
            has_no_impact = isinstance(no_claim_impact_reason, str) and no_claim_impact_reason.strip()
            if not has_affected and not has_no_impact:
                raise ValueError(
                    f"{label}: deviation must include either non-empty affected_claims or non-empty no_claim_impact_reason; expected: at least one; actual: both missing or empty; field: deviation"
                )
            if has_affected:
                for claim_index, claim_item in enumerate(affected_claims):
                    claim_label = f"{label} deviation.affected_claims[{claim_index}]"
                    if not isinstance(claim_item, dict):
                        raise ValueError(f"{claim_label}: must be an object; expected: object; actual: {type(claim_item).__name__}")
                    claim_id = claim_item.get("claim_id")
                    limitation = claim_item.get("limitation")
                    if not isinstance(claim_id, str) or not claim_id.strip():
                        raise ValueError(f"{claim_label}: claim_id must be a non-empty string; expected: non-empty string; actual: {_bounded_repr(claim_id)}")
                    if claim_id not in claim_ids:
                        known_claims_text = sorted(claim_ids) or "none registered"
                        raise ValueError(
                            f"{claim_label}: claim_id {claim_id} does not exist in claims.json or manifest; expected: one of {known_claims_text}; actual: {claim_id}; field: deviation.affected_claims[].claim_id"
                        )
                    if not isinstance(limitation, str) or not limitation.strip():
                        raise ValueError(f"{claim_label}: limitation must be a non-empty string; expected: non-empty text; actual: {_bounded_repr(limitation)}; field: deviation.affected_claims[].limitation")
                    if report_path is None:
                        raise ValueError(f"{claim_label}: limitation requires a registered, hash-verified report.md")
                    if report_text is None:
                        report_text = report_path.read_text(encoding="utf-8")
                    if limitation not in report_text:
                        raise ValueError(
                            f"{claim_label}: limitation text does not appear verbatim in report.md; expected: text present in report.md; actual: missing; field: deviation.affected_claims[].limitation"
                        )

        proc_context: dict[str, Any] = {
            "id": proc_id,
            "target_set": dict(target_set),
            "denominator": denominator,
            "completed_count": completed_count,
        }
        if isinstance(deviation, dict):
            deviation_context = {
                "reason": deviation.get("reason"),
                "no_claim_impact_reason": deviation.get("no_claim_impact_reason"),
            }
            affected_claims_context = []
            if isinstance(deviation.get("affected_claims"), list):
                for ac in deviation.get("affected_claims", []):
                    if isinstance(ac, dict):
                        affected_claims_context.append({
                            "claim_id": ac.get("claim_id"),
                            "limitation": ac.get("limitation"),
                        })
            if affected_claims_context:
                deviation_context["affected_claims"] = affected_claims_context
            proc_context["deviation"] = deviation_context
        context_procedures.append(proc_context)

    return {"procedures": context_procedures}


def _bounded_repr(value: Any) -> str:
    import reprlib
    r = reprlib.Repr()
    r.maxlevel = 4
    r.maxstring = 80
    r.maxlist = 6
    r.maxdict = 6
    r.maxtuple = 6
    r.maxset = 6
    r.maxother = 80
    try:
        rendered = r.repr(value)
    except Exception:
        rendered = f"<{type(value).__name__[:40]}>"
    rendered = rendered.replace("\r", r"\r").replace("\n", r"\n")
    return rendered if len(rendered) <= 120 else rendered[:119] + "…"
