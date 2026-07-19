#!/usr/bin/env python3
"""Managed-update entry point that strengthens the stable updater transaction."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATER = ROOT / "scripts" / "science_update_hook.py"
spec = importlib.util.spec_from_file_location("codex_science_stable_updater", UPDATER)
if spec is None or spec.loader is None:
    raise SystemExit("could not load stable Codex Science updater")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
_original_candidate_self_check = module._candidate_self_check


def strict_candidate_self_check(candidate: Path) -> bool:
    candidate = candidate.resolve()
    if not _original_candidate_self_check(candidate):
        return False
    contract = module._run(
        [
            "python3",
            str(candidate / "scripts" / "candidate_contract_check.py"),
            "--root",
            str(candidate),
        ],
        timeout=300,
    )
    return contract.returncode == 0 and "candidate contract: ok" in contract.stdout


module._candidate_self_check = strict_candidate_self_check

if __name__ == "__main__":
    raise SystemExit(module.main())
