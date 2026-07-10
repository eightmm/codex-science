#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

expected="$(python3 -c 'import json; print(json.load(open("catalog/source.json"))["commit"])')"
actual="$(git -C vendor/scientific-agent-skills rev-parse HEAD)"
if [ "$actual" != "$expected" ]; then
  echo "doctor: upstream commit mismatch: expected $expected, got $actual" >&2
  exit 1
fi

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
  for skill in skills/* catalog/codex-skills/*; do
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
