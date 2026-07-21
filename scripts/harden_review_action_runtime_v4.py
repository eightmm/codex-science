#!/usr/bin/env python3
"""Finalize canonical hashes and receipt validation for review/action runtimes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_reviewer() -> None:
    path = ROOT / "src" / "codex_science" / "reviewer_runtime.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "from codex_science.review_receipts import build_review_receipt, validate_review_receipt\n",
        "from codex_science.review_receipts import build_review_receipt, canonical_sha256, validate_review_receipt\n",
    )
    text = text.replace(
        '    receipt["fingerprint"] = _fingerprint(material)\n    validate_review_receipt(receipt)\n',
        '    receipt["fingerprint"] = canonical_sha256(material)\n    validate_review_receipt(receipt)\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_action() -> None:
    path = ROOT / "src" / "codex_science" / "action_connectors.py"
    text = path.read_text(encoding="utf-8")
    marker = '''    validate_preview(preview, spec)
    existing = ledger.get(spec.idempotency_key)
'''
    replacement = '''    validate_preview(preview, spec)
    if adapter.connector_name != spec.connector:
        raise ValueError("adapter connector does not match action spec")
    existing = ledger.get(spec.idempotency_key)
'''
    if marker in text:
        text = text.replace(marker, replacement, 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_reviewer()
    patch_action()
    print("review/action runtime hardening: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
