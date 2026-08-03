#!/usr/bin/env bash
# Codex Science one-command installer.
#
#   curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
#
# Installs once into a shared location and registers the plugin globally with
# Codex. Re-run any time to update. After install, use it in ANY project by
# starting a new Codex task and saying "Start Codex Science".
set -euo pipefail

INSTALL_DIR="${CODEX_SCIENCE_HOME:-$HOME/.codex-science}"
OFFICIAL_REPO="https://github.com/eightmm/codex-science.git"
REPO_URL="$OFFICIAL_REPO"
BRANCH="main"
RUNNING_INSTALLER="${BASH_SOURCE[0]:-}"
RUNNING_INSTALLER_SHA256=""
HANDOFF_COUNT="${CODEX_SCIENCE_INSTALLER_HANDOFF_COUNT:-0}"
RUNTIME_FILE="${CODEX_SCIENCE_RUNTIME_FILE:-$HOME/.codex-science-python}"
PYTHON=""

info() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; }

if [ -n "${CODEX_SCIENCE_REPO:-}" ] && [ "$CODEX_SCIENCE_REPO" != "$OFFICIAL_REPO" ]; then
  err "CODEX_SCIENCE_REPO overrides are not accepted by the managed installer"
  exit 1
fi
if [ -n "${CODEX_SCIENCE_REF:-}" ] && [ "$CODEX_SCIENCE_REF" != "main" ]; then
  err "CODEX_SCIENCE_REF overrides are not accepted; managed installs track main"
  exit 1
fi

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
RECOVERY_DIR=""
UPDATE_HOOK=""
cleanup() {
  if [ -n "$HOOK_DATA" ]; then rm -rf "$HOOK_DATA"; fi
  if [ -n "$RECOVERY_DIR" ]; then rm -rf "$RECOVERY_DIR"; fi
  if [ -n "$STAGING" ]; then rm -rf "$STAGING"; fi
  if [ -n "$LOCKER_PID" ]; then
    kill "$LOCKER_PID" 2>/dev/null || true
    wait "$LOCKER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

managed_updater_is_trusted() {
  [ -d "$INSTALL_DIR/.git" ] || return 1
  remote="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null || true)"
  case "${remote%/}" in
    https://github.com/eightmm/codex-science.git|https://github.com/eightmm/codex-science|git@github.com:eightmm/codex-science.git|ssh://git@github.com/eightmm/codex-science.git) ;;
    *) return 1 ;;
  esac
  [ -z "$(git -C "$INSTALL_DIR" status --porcelain --untracked-files=normal 2>/dev/null)" ] \
    || return 1
  head="$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true)"
  tracking="$(git -C "$INSTALL_DIR" rev-parse refs/remotes/origin/main 2>/dev/null || true)"
  [ "${#head}" -eq 40 ] || return 1
  case "$head" in *[!0-9a-f]*) return 1 ;; esac
  [ "$head" = "$tracking" ]
}

select_trusted_updater() {
  command -v curl >/dev/null || {
    err "curl is required to load the trusted main-branch update helper"
    exit 1
  }
  RECOVERY_COMMIT="$(git ls-remote --heads "$OFFICIAL_REPO" refs/heads/main 2>/dev/null | awk 'NR == 1 {print $1}')"
  if [ "${#RECOVERY_COMMIT}" -ne 40 ]; then
    err "could not resolve the official main commit"
    exit 1
  fi
  case "$RECOVERY_COMMIT" in
    *[!0-9a-f]*) err "official main returned an invalid commit"; exit 1 ;;
  esac

  if managed_updater_is_trusted \
    && [ "$(git -C "$INSTALL_DIR" rev-parse HEAD 2>/dev/null || true)" = "$RECOVERY_COMMIT" ]
  then
    if [ -f "$INSTALL_DIR/scripts/science_update_entry.py" ]; then
      UPDATE_HOOK="$INSTALL_DIR/scripts/science_update_entry.py"
    else
      UPDATE_HOOK="$INSTALL_DIR/scripts/science_update_hook.py"
    fi
    if "$PYTHON" "$UPDATE_HOOK" --self-check >/dev/null 2>&1; then
      return
    fi
  fi

  info "Loading the verified main-branch update helper"
  RECOVERY_DIR="$(mktemp -d "${TMPDIR:-/tmp}/codex-science-update-helper.XXXXXX")"
  mkdir -p "$RECOVERY_DIR/scripts"
  RECOVERY_BASE="https://raw.githubusercontent.com/eightmm/codex-science/$RECOVERY_COMMIT/scripts"
  if ! curl -fsSL "$RECOVERY_BASE/science_update_hook.py" \
      -o "$RECOVERY_DIR/scripts/science_update_hook.py" \
    || ! curl -fsSL "$RECOVERY_BASE/science_update_entry.py" \
      -o "$RECOVERY_DIR/scripts/science_update_entry.py" \
    || ! curl -fsSL "$RECOVERY_BASE/science_runtime_state.py" \
      -o "$RECOVERY_DIR/scripts/science_runtime_state.py"; then
    err "could not download the trusted update helper"
    exit 1
  fi
  UPDATE_HOOK="$RECOVERY_DIR/scripts/science_update_entry.py"
  if ! "$PYTHON" "$UPDATE_HOOK" --self-check >/dev/null; then
    err "trusted update helper self-check failed"
    exit 1
  fi
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

