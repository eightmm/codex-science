#!/usr/bin/env python3
"""Integrate independent reviewer packet runtime into progressive skill references."""

from __future__ import annotations

import json
import subprocess
import sys
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


def add_skill_route(path: Path, marker: str, paragraph: str) -> None:
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
        anchor = "## Review workflow"
        if anchor not in text:
            raise SystemExit(f"cannot insert reviewer reference route: {path}")
        text = text.replace(anchor, f"## Reference usage\n\n{paragraph}\n\n{anchor}", 1)
    path.write_text(text, encoding="utf-8")


def patch_redaction() -> None:
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
                    (key, "[REDACTED]" if any(fragment in key.lower() for fragment in SENSITIVE_FRAGMENTS) else item)
                    for key, item in query
                ]
                return urllib.parse.urlunsplit(
                    (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
                )
        except ValueError:
            return "[REDACTED-INVALID-URL]"
    return value
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "REDACTED-INVALID-URL" not in text:
        raise SystemExit("reviewer redaction marker is missing")
    old_modes = '''    response_modes = sorted({_text(item, "response review mode") for item in response.get("review_modes", [])})
'''
    new_modes = '''    response_modes_raw = response.get("review_modes", [])
    if not isinstance(response_modes_raw, list):
        raise ValueError("response review_modes must be a list")
    response_modes = sorted({_text(item, "response review mode") for item in response_modes_raw})
'''
    if old_modes in text:
        text = text.replace(old_modes, new_modes, 1)
    old_claims = '''    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in response.get("reviewed_claim_ids", [])})
'''
    new_claims = '''    reviewed_claims_raw = response.get("reviewed_claim_ids", [])
    if not isinstance(reviewed_claims_raw, list):
        raise ValueError("reviewed_claim_ids must be a list")
    reviewed_claims = sorted({_text(item, "reviewed claim ID") for item in reviewed_claims_raw})
'''
    if old_claims in text:
        text = text.replace(old_claims, new_claims, 1)
    path.write_text(text, encoding="utf-8")


def patch_reference_and_quality() -> None:
    update_index(
        ROOT / "skills" / "science-review" / "references" / "index.json",
        {
            "id": "independent-review-runtime",
            "path": "references/independent-review-runtime.md",
            "purpose": "Prepare blinded, hash-bound review packets and validate separate reviewer responses without exposing producer-only rationale.",
            "read_when": ["before handing a run to a separate reviewer", "before accepting a reviewer response", "before calling a review independent or reproduced"],
            "required_before": ["calling scripts/science_reviewer.py", "attaching a packet-derived review receipt to a run"],
            "search_patterns": ["## Independence boundary", "## Prepare a review packet", "## Reviewer response contract", "## Reproduction mode", "## Failure handling"],
            "authority": "Codex Science first-party review packet contract",
            "version": "1",
            "evidence_boundary": "The runtime standardizes packet and receipt coverage but does not authenticate reviewer identity or guarantee independence."
        },
    )
    add_skill_route(
        ROOT / "skills" / "science-review" / "SKILL.md",
        "references/independent-review-runtime.md",
        "Before preparing a separate human or agent review, accepting a response, or claiming independence or reproduction, **MUST** read [the independent reviewer packet contract](references/independent-review-runtime.md). Use `scripts/science_reviewer.py` to bind the packet to source manifest and artifact hashes; do not expose producer-only rationale or transfer a response to changed bytes.",
    )
    quality = ROOT / "skills" / "science-review" / "quality.json"
    payload = json.loads(quality.read_text(encoding="utf-8"))
    outputs = payload.setdefault("output_schemas", [])
    for value in ("review-task-v1", "review-response-v1", "review-receipt-v2"):
        if value not in outputs:
            outputs.append(value)
    outputs.sort()
    write_json(quality, payload)
    quickstart = ROOT / "docs" / "NATIVE_RUNTIME_QUICKSTART.md"
    text = quickstart.read_text(encoding="utf-8")
    marker = "## 6. Prepare an independent review packet"
    if marker not in text:
        quickstart.write_text(text.rstrip() + '''

## 6. Prepare an independent review packet

Read `skills/science-review/references/independent-review-runtime.md`, then use `scripts/science_reviewer.py prepare` to create a hash-bound packet and `finalize` to validate a separate response. A second pass by the producer must use `independent: false`; reproduction requires a separate execution.
''', encoding="utf-8")


def main() -> int:
    patch_redaction()
    patch_reference_and_quality()
    subprocess.run([sys.executable, "-m", "compileall", "-q", "src", "scripts"], cwd=ROOT, check=True)
    print("reviewer runtime integration: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
