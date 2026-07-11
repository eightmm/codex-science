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
OFFICIAL_REPO="https://github.com/eightmm/codex-science.git"

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

command -v git >/dev/null || { err "git is required"; exit 1; }
command -v python3 >/dev/null || { err "python3 (3.11+) is required"; exit 1; }
command -v codex >/dev/null || { err "codex CLI not found; install Codex first"; exit 1; }

STAGING=""
LOCKER_PID=""
HOOK_DATA=""
cleanup() {
  if [ -n "$HOOK_DATA" ]; then rm -rf "$HOOK_DATA"; fi
  if [ -n "$STAGING" ]; then rm -rf "$STAGING"; fi
  if [ -n "$LOCKER_PID" ]; then
    kill "$LOCKER_PID" 2>/dev/null || true
    wait "$LOCKER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

# 1. Clone into staging or update through the transactional updater.
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Safely updating $INSTALL_DIR"
  python3 "$INSTALL_DIR/scripts/science_update_hook.py" --manual-update "$INSTALL_DIR" "$BRANCH"
else
  [ "$REPO_URL" = "$OFFICIAL_REPO" ] || {
    err "fresh installs accept only $OFFICIAL_REPO"; exit 1;
  }
  [ "$BRANCH" = "main" ] || { err "fresh installs accept only the main branch"; exit 1; }
  INSTALL_PARENT="$(dirname "$INSTALL_DIR")"
  mkdir -p "$INSTALL_PARENT"
  LOCK_PATH="$INSTALL_PARENT/.codex-science-update.lock"
  coproc CODEX_SCIENCE_LOCKER {
    exec python3 - "$LOCK_PATH" <<'PY'
import fcntl
import os
import sys
import time

flags = os.O_CREAT | os.O_RDWR
if hasattr(os, "O_NOFOLLOW"):
    flags |= os.O_NOFOLLOW
try:
    descriptor = os.open(sys.argv[1], flags, 0o600)
    os.fchmod(descriptor, 0o600)
    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
except (OSError, BlockingIOError):
    print("rejected", flush=True)
    raise SystemExit(1)
print("locked", flush=True)
while True:
    time.sleep(60)
PY
  }
  LOCKER_PID="$CODEX_SCIENCE_LOCKER_PID"
  read -r LOCK_STATE <&"${CODEX_SCIENCE_LOCKER[0]}" || LOCK_STATE="rejected"
  if [ "$LOCK_STATE" != "locked" ]; then
    wait "$LOCKER_PID" 2>/dev/null || true
    err "another Codex Science install or update is running, or the lock path is unsafe"
    exit 1
  fi
  if [ -e "$INSTALL_DIR" ]; then
    err "$INSTALL_DIR already exists and is not a managed Git checkout"
    exit 1
  fi
  STAGING="$(mktemp -d "$INSTALL_PARENT/.codex-science-install.XXXXXX")"
  info "Cloning and validating in staging"
  git clone --quiet --branch "$BRANCH" --single-branch "$REPO_URL" "$STAGING/candidate"
  "$STAGING/candidate/scripts/bootstrap.sh"
  python3 "$STAGING/candidate/scripts/science_update_hook.py" \
    --candidate-check "$STAGING/candidate"
  mv -T "$STAGING/candidate" "$INSTALL_DIR"
  rm -rf "$STAGING"
  STAGING=""
fi

# 2. Verify interpreter and fetch the pinned upstream skills (light bootstrap).
info "Running bootstrap"
"$INSTALL_DIR/scripts/bootstrap.sh"

# 3. Register the plugin globally with Codex and fail if the cache is stale.
info "Registering Codex plugin"
codex plugin marketplace add "$INSTALL_DIR" >/dev/null
codex plugin add codex-science@codex-science >/dev/null
if python3 - "$INSTALL_DIR" <<'PY'
import importlib.util
import sys
from pathlib import Path

root = Path(sys.argv[1])
script = root / "scripts" / "science_update_hook.py"
spec = importlib.util.spec_from_file_location("science_update_hook", script)
if spec is None or spec.loader is None:
    raise SystemExit(1)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
raise SystemExit(0 if module._installed_cache_matches(root) else 1)
PY
then
  info "Installed plugin cache verified"
else
  err "installed plugin cache verification failed"
  exit 1
fi

# 4. Runtime self-check: confirm both the MCP server and session hook respond.
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

HOOK_DATA="$(mktemp -d)"
if printf '%s\n' \
    '{"cwd":".","hook_event_name":"UserPromptSubmit","model":"self-check","permission_mode":"default","prompt":"Start Codex Science","session_id":"install-self-check","transcript_path":null,"turn_id":"turn-1"}' \
    | PLUGIN_DATA="$HOOK_DATA" python3 "$INSTALL_DIR/scripts/science_session_hook.py" 2>/dev/null \
    | grep -q 'Codex Science is active'; then
  info "Session persistence self-check passed"
else
  err "session persistence self-check failed"
  exit 1
fi
rm -rf "$HOOK_DATA"
HOOK_DATA=""

if python3 "$INSTALL_DIR/scripts/science_update_hook.py" --self-check >/dev/null 2>&1; then
  info "Update lifecycle self-check passed"
else
  err "update lifecycle self-check failed"
  exit 1
fi

cat <<EOF

Codex Science is installed at: $INSTALL_DIR

Use it in ANY project — start a new Codex task and say:
  Start Codex Science   (or: Codex Science 시작)

On first use, open /hooks and trust the Codex Science SessionStart and
UserPromptSubmit hooks. They store only a hashed session marker under the
plugin data directory; prompts and research data are never stored.

Update checks default to notify at most once every 24 hours. Say
"Codex Science 업데이트" to stage and install the exact advertised commit for
the next new Codex task. Unattended apply is intentionally unsupported.

Re-run this installer any time to update.
EOF
