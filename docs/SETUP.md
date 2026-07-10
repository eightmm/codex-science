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

The installer clones into `~/.codex-science` (override with `CODEX_SCIENCE_HOME`), runs the light bootstrap, and registers the plugin. Re-run it any time to update.

Then start a new Codex task in any project and say `Start Codex Science` or `Codex Science 시작`. You do not install per project — the plugin is user-global in `~/.codex`.

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
