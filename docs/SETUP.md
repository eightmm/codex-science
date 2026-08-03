# Setup

## Requirements

- Codex app or CLI with plugin support.
- `curl` for the recommended one-command install.
- Git.
- Either `uv` or Python 3.11 or later.

The runtime is pure Python standard library — no packages to install. The
installer prefers `uv`: it provisions a managed Python 3.12 interpreter once
and records its absolute path in `~/.codex-science-python`. Hooks and the MCP
server execute that interpreter directly rather than running `uv` for every
event. Without `uv`, an existing compatible `python3` is used. A host whose
default Python is 3.8 therefore needs `uv` before running the installer.

## Install (recommended)

Install once; it registers globally with Codex and applies to every project:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

The installer validates a fresh clone in staging before moving it into
`~/.codex-science`, runs the light bootstrap, registers the stable host plugin,
and prepares an immutable scientific runtime in Codex Science's private plugin
data. `CODEX_SCIENCE_HOME` overrides the managed-checkout path.
`CODEX_SCIENCE_PYTHON` can select an existing Python 3.11+ interpreter, and
`CODEX_SCIENCE_RUNTIME_FILE` can override the interpreter record path.

An existing installation requires an explicit migration only when its
host-loaded bootstrap must change. Close every Codex task and quit the Codex app,
then run:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | CODEX_SCIENCE_MIGRATION_ACK=all-codex-tasks-closed bash
```

The acknowledgement is an assertion by the user, not a process-killing option;
never set it while Codex is open. Codex registration can prune an old host cache,
including one still referenced by an inactive open task. The installer also uses
this guarded transaction to migrate a marketplace that points at an older local
development checkout. Routine scientific-runtime updates are automatic after
the host bootstrap is installed and do not use Codex's plugin CLI.

Then start a new Codex task in any project, open `/hooks`, and trust the Codex
Science `SessionStart`, `UserPromptSubmit`, and `Stop` hooks. Say
`Start Codex Science` or `Codex Science 시작`. You do not install per project —
the plugin is user-global in `~/.codex`. Hook definitions are the human security
boundary. Ordinary runtime updates keep the bootstrap definition stable; review
them again only if that definition changes.

Verify registration with `codex plugin list`; the
`codex-science@codex-science` row should be `installed, enabled`.

The activation marker path is a SHA-256 hash of Codex's `session_id`, and the
marker contains a random generation plus the public version, commit, and receipt
digest of its private immutable runtime pin. The checkpoint owner key is derived
from the session ID plus that generation. Raw session IDs, prompts, research inputs,
credentials, and results are not stored in the marker. Later turns, resume, and
context compaction retain the generation. Explicit stop or `clear` abandons the
discoverable owned nonterminal run and removes the marker; reactivation rotates
the generation and owner key, so an old run cannot regain the guard even if its
artifact was not discoverable during deactivation. Inactive markers expire after
180 days.

The `Stop` hook warns when the owned checkpoint is `active` but allows the turn
to end by default. This avoids openai/codex#20783, where a blocking continuation
can poison the next API request with a local UUID. Approval gates, genuine
blockers, and `waiting_external` end without that warning. An external wait
records a poll interval and terminal rule so Codex does not busy-poll.
`CODEX_SCIENCE_STOP_MODE=block` is retained only for compatibility testing after
the installed Codex includes the upstream fix; its legacy path has a default
absolute continuation budget of 100 plus the no-progress safety limit.

Native Goal mode is optional and must be requested explicitly with `/goal`.
Hooks cannot call or observe Goal tools; the coordinator uses `get_goal` during
automatic continuations. A native Goal run completes in this order:

1. Complete every planned checkpoint step.
2. Satisfy every schema-v4 criterion with existing run-local evidence.
3. Record a passed JSON review receipt that names the reviewer and attests independence.
4. Run checkpoint `complete`, which enters `completion_pending`.
5. Call `update_goal` with `complete`.
6. Save a run-local Goal receipt from the successful host result and run
   checkpoint `confirm-goal-complete --receipt <path>`.

Do not enable another generic or Ralph-style `Stop` loop in the same task.
Competing stop guards can keep each other alive.

Neither Goal nor the Stop hook runs after the Codex app or task is closed. They
do not bypass hook trust, permissions, approvals, or host availability.

Update checks default to `CODEX_SCIENCE_AUTO_UPDATE=apply`. The stable bootstrap
checks the official GitHub `main` branch at `SessionStart` and on the first
activation when needed. Before candidate code runs, the updater rejects a
bootstrap-byte or bootstrap-policy change and a non-monotonic runtime version.
It then performs only the bounded MCP discovery handshake, requires that
contract to match the host, and runs the full candidate gate. A verified
compatible candidate is installed append-only at
`$CODEX_HOME/plugins/data/codex-science-codex-science/runtime-cache/<runtime_version>`
with a bounded receipt. This store belongs to Codex Science and is not a Codex
host cache.

Automatic and ordinary explicit runtime updates never call `codex plugin` or
modify Codex plugin registration. First activation pins the runtime version,
commit, and receipt across hook, Stop, skill, and MCP boundaries. An explicit
update in an active task installs for new activations without switching the
current run. Durable checkpoint and manifest writes record runtime identity;
version-spanning state is a defensive legacy/recovery warning. A candidate that
changes the host bootstrap is rejected with instructions for the acknowledged
curl migration. Codex's displayed plugin version identifies the stable host
bootstrap, not the independently advancing scientific runtime.

| Mode | Automatic lifecycle check | `Codex Science 업데이트` |
| --- | --- | --- |
| `apply` (default) | Verify and apply | Verify and apply |
| `notify` | Report only | Verify and apply |
| `off` | Skip | Verify and apply |

Offline access, a busy updater, a dirty or unofficial checkout, diverged history,
or failed validation leaves the last-known-good verified runtime active. Re-run
the curl installer only when a bootstrap migration or repair is requested, and
use the acknowledgement only after closing every Codex task and the app.

## Development checkout

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
./scripts/check.sh fast
```

Do not register this checkout as a marketplace. Development happens here, while
the curl installer owns the runnable `~/.codex-science` checkout and global
marketplace registration. `bootstrap.sh` verifies the Python version and
shallow-fetches the pinned upstream skills submodule; `--recurse-submodules` at
clone time is not required. The one-command installer additionally exercises the
MCP server, generation-derived activation key, a temporary schema-v4 checkpoint,
the opt-in active-run Stop rejection path, external-wait Stop allowance, and the
update lifecycle before reporting success.

## Verify

Development checks also require `uv`:

```bash
./scripts/check.sh fast
./scripts/check.sh public
```

The public check performs live read-only requests. No credential is required.
