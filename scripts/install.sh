#!/usr/bin/env bash
# Codex Science one-command installer.
#
#   curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
#
# Installs once into a shared location and registers the plugin globally with
# Codex. Re-run any time to update. After install, use it in ANY project by
# starting a new Codex task and saying "Start Codex Science".
set -euo pipefail

REPO_URL="${CODEX_SCIENCE_REPO:-https://github.com/eightmm/codex-science.git}"
INSTALL_DIR="${CODEX_SCIENCE_HOME:-$HOME/.codex-science}"
BRANCH="${CODEX_SCIENCE_REF:-main}"

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

command -v git >/dev/null || { err "git is required"; exit 1; }
command -v python3 >/dev/null || { err "python3 (3.11+) is required"; exit 1; }
command -v codex >/dev/null || { err "codex CLI not found; install Codex first"; exit 1; }

# 1. Clone or update a single shared checkout.
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Updating $INSTALL_DIR"
  git -C "$INSTALL_DIR" fetch --quiet origin "$BRANCH"
  git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
  git -C "$INSTALL_DIR" pull --quiet --ff-only origin "$BRANCH"
else
  info "Cloning into $INSTALL_DIR"
  git clone --quiet --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi

# 2. Verify interpreter and fetch the pinned upstream skills (light bootstrap).
info "Running bootstrap"
"$INSTALL_DIR/scripts/bootstrap.sh"

# 3. Register the plugin globally with Codex (idempotent; re-adds are no-ops).
info "Registering Codex plugin"
codex plugin marketplace add "$INSTALL_DIR" >/dev/null 2>&1 || true
codex plugin add codex-science@codex-science >/dev/null 2>&1 || true

# 4. Runtime self-check: the MCP server is pure stdlib, so a working python3 is
#    all it needs. Confirm it actually responds on this machine.
info "Verifying runtime"
if printf '%s\n%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
    | python3 "$INSTALL_DIR/scripts/science_mcp.py" --inventory "$INSTALL_DIR/catalog/inventory.json" 2>/dev/null \
    | grep -q science_search_skills; then
  info "Runtime self-check passed"
else
  err "runtime self-check failed — the MCP server did not respond; check python3 (3.11+)"
  exit 1
fi

cat <<EOF

Codex Science is installed at: $INSTALL_DIR

Use it in ANY project — start a new Codex task and say:
  Start Codex Science   (or: Codex Science 시작)

Re-run this installer any time to update.
EOF
