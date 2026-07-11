---
name: compute-environment
description: "Inspect and use the local computer as a reproducible scientific workbench across shell, Python, R, Julia, Jupyter, containers, CPUs, and GPUs. Use when a scientific task needs local files, code execution, package or environment setup, data conversion, visualization, notebooks, simulation, model inference, or hardware-aware execution rather than instructions alone, including a Julia notebook on a local GPU."
license: Apache-2.0
---

# Local Scientific Compute

Use the existing computer to produce a result, not merely a tutorial. Keep work
isolated, inspectable, and reproducible.

Resolve `<plugin-root>` as two directories above this `SKILL.md`. Load the
plugin's `$science-provenance` and `$science-review` core skills when their
schemas or review procedure are needed.

## Preflight

1. Resolve the project root from the current workspace or nearest version-control
   root. Inspect relevant inputs and storage needs without copying sensitive data.
2. Run `python3 <plugin-root>/scripts/compute_probe.py`
   for a read-only capability report. Save it under the run directory with
   `--output artifacts/<run-id>/compute-environment.json` once a run exists.
3. Select the smallest adequate backend:
   - shell or an existing executable for simple transformations;
   - an isolated Python, R, or Julia project for analysis;
   - Jupyter only when an inspectable notebook is a required deliverable;
   - a digest-pinned container for system dependencies or stronger isolation;
   - a GPU only when the method benefits materially and its memory need fits.
4. State inputs, outputs, expected runtime/disk, and the smallest smoke test.

## Project environment

Reuse a project's existing environment contract before creating anything:

- Python: honor `pyproject.toml`, `uv.lock`, and an existing project `.venv`;
  use `uv run --locked` when a lock exists, otherwise create an isolated run
  environment without changing global Python.
- R: honor `renv.lock` and the project library; record `sessionInfo()`.
- Julia: honor `Project.toml` and `Manifest.toml`; run with the matching project.
- Jupyter: bind the Jupyter kernel to the selected project environment and record
  the kernel/runtime identity with the executed notebook.
- Containers: honor a reviewed project container definition and pinned digest.

Do not silently rewrite a lockfile or mix environments from another project.
Request approval before adding dependencies or changing a project lock.

Read-only inspection and a small CPU calculation in an existing environment need
no extra gate. Any GPU workload beyond capability/version inspection requires the
approval packet below, as does package installation, a new network host or
container image, a large download, privileged container flags, heavy CPU work,
or sensitive-data movement. After approval, continue through reversible steps.

## One-time approval packet

Before gated work, present one approval packet containing the local target and
GPU selection; code/notebook path and hash; inputs and sensitivity; pinned
environment or image; smoke and full commands; package/download/network changes;
CPU/GPU/memory/time/disk envelope; output path; validation criterion; and the
cancellation and checkpoint plan. Approval applies only to that envelope.

For cancellation, identify the process launched by this run, request graceful
checkpoint/interrupt first, and never kill unrelated processes. Ask again when
the data boundary, environment, resource envelope, or method changes.

## Execute

1. Create `artifacts/<run-id>/`; hash inputs or record approved external paths.
2. Preserve the user's base environment:
   - Python: use a run-scoped `uv` environment and pin packages.
   - R: use a project library and record `sessionInfo()`; use `renv` when present.
   - Julia: activate a run-scoped project and preserve `Project.toml` and
     `Manifest.toml`.
   - Shell: save non-trivial commands in a script with `set -euo pipefail`.
   - Jupyter: save the notebook plus an exported script or executed cell log.
   - Container: pin the image by digest, mount only required paths, avoid
     privileged mode, and record the full invocation.
3. Run the smallest falsifying or representative smoke input first. Then run the
   full workload within the approved resource envelope.
4. Capture commands, exit codes, stdout/stderr paths, package/runtime versions,
   CPU/GPU details, seeds, wall time, peak resource use when available, and all
   output hashes with `$science-provenance`.
5. Validate outputs against a baseline, invariant, or independent implementation.
   Preserve failed and inconclusive attempts. Finish with `$science-review`.

## Boundaries

- Do not modify system packages, the global Python/R/Julia environment, shell
  startup files, or unrelated user files.
- Do not expose environment variables, credential files, SSH keys, tokens, or
  private dataset contents in logs or artifacts.
- Do not use a GPU merely because one exists; report CPU and GPU assumptions.
- Do not run untrusted repository scripts or container entrypoints before review.
- Route SSH, Slurm, cloud GPU, or remote object storage work to
  `$cx-remote-scientific-compute`.
