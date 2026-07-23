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
`~/.codex-science`, runs the light bootstrap, and registers the plugin. Re-runs
use the locked transactional updater. `CODEX_SCIENCE_HOME` overrides the path.
`CODEX_SCIENCE_PYTHON` can select an existing Python 3.11+ interpreter, and
`CODEX_SCIENCE_RUNTIME_FILE` can override the interpreter record path.
This managed checkout is the only supported installation source. If the
`codex-science` marketplace still points at an older local development checkout,
the installer transactionally migrates it to the managed checkout.

Then start a new Codex task in any project, open `/hooks`, and trust the Codex
Science `SessionStart`, `UserPromptSubmit`, and `Stop` hooks. Say
`Start Codex Science` or `Codex Science 시작`. You do not install per project —
the plugin is user-global in `~/.codex`. Hook definitions are the human security
boundary; review them again after an update that changes them.

Verify registration with `codex plugin list`; the
`codex-science@codex-science` row should be `installed, enabled`.

The activation marker path is a SHA-256 hash of Codex's `session_id`, and the
marker content is a random generation. The checkpoint owner key is derived from
the session ID plus that generation. Raw session IDs, prompts, research inputs,
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

Update checks default to `CODEX_SCIENCE_AUTO_UPDATE=notify`. A `SessionStart`
hook checks the official GitHub `main` branch at most once per 24 hours and stores
only the check time and public commit IDs under `PLUGIN_DATA`. Say
`Codex Science 업데이트` to stage and apply the exact advertised commit. There
is no unattended apply mode. Updates affect only a new task; the current task's
loaded cache and older version caches are preserved so open tasks retain their
pinned hook paths. Set the mode to `off` to disable checks.
Without a fresh notice, the first explicit request advertises the exact commit;
repeat it once to approve that commit.

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
