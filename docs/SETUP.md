# Setup

## Requirements

- Codex app or CLI with plugin support.
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

Then start a new Codex task in any project, open `/hooks`, and trust the Codex Science `SessionStart` and `UserPromptSubmit` hooks. Say `Start Codex Science` or `Codex Science 시작`. You do not install per project — the plugin is user-global in `~/.codex`.

The hooks persist only a SHA-256 hash of Codex's `session_id` as an activation marker under `PLUGIN_DATA`. They do not store prompts, research inputs, credentials, or results. This keeps the coordinator active across later turns, resume, and context compaction; explicit stop, `clear`, and new tasks remain inactive. Abandoned markers expire after 180 days of inactivity.

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

`bootstrap.sh` verifies the Python version and shallow-fetches the pinned upstream skills submodule; `--recurse-submodules` at clone time is not required.

## Verify

Development checks require `uv`:

```bash
./scripts/check.sh fast
./scripts/check.sh public
```

The public check performs live read-only requests. No credential is required.
