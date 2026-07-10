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

  python3 /home/jaemin/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
  skill_count=0
  for skill in skills/* catalog/codex-skills/*; do
    [ -d "$skill" ] || continue
    if ! output="$(python3 /home/jaemin/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill")"; then
      echo "$skill: $output" >&2
      return 1
    fi
    skill_count=$((skill_count + 1))
  done
  echo "skill validation: ok ($skill_count skills)"
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
