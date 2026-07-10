#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Light installer: the catalog, wrappers, and inventory are committed, and the
# runtime is pure Python stdlib, so installing only needs a compatible
# interpreter plus the pinned upstream instructions (shallow submodule).
# For development verification (regeneration, tests, doctor) use scripts/check.sh.

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"error: Python 3.11+ required, found {sys.version.split()[0]}")
print(f"python {sys.version.split()[0]} ok")
PY

# Upstream skill instructions live in a pinned submodule. Shallow-fetch it so
# selected skills can show their upstream text without downloading full history.
git submodule update --init --recursive --depth 1 vendor/scientific-agent-skills

cat <<'EOF'
bootstrap: ok

Register the plugin with Codex:
  codex plugin marketplace add "$PWD"
  codex plugin add codex-science@codex-science

Then start a new Codex task, review/trust the plugin hooks with /hooks, and say
"Start Codex Science". The mode will self-invoke on later turns in that task.
Developers can verify the checkout with: ./scripts/check.sh fast
EOF
