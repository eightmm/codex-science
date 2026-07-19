#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.model_registry_v2 import registry_sha256, validate_registry_v2  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=ROOT / "models" / "registry-v2.json")
    args = parser.parse_args()
    payload = json.loads(args.registry.read_text(encoding="utf-8"))
    models = validate_registry_v2(payload)
    print(f"model registry v2: valid ({len(models)} models, sha256={registry_sha256(payload)})")
    return 0
if __name__ == "__main__": raise SystemExit(main())
