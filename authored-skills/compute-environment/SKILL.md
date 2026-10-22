---
name: compute-environment
description: "Inspect and use the local computer as a reproducible scientific workbench across shell, Python, R, Julia, Jupyter, containers, CPUs, and GPUs. Use when a scientific task needs local files, code execution, package or environment setup, data conversion, visualization, notebooks, simulation, model inference, or hardware-aware execution rather than instructions alone, including a Julia notebook on a local GPU."
license: Apache-2.0
---

# Local Scientific Compute

## Decision contract

Act as an executor. Define the scientific task, inputs and sensitivity, expected outputs, baseline/invariants and scientific acceptance criterion separately from process success. Record code/notebook path and hash, intended backend, expected runtime/disk/resource envelope, smallest smoke input, and falsifier. Use the existing computer to produce an inspectable, reproducible result, not merely a tutorial. Resolve `<plugin-root>` as two directories above this `SKILL.md`; load `$science-provenance` and `$science-review` when their schemas or review procedure are needed.

## Reference usage

Read [references/compute-reproducibility.md](references/compute-reproducibility.md) before capturing an environment, approving a resource-intensive run, interpreting reproducibility, or deciding whether outputs are durable. It defines safe environment capture, resource controls, seed/nondeterminism reporting, clean-environment reproduction, and output boundaries.

## Workflow

1. **Approval gates.** Read-only inspection and a small CPU calculation in an existing environment need no extra gate. Request approval before adding dependencies/changing a lock, package installation, GPU workload beyond capability/version inspection, a new network host/container image, large download, privileged container flags, heavy CPU work, or sensitive-data movement; present one approval packet with local target/GPU, code path/hash, inputs/sensitivity, pinned environment/image, smoke/full commands, package/download/network changes, CPU/GPU/memory/time/disk, output path, validation criterion, and cancellation/checkpoint plan. Approval covers only that envelope. After approval, continue reversible steps inside it without re-asking; ask again if the data boundary, environment, resources, or method changes.
2. Resolve the project root from workspace or nearest version-control root; inspect inputs/storage without copying sensitive data and run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/compute_probe.py"` for a read-only capability report, saving it with `--output artifacts/<run-id>/compute-environment.json` once a run exists.
3. Select the smallest adequate backend: shell/existing executable for simple transformations; isolated Python, R, or Julia project for analysis; Jupyter only when an inspectable notebook is required; digest-pinned container for system dependencies or stronger isolation; GPU only when it materially benefits and memory fits. Record the selection and reason.
4. Reuse project contracts: Python honors `pyproject.toml`, `uv.lock`, `.venv`, and uses `uv run --locked` when locked, otherwise an isolated run environment without changing global Python; R honors `renv.lock`/project library and records `sessionInfo()` (use `renv` when present); Julia uses matching `Project.toml`/`Manifest.toml`; bind Jupyter kernel to selected environment and record runtime identity; containers honor reviewed definitions and pinned digests. Never silently rewrite locks or mix project environments.
5. Create `artifacts/<run-id>/`; hash inputs or record approved external paths. Preserve base environments using run-scoped pinned Python, project R library and `sessionInfo()`, run-scoped Julia project with project/manifest, shell scripts with `set -euo pipefail` for non-trivial commands, notebook plus exported script or executed-cell log, and containers with limited mounts, no privileged mode, and full invocation.
6. Run the smallest falsifying/representative smoke first, then only the approved full workload; if preflight fails, stop or diagnose within the approved scope and retain failure evidence rather than escalating resource use.
7. Capture commands, exit codes, stdout/stderr paths, package/runtime versions, model/weight/database revisions, CPU/GPU details, seeds, wall time, peak resources when available, and output hashes via `$science-provenance`; validate against a baseline, invariant, or independent implementation.
8. Reproduce in a clean environment when the claim requires portability; vary seeds, backend, deterministic settings, and relevant package/runtime versions within the approved scope, and record which differences change outputs or conclusions.
9. Preserve failures and inconclusive attempts, distinguish scientific acceptance from exit status, and finish material results with `$science-review`; return limitations and exact artifact paths.

## Outputs

Return one `compute-environment-evidence-v1` record with required fields: decision contract (`decision_contract`), input manifest (`input_manifest`), code path and hash (`code_path_hash`), environment capture (`environment_capture`), lockfiles and image digests (`lockfiles_and_image_digests`), backend and resource check (`backend_and_resource_check`), approval scope (`approval_scope`), smoke result (`smoke_result`), commands and exit codes (`commands_and_exit_codes`), outputs and hashes (`outputs_and_hashes`), baseline or invariants (`baseline_or_invariants`), seed and determinism record (`seed_and_determinism_record`), clean-environment reproduction (`clean_environment_reproduction`), claim statuses (`claim_statuses`: supported, contradicted, inconclusive, or unavailable), scientific acceptance (`scientific_acceptance`), uncertainty (`uncertainty`), applicability domain (`applicability_domain`), limitations (`limitations`), failures (`failures`), next action (`next_action`), and review receipt (`review_receipt`). Keep local scratch distinct from durable outputs and preserve logs, outputs, environment capture, and failed attempts through `$science-provenance`.

## Boundaries

- Do not modify system packages, global Python/R/Julia environments, shell startup files, or unrelated user files.
- Do not expose environment variables, credential files, SSH keys, tokens, or private dataset contents in logs/artifacts. Never read or print private configuration or account files.
- Do not use a GPU merely because one exists; report CPU/GPU assumptions.
- Do not run untrusted repository scripts or container entrypoints before review.
- Route SSH, Slurm, cloud GPU, or remote object-storage work to `$cx-remote-scientific-compute`.
- For cancellation identify only the process launched by this run, request graceful checkpoint/interrupt first, and never kill unrelated processes.
- Do not treat process completion, exit code, or model confidence as scientific acceptance without the declared validation.
