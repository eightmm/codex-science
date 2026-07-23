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
RUNNING_INSTALLER="${BASH_SOURCE[0]:-}"
RUNTIME_FILE="${CODEX_SCIENCE_RUNTIME_FILE:-$HOME/.codex-science-python}"
PYTHON=""

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

command -v git >/dev/null || { err "git is required"; exit 1; }
command -v codex >/dev/null || { err "codex CLI not found; install Codex first"; exit 1; }

python_is_compatible() {
  [ -n "$1" ] \
    && [ -x "$1" ] \
    && "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1
}

record_python() {
  runtime_parent="$(dirname "$RUNTIME_FILE")"
  mkdir -p "$runtime_parent"
  if [ -L "$RUNTIME_FILE" ] || { [ -e "$RUNTIME_FILE" ] && [ ! -f "$RUNTIME_FILE" ]; }; then
    err "runtime interpreter record is unsafe: $RUNTIME_FILE"
    exit 1
  fi
  runtime_temporary="$(mktemp "$runtime_parent/.codex-science-python.XXXXXX")"
  chmod 600 "$runtime_temporary"
  printf '%s\n' "$PYTHON" > "$runtime_temporary"
  mv -f "$runtime_temporary" "$RUNTIME_FILE"
}

select_python() {
  requested="${CODEX_SCIENCE_PYTHON:-}"
  if [ -n "$requested" ]; then
    python_is_compatible "$requested" || {
      err "CODEX_SCIENCE_PYTHON must point to Python 3.11+"; exit 1;
    }
    PYTHON="$requested"
  elif [ -f "$RUNTIME_FILE" ] && [ ! -L "$RUNTIME_FILE" ]; then
    IFS= read -r recorded_python < "$RUNTIME_FILE" || recorded_python=""
    case "$recorded_python" in
      /*)
        if python_is_compatible "$recorded_python"; then
          PYTHON="$recorded_python"
        fi
        ;;
    esac
  fi

  if [ -z "$PYTHON" ] && command -v uv >/dev/null 2>&1; then
    managed_python="$(
      uv python find --managed-python --no-project --no-python-downloads 3.12 2>/dev/null \
        || true
    )"
    if ! python_is_compatible "$managed_python"; then
      info "Provisioning managed Python 3.12 with uv"
      if uv python install 3.12; then
        managed_python="$(uv python find --managed-python --no-project 3.12)"
      else
        managed_python=""
      fi
    fi
    if python_is_compatible "$managed_python"; then
      PYTHON="$managed_python"
    fi
  fi

  if [ -z "$PYTHON" ] && command -v python3 >/dev/null 2>&1; then
    system_python="$(command -v python3)"
    if python_is_compatible "$system_python"; then
      PYTHON="$system_python"
    fi
  fi
  if [ -z "$PYTHON" ]; then
    err "Python 3.11+ is required; install uv or set CODEX_SCIENCE_PYTHON"
    exit 1
  fi

  PYTHON="$(cd "$(dirname "$PYTHON")" && pwd)/$(basename "$PYTHON")"
  export CODEX_SCIENCE_PYTHON="$PYTHON"
  record_python
  info "Using $("$PYTHON" -c 'import sys; print(sys.executable)')"
}

STAGING=""
LOCKER_PID=""
HOOK_DATA=""
RECOVERY_HELPER=""
UPDATE_HOOK=""
cleanup() {
  if [ -n "$HOOK_DATA" ]; then rm -rf "$HOOK_DATA"; fi
  if [ -n "$RECOVERY_HELPER" ]; then rm -f "$RECOVERY_HELPER"; fi
  if [ -n "$STAGING" ]; then rm -rf "$STAGING"; fi
  if [ -n "$LOCKER_PID" ]; then
    kill "$LOCKER_PID" 2>/dev/null || true
    wait "$LOCKER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

repair_marketplace_for_legacy_updater() {
  UPDATE_HOOK="$INSTALL_DIR/scripts/science_update_hook.py"
  if "$PYTHON" "$INSTALL_DIR/scripts/science_update_hook.py" \
    --ensure-marketplace "$INSTALL_DIR" >/dev/null 2>&1
  then
    return
  fi

  command -v curl >/dev/null || {
    err "curl is required to recover a legacy Codex Science installation"
    exit 1
  }
  info "Repairing plugin marketplace before the legacy updater runs"
  RECOVERY_HELPER="$(mktemp "${TMPDIR:-/tmp}/codex-science-update-hook.XXXXXX")"
  RECOVERY_URL="https://raw.githubusercontent.com/eightmm/codex-science/$BRANCH/scripts/science_update_hook.py"
  if ! curl -fsSL "$RECOVERY_URL" -o "$RECOVERY_HELPER"; then
    err "could not download the marketplace recovery helper"
    exit 1
  fi
  if ! "$PYTHON" "$RECOVERY_HELPER" --self-check >/dev/null; then
    err "marketplace recovery helper self-check failed"
    exit 1
  fi
  if ! "$PYTHON" "$RECOVERY_HELPER" --ensure-marketplace "$INSTALL_DIR"; then
    err "legacy marketplace recovery failed"
    exit 1
  fi
  UPDATE_HOOK="$RECOVERY_HELPER"
}

# 1. Clone into staging or update through the transactional updater.
if [ ! -d "$INSTALL_DIR/.git" ]; then
  [ "$REPO_URL" = "$OFFICIAL_REPO" ] || {
    err "fresh installs accept only $OFFICIAL_REPO"; exit 1;
  }
  [ "$BRANCH" = "main" ] || { err "fresh installs accept only the main branch"; exit 1; }
  if [ -e "$INSTALL_DIR" ]; then
    err "$INSTALL_DIR already exists and is not a managed Git checkout"
    exit 1
  fi
fi
select_python

if [ -d "$INSTALL_DIR/.git" ]; then
  repair_marketplace_for_legacy_updater
  info "Safely updating $INSTALL_DIR"
  "$PYTHON" "$UPDATE_HOOK" \
    --manual-update "$INSTALL_DIR" "$BRANCH"
else
  INSTALL_PARENT="$(dirname "$INSTALL_DIR")"
  mkdir -p "$INSTALL_PARENT"
  LOCK_PATH="$INSTALL_PARENT/.codex-science-update.lock"
  coproc CODEX_SCIENCE_LOCKER {
    exec "$PYTHON" - "$LOCK_PATH" <<'PY'
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
  STAGING="$(mktemp -d "$INSTALL_PARENT/.codex-science-install.XXXXXX")"
  info "Cloning and validating in staging"
  git clone --quiet --branch "$BRANCH" --single-branch "$REPO_URL" "$STAGING/candidate"
  "$STAGING/candidate/scripts/bootstrap.sh"
  "$PYTHON" "$STAGING/candidate/scripts/science_update_hook.py" \
    --candidate-check "$STAGING/candidate"
  mv -T "$STAGING/candidate" "$INSTALL_DIR"
  rm -rf "$STAGING"
  STAGING=""
fi

# A streamed or older downloaded installer may have updated the checkout to a
# newer implementation. Continue with that implementation before taking any
# registration action, and use a marker to prevent recursive handoffs.
if [ "${CODEX_SCIENCE_INSTALLER_HANDOFF:-0}" != "1" ] \
  && [ -f "$INSTALL_DIR/scripts/install.sh" ] \
  && { [ -z "$RUNNING_INSTALLER" ] \
    || [ ! -f "$RUNNING_INSTALLER" ] \
    || ! cmp -s "$RUNNING_INSTALLER" "$INSTALL_DIR/scripts/install.sh"; }
then
  info "Continuing with the installer from $INSTALL_DIR"
  cleanup
  trap - EXIT
  export CODEX_SCIENCE_INSTALLER_HANDOFF=1
  exec bash "$INSTALL_DIR/scripts/install.sh"
fi

# 2. Verify interpreter and fetch the pinned upstream skills (light bootstrap).
info "Running bootstrap"
"$INSTALL_DIR/scripts/bootstrap.sh"

# 3. Register globally without deleting versions pinned by existing Codex tasks.
info "Registering Codex plugin"
if "$PYTHON" "$INSTALL_DIR/scripts/science_update_hook.py" \
  --ensure-marketplace "$INSTALL_DIR" >/dev/null
then
  info "Managed marketplace points to $INSTALL_DIR"
else
  err "managed marketplace registration failed"
  exit 1
fi
if "$PYTHON" "$INSTALL_DIR/scripts/science_update_hook.py" \
  --register-plugin "$INSTALL_DIR" >/dev/null
then
  info "Installed plugin cache verified; prior task caches preserved"
else
  err "installed plugin cache verification failed"
  exit 1
fi

# 4. Runtime self-check: confirm both the MCP server and session hook respond.
info "Verifying runtime"
if printf '%s\n%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
    | "$PYTHON" "$INSTALL_DIR/scripts/science_mcp.py" --inventory "$INSTALL_DIR/catalog/inventory.json" 2>/dev/null \
    | grep -q science_search_skills; then
  info "Runtime self-check passed"
else
  err "runtime self-check failed — the managed Python runtime did not respond"
  exit 1
fi

HOOK_DATA="$(mktemp -d)"
if PLUGIN_DATA="$HOOK_DATA" "$PYTHON" - "$INSTALL_DIR" "$HOOK_DATA" <<'PY'
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
plugin_data = Path(sys.argv[2])
workspace = plugin_data / "workspace"
run_dir = workspace / "artifacts" / "install-self-check"
workspace.mkdir()
session_id = "install-self-check"
environment = {
    **os.environ,
    "PLUGIN_DATA": str(plugin_data),
    "CODEX_SCIENCE_STOP_MODE": "block",
}


def hook(script: str, event: str, **extra: object) -> subprocess.CompletedProcess[str]:
    payload: dict[str, object] = {
        "cwd": str(workspace),
        "hook_event_name": event,
        "model": "self-check",
        "permission_mode": "default",
        "session_id": session_id,
        "transcript_path": None,
        "turn_id": "turn-1",
    }
    payload.update(extra)
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )
    if result.returncode:
        raise SystemExit(result.stderr or f"{script} failed")
    return result


activation = hook(
    "science_session_hook.py",
    "UserPromptSubmit",
    prompt="Start Codex Science",
)
output = json.loads(activation.stdout)
context = output["hookSpecificOutput"]["additionalContext"]
match = re.search(r"--session-key ([0-9a-f]{64})", context)
if match is None:
    raise SystemExit("activation did not emit an owner key")
owner_key = match.group(1)
goal_match = re.search(r"--goal-task-key ([0-9a-f]{64})", context)
if goal_match is None:
    raise SystemExit("activation did not emit a Goal task key")
goal_task_key = goal_match.group(1)
expected_goal_key = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
if goal_task_key != expected_goal_key:
    raise SystemExit("Goal task key is not bound to the Codex task")

markers = [path for path in plugin_data.rglob("*") if path.is_file()]
if len(markers) != 1:
    raise SystemExit("activation did not create exactly one marker")
marker = json.loads(markers[0].read_text(encoding="utf-8"))
generation = marker.get("generation")
if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{64}", generation):
    raise SystemExit("activation marker generation is invalid")
expected_key = hashlib.sha256(
    session_id.encode("utf-8") + b"\0" + generation.encode("ascii")
).hexdigest()
if owner_key != expected_key:
    raise SystemExit("owner key is not bound to session plus generation")

checkpoint = subprocess.run(
    [
        sys.executable,
        str(root / "scripts" / "science_checkpoint.py"),
        "init",
        str(run_dir),
        "--goal",
        "Exercise the installed Goal/loop contract",
        "--deliverable",
        "Temporary self-check artifact",
        "--done",
        "The active Stop guard is exercised",
        "--step",
        "work=Exercise the runtime",
        "--next-action",
        "Run the Stop hook",
        "--session-key",
        owner_key,
        "--outer-goal",
        "native",
        "--goal-task-key",
        goal_task_key,
    ],
    capture_output=True,
    text=True,
    env=environment,
    check=False,
)
if checkpoint.returncode:
    raise SystemExit(checkpoint.stderr or "checkpoint init failed")
checkpoint_data = json.loads(checkpoint.stdout)
if checkpoint_data.get("schema_version") != 4:
    raise SystemExit("checkpoint self-check did not create schema v4")
if checkpoint_data.get("outer_goal", {}).get("task_key") != goal_task_key:
    raise SystemExit("checkpoint Goal binding does not match the task key")

active_stop = hook("science_stop_hook.py", "Stop")
active_output = json.loads(active_stop.stdout)
if active_output.get("decision") != "block":
    raise SystemExit("active checkpoint did not block Stop")

waiting = subprocess.run(
    [
        sys.executable,
        str(root / "scripts" / "science_checkpoint.py"),
        "wait",
        str(run_dir),
        "--reason",
        "Self-check external wait",
        "--next-action",
        "Resume after the self-check interval",
        "--poll-interval-seconds",
        "1",
        "--terminal-rule",
        "Stop after one bounded status check",
    ],
    capture_output=True,
    text=True,
    env=environment,
    check=False,
)
if waiting.returncode:
    raise SystemExit(waiting.stderr or "checkpoint wait failed")
if hook("science_stop_hook.py", "Stop").stdout.strip():
    raise SystemExit("waiting_external checkpoint did not allow Stop")
PY
then
  info "Goal/loop runtime self-check passed"
else
  err "Goal/loop runtime self-check failed"
  exit 1
fi
rm -rf "$HOOK_DATA"
HOOK_DATA=""

if "$PYTHON" "$INSTALL_DIR/scripts/science_update_hook.py" --self-check >/dev/null 2>&1; then
  info "Update lifecycle self-check passed"
else
  err "update lifecycle self-check failed"
  exit 1
fi

cat <<EOF

Codex Science is installed at: $INSTALL_DIR

Use it in ANY project — start a new Codex task and say:
  Start Codex Science   (or: Codex Science 시작)

On first use, open /hooks and trust the Codex Science SessionStart,
UserPromptSubmit, and Stop hooks. The private activation marker stores a random
generation; prompts and research data are never stored. Do not enable another
generic Stop loop in the same task.

Update checks default to notify at most once every 24 hours. Say
"Codex Science 업데이트" to stage and install the exact advertised commit for
the next new Codex task. Unattended apply is intentionally unsupported.

Re-run this installer any time to update.
EOF
