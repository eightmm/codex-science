#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

MODE="${1:-fast}"

run_fast() {
  uv run python -m compileall -q src scripts
  uv run python -m unittest discover -s tests

  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' RETURN
  uv run python scripts/audit_skills.py --output "$tmp" >/dev/null
  cmp catalog/inventory.json "$tmp"
  uv run python scripts/generate_wrappers.py --check

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
        return 1
      fi
      skill_count=$((skill_count + 1))
    done
    echo "skill validation: ok ($skill_count skills)"
  else
    echo "check: skipping Codex skill validation (system skills not found at $sys_skills)"
  fi
  echo "check fast: ok"
}

case "$MODE" in
  fast) run_fast ;;
  public) uv run python scripts/public_smoke.py ;;
  doctor) bash scripts/doctor.sh ;;
  *)
    echo "usage: scripts/check.sh [fast|public|doctor]" >&2
    exit 2
    ;;
esac
