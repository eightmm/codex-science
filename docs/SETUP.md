# Setup

## Requirements

- Codex app or CLI with plugin support.
- Git.
- Python 3.11 or later.

The runtime is pure Python standard library — no packages to install. `uv` is only needed for the development checks below.

## Install

```bash
git clone https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

`bootstrap.sh` verifies the Python version and shallow-fetches the pinned upstream skills submodule; `--recurse-submodules` at clone time is not required. Start a new Codex task after installation. Say `Start Codex Science` or `Codex Science 시작` once to activate it for that task. The plugin cache is refreshed only on install or reinstall.

## Verify

Development checks require `uv`:

```bash
./scripts/check.sh fast
./scripts/check.sh public
```

The public check performs live read-only requests. No credential is required.
