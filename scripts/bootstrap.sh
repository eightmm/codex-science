#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Light installer: committed catalog/wrappers plus a compatible interpreter and
# the pinned upstream skill submodule. The deterministic candidate contract is
# also exercised so fresh installs and managed updates use the same safety gate.

"$PWD/scripts/python_runtime.sh" - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"error: Python 3.11+ required, found {sys.version.split()[0]}")
print(f"python {sys.version.split()[0]} ok")
PY

git submodule update --init --recursive --depth 1 vendor/scientific-agent-skills
"$PWD/scripts/python_runtime.sh" scripts/candidate_contract_check.py --root "$PWD"

cat <<'EOF'
bootstrap: ok

The managed installer performs plugin registration after this validation step.
Do not register a development checkout as a second marketplace source.
Developers can verify the checkout with: ./scripts/check.sh fast
EOF
