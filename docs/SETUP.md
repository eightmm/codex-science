# Setup

## Requirements

- Codex app or CLI with plugin support.
- `curl` for the recommended one-command install.
- Git.
- Python 3.11 or later.

The runtime is pure Python standard library — no packages to install. `uv` is only needed for the development checks below.

## Install (recommended)

Install once; it registers globally with Codex and applies to every project:

```bash
curl -fsSL https://raw.githubusercontent.com/eightmm/codex-science/main/scripts/install.sh | bash
```

The installer validates a fresh clone in staging before moving it into
`~/.codex-science`, runs the light bootstrap, and registers the plugin. Re-runs
use the locked transactional updater. `CODEX_SCIENCE_HOME` overrides the path.

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

The `Stop` hook only rejects a stop while the owned checkpoint is `active`.
Approval gates, genuine blockers, and `waiting_external` allow the turn to end.
An external wait records a poll interval and terminal rule so Codex does not
busy-poll. Each run has a default absolute continuation budget of 100, in
addition to the no-progress safety limit.

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
loaded cache is preserved. Set the mode to `off` to disable checks.
Without a fresh notice, the first explicit request advertises the exact commit;
repeat it once to approve that commit.

## Install (manual / development)

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

`bootstrap.sh` verifies the Python version and shallow-fetches the pinned upstream skills submodule; `--recurse-submodules` at clone time is not required. The one-command installer additionally exercises the MCP server, generation-derived activation key, a temporary schema-v4 checkpoint, active-run Stop rejection, external-wait Stop allowance, and the update lifecycle before reporting success.

## Verify

Development checks require `uv`:

```bash
./scripts/check.sh fast
./scripts/check.sh public
```

The public check performs live read-only requests. No credential is required.
