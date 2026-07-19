#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

MODE="${1:-fast}"

run_compile() {
  uv run python -m compileall -q src scripts
  echo "compile: ok"
}

run_tests() {
  uv run python -m unittest discover -s tests
  echo "unit tests: ok"
}

run_inventory() {
  local tmp
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' RETURN
  uv run python scripts/audit_skills.py --output "$tmp" >/dev/null
  cmp catalog/inventory.json "$tmp"
  echo "inventory determinism: ok"
}

run_wrappers() {
  uv run python scripts/generate_wrappers.py --check
}

run_science_contracts() {
  local review_tmp diff_tmp
  review_tmp="$(mktemp)"
  diff_tmp="$(mktemp)"
  trap 'rm -f "$review_tmp" "$diff_tmp"' RETURN
  uv run python scripts/validate_models.py
  uv run python scripts/validate_artifact.py \
    examples/literature-review-reviewed-run/manifest.json \
    --review-output "$review_tmp" \
    --require-passed-review
  uv run python scripts/diff_literature_review.py \
    examples/literature-review-reviewed-run/snapshot.previous.json \
    examples/literature-review-reviewed-run/snapshot.current.json \
    --output "$diff_tmp"
  cmp examples/literature-review-reviewed-run/snapshot.diff.json "$diff_tmp"
  uv run python scripts/audit_sbdd_benchmark.py examples/sbdd-acceptance/benchmark.json >/dev/null
  echo "scientific contracts: ok"
}

run_skill_validation() {
  local sys_skills validate_plugin quick_validate skill_count skill output
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
        return 1
      fi
      skill_count=$((skill_count + 1))
    done
    echo "skill validation: ok ($skill_count skills)"
  else
    echo "check: skipping Codex skill validation (system skills not found at $sys_skills)"
  fi
}

run_fast() {
  run_compile
  run_tests
  run_inventory
  run_wrappers
  run_science_contracts
  run_skill_validation
  echo "check fast: ok"
}

case "$MODE" in
  fast) run_fast ;;
  compile) run_compile ;;
  tests) run_tests ;;
  inventory) run_inventory ;;
  wrappers) run_wrappers ;;
  contracts) run_science_contracts ;;
  skills) run_skill_validation ;;
  public) uv run python scripts/public_smoke.py ;;
  doctor) bash scripts/doctor.sh ;;
  *)
    echo "usage: scripts/check.sh [fast|compile|tests|inventory|wrappers|contracts|skills|public|doctor]" >&2
    exit 2
    ;;
esac
