#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

python3 - <<'PY'
import json, subprocess, sys
from pathlib import Path

sources = json.loads(Path("catalog/sources.json").read_text())["sources"]
for src in sources:
    key, kind, path = src["key"], src.get("kind", ""), src["catalog_path"]
    root = Path(path).parent
    if kind == "submodule":
        actual = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        if actual != src["commit"]:
            sys.exit(f"doctor: {key} commit mismatch: expected {src['commit']}, got {actual}")
    elif not Path(path).is_dir():
        sys.exit(f"doctor: {key} vendored catalog missing at {path}")
print(f"source check: ok ({len(sources)} sources)")
PY

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
uv run python scripts/audit_skills.py --output "$tmp" >/dev/null
cmp catalog/inventory.json "$tmp"
uv run python scripts/generate_wrappers.py --check
uv run python -m unittest discover -s tests

sys_skills="${CODEX_HOME:-$HOME/.codex}/skills/.system"
validate_plugin="$sys_skills/plugin-creator/scripts/validate_plugin.py"
quick_validate="$sys_skills/skill-creator/scripts/quick_validate.py"
if [ -f "$validate_plugin" ] && [ -f "$quick_validate" ]; then
  python3 "$validate_plugin" .
  skill_count=0
  for skill in skills/* authored-skills/* catalog/codex-skills/*; do
    [ -d "$skill" ] || continue
    if ! output="$(python3 "$quick_validate" "$skill")"; then
      echo "$skill: $output" >&2
      exit 1
    fi
    skill_count=$((skill_count + 1))
  done
  echo "skill validation: ok ($skill_count skills)"
else
  echo "doctor: skipping Codex skill validation (system skills not found at $sys_skills)"
fi
echo "doctor: ok"
