#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.model_registry_v2 import registry_sha256, validate_model_receipt_v2, validate_registry_v2  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry-v2.json")
    parser.add_argument("--receipt", action="append", default=[])
    parser.add_argument("--current-revisions", type=Path)
    args = parser.parse_args()
    if args.current_revisions is not None and not args.receipt:
        parser.error("--current-revisions requires at least one --receipt")
    try:
        payload = json.loads(args.registry.read_text(encoding="utf-8"))
        models = validate_registry_v2(payload)
        if not args.receipt:
            print(f"model registry v2: valid ({len(models)} models, sha256={registry_sha256(payload)})")
            return 0
        current_revisions = None
        if args.current_revisions is not None:
            current_revisions = json.loads(args.current_revisions.read_text(encoding="utf-8"))
            if not isinstance(current_revisions, dict):
                raise ValueError("current revisions JSON must be an object")
        findings = []
        for receipt_path in args.receipt:
            receipt = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
            if not isinstance(receipt, dict):
                raise ValueError(f"receipt must be a JSON object: {receipt_path}")
            findings.extend(
                {**finding, "receipt": receipt_path}
                for finding in validate_model_receipt_v2(receipt, payload, current_revisions=current_revisions)
            )
        for finding in findings:
            print(json.dumps(finding, sort_keys=True))
        return 1 if findings else 0
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
if __name__ == "__main__": raise SystemExit(main())
