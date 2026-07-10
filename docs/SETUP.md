# Setup

## Requirements

- Codex app or CLI with plugin support.
- Git with submodule support.
- Python 3.11 or later.
- `uv`.

## Install

```bash
git clone --recurse-submodules https://github.com/eightmm/codex-science.git
cd codex-science
./scripts/bootstrap.sh
codex plugin marketplace add "$PWD"
codex plugin add codex-science@codex-science
```

Start a new Codex task after installation. Say `Start Codex Science` or `Codex Science 시작` once to activate it for that task. The plugin cache is refreshed only on install or reinstall.

## Verify

```bash
./scripts/check.sh fast
./scripts/check.sh public
```

The public check performs live read-only requests. No credential is required.
