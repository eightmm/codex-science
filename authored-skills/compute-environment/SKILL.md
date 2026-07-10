---
name: compute-environment
description: Build an isolated, reproducible compute environment with uv and actually run scientific code in it — install pinned packages, run analysis or modeling, and execute a tool end-to-end (not just query data). Use whenever a task needs to install packages or run code. Records the exact environment for reproducibility.
license: Apache-2.0
---

# Compute Environment and Execution (Codex-native)

Give the workflow a real, isolated environment and run work in it — the missing
step between "found the right method" and "produced the result". Standardized on
**`uv`**: fast, isolated, reproducible, and no global/system pollution.

## Gates — ask once, then run to completion

Building an environment and executing code crosses the project's safety gates.
Ask the user **once**, up front, with the concrete plan (which tool, expected
download size, whether a GPU is needed, and any network host), then proceed
autonomously through the rest — do not re-ask between steps.

- **Install / download**: package installation and model-weight downloads (often
  multiple GB) need approval once.
- **Compute**: long or GPU/remote compute needs approval once; state the rough
  cost/time.
- **Network**: name any host contacted (package index, weight host, MSA server).
- **Data**: never send proprietary or sensitive input to a public/third-party
  service without explicit approval.

## Workflow (uv)

1. Confirm the tool, exact version, and hardware need; get the one-time gate
   approval above.
2. Create an isolated environment scoped to the run:
   ```bash
   uv venv "<run_dir>/.venv"
   uv pip install --python "<run_dir>/.venv" "<package>==<version>"
   ```
   Always **pin versions**. Never `pip install` into or modify the system/global
   Python; never run bare `python3` for the work — use `uv run`.
3. Smoke-test first: run the tool `--help` or a tiny input via
   `uv run --python "<run_dir>/.venv" <cmd>` to confirm the env works.
4. Execute the real job with `uv run`; capture stdout/stderr, exit code, and
   outputs under `artifacts/<run-id>/`. Prefer a CPU-safe path; use GPU only if
   available and needed.
5. **Capture the environment** for reproducibility:
   `uv pip freeze --python "<run_dir>/.venv"` plus tool version, hardware, seeds,
   and key env vars — save it with `$science-provenance`.
6. On failure, diagnose and retry within the approved plan (persistence); only
   return to the user for a new gate or a genuine fork.
7. Review results with `$science-review` before presenting.

## Boundaries

- `uv` only. Do not modify the user's global/base environment or system
  packages; keep everything in the run's `.venv`.
- Pin versions and record them; an unpinned "latest" is not reproducible.
- A genuinely conda-only tool (system/bioconda deps with no PyPI wheel) is an
  exception — surface it and let the user decide rather than silently reaching
  for conda.
- Report hardware (CPU/GPU), wall-clock, and any nondeterminism (seeds). Do not
  upload private data to public services without explicit approval.