case "$HANDOFF_COUNT" in
  0|1|2|3) ;;
  *) err "CODEX_SCIENCE_INSTALLER_HANDOFF_COUNT is invalid"; exit 1 ;;
esac
if [ -n "$RUNNING_INSTALLER" ] && [ -f "$RUNNING_INSTALLER" ]; then
  RUNNING_INSTALLER_SHA256="$(
    "$PYTHON" - "$RUNNING_INSTALLER" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
  )"
fi

if [ -d "$INSTALL_DIR/.git" ]; then
  select_trusted_updater
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
# newer implementation. Compare against the bytes captured before the checkout
# swap: the original path may now resolve to the replacement file even though
# this shell is still executing the old program. A bounded count permits a
# second handoff if main advances again during the first update.
MANAGED_INSTALLER_SHA256=""
if [ -f "$INSTALL_DIR/scripts/install.sh" ]; then
  MANAGED_INSTALLER_SHA256="$(
    "$PYTHON" - "$INSTALL_DIR/scripts/install.sh" <<'PY'
import hashlib
import sys
from pathlib import Path

print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
  )"
fi
if [ -n "$MANAGED_INSTALLER_SHA256" ] \
  && [ "$RUNNING_INSTALLER_SHA256" != "$MANAGED_INSTALLER_SHA256" ]
then
  if [ "$HANDOFF_COUNT" -ge 3 ]; then
    err "official main changed repeatedly during installer handoff; rerun the installer"
    exit 1
  fi
  info "Continuing with the installer from $INSTALL_DIR"
  cleanup
  trap - EXIT
  export CODEX_SCIENCE_INSTALLER_HANDOFF=1
  export CODEX_SCIENCE_INSTALLER_HANDOFF_COUNT="$((HANDOFF_COUNT + 1))"
  exec bash "$INSTALL_DIR/scripts/install.sh"
fi

# 2. Verify interpreter and fetch the pinned upstream skills (light bootstrap).
info "Running bootstrap"
"$INSTALL_DIR/scripts/bootstrap.sh"

# 3. Register the stable host bootstrap. The helper prepares the independent
# runtime store first and performs any Codex CLI mutation under its migration
# barrier.
info "Registering Codex plugin"
if "$PYTHON" "$INSTALL_DIR/scripts/science_update_hook.py" \
  --register-plugin "$INSTALL_DIR" >/dev/null
then
  info "Host bootstrap verified; private runtime ready"
else
  err "host bootstrap registration failed"
  exit 1
fi

# 4. Runtime self-check: confirm the live MCP proxy and unified hooks respond.
info "Verifying runtime"
if printf '%s\n%s\n' \
    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
    '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
    | CODEX_SCIENCE_HOME="$INSTALL_DIR" PLUGIN_ROOT="$INSTALL_DIR" \
      "$PYTHON" "$INSTALL_DIR/scripts/science_mcp_proxy.py" 2>/dev/null \
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
    "CODEX_SCIENCE_AUTO_UPDATE": "off",
    "CODEX_SCIENCE_HOME": str(root),
    "CODEX_SCIENCE_PLUGIN_DATA": str(plugin_data),
    "PLUGIN_DATA": str(plugin_data),
    "PLUGIN_ROOT": str(root),
    "CODEX_SCIENCE_STOP_MODE": "block",
}

sys.path.insert(0, str(root / "scripts"))
from science_runtime_state import install_runtime_append_only

runtime, runtime_reason = install_runtime_append_only(
    root,
    environment,
    plugin_data=plugin_data,
    repair_existing=True,
)
if runtime is None:
    raise SystemExit(f"private runtime preparation failed: {runtime_reason}")


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
    "science_hook_dispatch.py",
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

markers = [
    path
    for path in (plugin_data / "science-sessions").iterdir()
    if path.is_file() and re.fullmatch(r"[0-9a-f]{64}", path.name)
]
if len(markers) != 1:
    raise SystemExit("activation did not create exactly one marker")
marker = json.loads(markers[0].read_text(encoding="utf-8"))
generation = marker.get("generation")
if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{64}", generation):
    raise SystemExit("activation marker generation is invalid")
runtime_pin = marker.get("runtime_pin")
if marker.get("schema_version") != 2 or not isinstance(runtime_pin, dict):
    raise SystemExit("activation marker has no verified runtime pin")
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

active_stop = hook("science_hook_dispatch.py", "Stop")
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
if hook("science_hook_dispatch.py", "Stop").stdout.strip():
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

From this bootstrap release onward, a new task or first activation checks the
official main branch automatically. A verified compatible fast-forward is added
to Codex Science's private immutable runtime store without calling the Codex
plugin CLI. Before first activation it is pinned to that generation, so its
workflow and MCP runtime are used in the same task. An update requested after
activation is installed for new activations and does not repin the current run.
If the network or verification fails, Codex Science keeps the last verified
runtime and shows one short recovery message.

Routine runtime updates do not require this installer. If a later release asks
for a host-bootstrap migration, close every Codex task and quit the Codex app,
then run:
  curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | CODEX_SCIENCE_MIGRATION_ACK=all-codex-tasks-closed bash
Never set that acknowledgement while Codex is still open.
EOF
