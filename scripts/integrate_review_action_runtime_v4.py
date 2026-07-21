#!/usr/bin/env python3
"""Integrate reviewer and authenticated connector action runtimes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def update_index(path: Path, entry: dict[str, Any]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = "references" if "references" in payload else "entries" if "entries" in payload else "references"
    entries = payload.setdefault(key, [])
    if not isinstance(entries, list):
        raise SystemExit(f"reference index is invalid: {path}")
    existing = next((item for item in entries if isinstance(item, dict) and item.get("id") == entry["id"]), None)
    if existing is None:
        entries.append(entry)
    else:
        existing.clear()
        existing.update(entry)
    entries.sort(key=lambda item: str(item.get("id", "")) if isinstance(item, dict) else "")
    write_json(path, payload)


def add_route(path: Path, marker: str, paragraph: str, *, anchor: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    heading = "## Reference usage"
    if heading in text:
        start = text.index(heading) + len(heading)
        next_heading = text.find("\n## ", start)
        if next_heading < 0:
            text = text.rstrip() + "\n\n" + paragraph + "\n"
        else:
            text = text[:next_heading].rstrip() + "\n\n" + paragraph + "\n" + text[next_heading:]
    else:
        if anchor not in text:
            raise SystemExit(f"cannot insert reference route: {path}")
        text = text.replace(anchor, f"## Reference usage\n\n{paragraph}\n\n{anchor}", 1)
    path.write_text(text, encoding="utf-8")


def add_quality(path: Path, values: tuple[str, ...]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    outputs = payload.setdefault("output_schemas", [])
    if not isinstance(outputs, list):
        raise SystemExit(f"quality output_schemas is invalid: {path}")
    for value in values:
        if value not in outputs:
            outputs.append(value)
    outputs.sort()
    write_json(path, payload)


def patch_reviewer() -> None:
    path = ROOT / "src" / "codex_science" / "reviewer_runtime.py"
    text = path.read_text(encoding="utf-8")
    if "import urllib.parse\n" not in text:
        text = text.replace("import json\n", "import json\nimport urllib.parse\n", 1)
    old = '''    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value
'''
    new = '''    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and "://" in value:
        try:
            parsed = urllib.parse.urlsplit(value)
            query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            if query:
                query = [
                    (
                        key,
                        "[REDACTED]"
                        if any(fragment in key.lower() for fragment in SENSITIVE_FRAGMENTS)
                        else item,
                    )
                    for key, item in query
                ]
                return urllib.parse.urlunsplit(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        urllib.parse.urlencode(query),
                        parsed.fragment,
                    )
                )
        except ValueError:
            return "[REDACTED-INVALID-URL]"
    return value
'''
    if old in text:
        text = text.replace(old, new, 1)
    old_modes = '    response_modes = sorted({_text(item, "response review mode") for item in response.get("review_modes", [])})\n'
    new_modes = '''    response_modes_raw = response.get("review_modes", [])
    if not isinstance(response_modes_raw, list):
        raise ValueError("response review_modes must be a list")
    response_modes = sorted({_text(item, "response review mode") for item in response_modes_raw})
'''
    if old_modes in text:
        text = text.replace(old_modes, new_modes, 1)
    old_claims = '    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in response.get("reviewed_claim_ids", [])})\n'
    new_claims = '''    reviewed_claims_raw = response.get("reviewed_claim_ids", [])
    if not isinstance(reviewed_claims_raw, list):
        raise ValueError("reviewed_claim_ids must be a list")
    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in reviewed_claims_raw})
'''
    if old_claims in text:
        text = text.replace(old_claims, new_claims, 1)
    path.write_text(text, encoding="utf-8")


def patch_action_framework() -> None:
    path = ROOT / "src" / "codex_science" / "action_connectors.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'SECRET_FRAGMENTS = {"token", "password", "secret", "credential", "private_key", "api_key", "apikey", "access_key", "client_secret"}\n',
        'SECRET_FRAGMENTS = {"token", "password", "secret", "credential", "private_key", "api_key", "apikey", "access_key", "client_secret", "authorization", "bearer", "session_cookie"}\n',
    )
    execute_marker = '''    validate_preview(preview, spec)
    existing = ledger.get(spec.idempotency_key)
'''
    execute_replacement = '''    validate_preview(preview, spec)
    if adapter.connector_name != spec.connector:
        raise ValueError("adapter connector does not match action spec")
    existing = ledger.get(spec.idempotency_key)
'''
    if execute_marker in text:
        text = text.replace(execute_marker, execute_replacement, 1)
    if "def validate_action_receipt" not in text:
        text += '''

def validate_action_receipt(payload: Mapping[str, Any], spec: ActionSpec | None = None) -> None:
    if payload.get("schema_version") != 1 or payload.get("status") != "executed":
        raise ValueError("invalid action receipt state")
    for field in (
        "action_id", "connector", "operation", "mode", "target",
        "action_spec_sha256", "preview_id", "preview_fingerprint",
        "idempotency_key", "before_state_sha256", "after_state_sha256",
        "executed_at", "evidence_boundary",
    ):
        _text(payload.get(field), field)
    for field in ("action_spec_sha256", "preview_fingerprint", "before_state_sha256", "after_state_sha256"):
        _sha(payload.get(field), field)
    material = dict(payload)
    fingerprint = str(material.pop("fingerprint", "")).lower()
    if _fingerprint(material) != fingerprint:
        raise ValueError("action receipt fingerprint mismatch")
    if spec is not None and payload.get("action_spec_sha256") != spec.fingerprint:
        raise ValueError("action receipt covers a different spec")
'''
    path.write_text(text, encoding="utf-8")


def patch_references() -> None:
    update_index(
        ROOT / "skills" / "science-review" / "references" / "index.json",
        {
            "id": "independent-review-runtime",
            "path": "references/independent-review-runtime.md",
            "purpose": "Prepare blinded, hash-bound review packets and validate separate reviewer responses without producer-only rationale.",
            "read_when": ["before handing a run to a separate reviewer", "before accepting a reviewer response", "before calling a review independent or reproduced"],
            "required_before": ["calling scripts/science_reviewer.py", "attaching a packet-derived review receipt"],
            "search_patterns": ["## Independence boundary", "## Prepare a review packet", "## Reviewer response contract", "## Reproduction mode", "## Failure handling"],
            "authority": "Codex Science first-party review packet contract",
            "version": "1",
            "evidence_boundary": "The packet standardizes coverage but does not authenticate identity or guarantee independence."
        },
    )
    add_route(
        ROOT / "skills" / "science-review" / "SKILL.md",
        "references/independent-review-runtime.md",
        "Before preparing a separate human or agent review, accepting a response, or claiming independence or reproduction, **MUST** read [the independent reviewer packet contract](references/independent-review-runtime.md). Use `scripts/science_reviewer.py` to bind the packet to source manifest and artifact hashes; do not expose producer-only rationale or transfer a response to changed bytes.",
        anchor="## Review workflow",
    )
    add_quality(ROOT / "skills" / "science-review" / "quality.json", ("review-task-v1", "review-response-v1", "review-receipt-v2"))

    update_index(
        ROOT / "skills" / "codex-science" / "references" / "index.json",
        {
            "id": "authenticated-connector-packs",
            "path": "references/authenticated-connector-packs.md",
            "purpose": "Approval-gated optional connector packs with out-of-band credentials, preview, scopes, idempotency, concurrency, and before/after receipts.",
            "read_when": ["before installing or designing an authenticated connector pack", "before previewing or executing a provider write", "before transferring sensitive data to an external service"],
            "required_before": ["issuing a connector action approval", "executing through ConnectorActionAdapter", "claiming a provider write integration is safe"],
            "search_patterns": ["## Action spec", "## Provider preview", "## Approval", "## Execute through an optional pack", "## Failure handling"],
            "authority": "Codex Science first-party optional connector contract",
            "version": "1",
            "evidence_boundary": "The framework standardizes action safety; it does not supply credentials, provider implementations, or compliance certification."
        },
    )
    add_route(
        ROOT / "skills" / "codex-science" / "SKILL.md",
        "references/authenticated-connector-packs.md",
        "Before designing, installing, approving, or using an authenticated or write-capable provider connector, **MUST** read [the optional connector pack contract](references/authenticated-connector-packs.md). Credentials stay out of band; every write requires a hash-bound preview, exact scopes, idempotency key, fresh before-state check, explicit approval, and before/after receipt.",
        anchor="## Workflow",
    )
    add_quality(ROOT / "skills" / "codex-science" / "quality.json", ("connector-action-spec-v1", "connector-action-preview-v1", "connector-action-approval-v1", "connector-action-receipt-v1"))


def patch_docs() -> None:
    quickstart = ROOT / "docs" / "NATIVE_RUNTIME_QUICKSTART.md"
    text = quickstart.read_text(encoding="utf-8")
    if "## 6. Prepare an independent review packet" not in text:
        text = text.rstrip() + '''

## 6. Prepare an independent review packet

Read `skills/science-review/references/independent-review-runtime.md`, then use `scripts/science_reviewer.py prepare` and `finalize`. A producer second pass is not independent, and reproduction requires a separate execution.
'''
    if "## 7. Validate an authenticated connector action" not in text:
        text = text.rstrip() + '''

## 7. Validate an authenticated connector action

Read `skills/codex-science/references/authenticated-connector-packs.md`. Use `scripts/connector_action_contract.py` for spec, preview, and approval validation. Provider execution belongs to an optional adapter pack; credentials never enter the action JSON.
'''
    quickstart.write_text(text, encoding="utf-8")


def main() -> int:
    patch_reviewer()
    patch_action_framework()
    patch_references()
    patch_docs()
    print("review and action runtime integration: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
