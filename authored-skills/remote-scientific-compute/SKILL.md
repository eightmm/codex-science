---
name: remote-scientific-compute
description: "Run reproducible scientific workloads through an existing SSH host, Slurm/HPC cluster, cloud GPU provider, or remote object storage. Use for remote execution, job submission and monitoring, checkpointed long runs, GPU allocation, data staging, result retrieval, queue diagnosis, or resuming work that can outlive the current Codex task."
---

# Remote Scientific Compute

Move an approved scientific workload to existing remote infrastructure while
protecting credentials, login nodes, private data, budgets, and reproducibility.

## Reference usage

Read [the backend checklists](references/backends.md) for the selected SSH, Slurm/HPC, cloud GPU, or object-storage route before staging, submitting, allocating, or writing remotely. Do not infer scheduler flags, cost controls, storage semantics, or cleanup procedures from a backend name.

Record the reference version and SHA-256 in the run when it controls a submission or transfer. The backend reference governs execution safety; it is not evidence for the scientific result.

## Inspect without changing state

1. Use only an existing host alias, provider profile, project, and account. Never
   enroll a service, create IAM policy, or modify SSH configuration implicitly.
   If the host is not already known, stop and show its host fingerprint for the
   user to verify out of band; never auto-accept first contact or a changed key.
2. Confirm the target type and remote working directory. Probe with minimal
   read-only commands such as scheduler availability, queue/partition metadata,
   disk quota, and accelerator inventory. Never read private keys or print tokens.
3. Inventory files to transfer, their hashes, sensitivity, size, destination, and
   exclusions. Prefer code/config plus immutable data references over bulk copies.
4. Read [references/backends.md](references/backends.md) only for the selected
   SSH, Slurm, cloud GPU, or object storage backend.

## One explicit approval packet

Before the first write, transfer, submission, allocation, or paid action, request
explicit approval for one concrete packet containing:

- target host/provider/account and remote path;
- code revision, command, environment or digest-pinned image;
- files and data leaving the local machine, including sensitivity;
- CPU/GPU type and count, memory, wall time, storage, and concurrency;
- estimated cost with a hard time/cost cap for paid compute;
- output/log/checkpoint locations and retrieval plan;
- cancellation, cleanup, and instance-termination commands.
- monitoring cadence, maximum monitoring duration, and terminal stop rule.

Approval covers reversible steps inside that packet only. Ask again if the target,
data boundary, cost cap, resource envelope, or scientific interpretation changes.

## Execute and monitor

1. Stage into a run-specific directory. Verify input and code hashes remotely.
   Never persist credentials in commands, scripts, logs, artifacts, notebooks, or
   environment snapshots.
2. Smoke-test on the smallest input. Do not run long, GPU, or high-CPU work on an
   SSH or cluster login node.
3. For Slurm, submit with `sbatch`; set account, partition, time, CPU, memory, GPU,
   and `%x-%j` log paths explicitly. Use `set -euo pipefail`, change to the submit
   directory, handle signals, and write resumable checkpoints.
4. For a cloud GPU, use the already configured provider interface, pin the image
   and region/type, enforce the approved cap, persist outputs outside ephemeral
   storage, and terminate the instance after retrieval or failure.
5. For object storage, preview transfers, keep destinations private, preserve
   checksums, and use least-privilege existing credentials. Do not make a bucket
   or object public for convenience.
6. Record remote job/instance IDs immediately. Monitor without busy polling;
   capture terminal status, exit code, resource accounting, logs, checkpoints,
   and failure cause. Resume from a verified checkpoint instead of duplicating a
   job. Cancel only on user request, a safety limit, or the approved stop rule.
7. Retrieve outputs into `artifacts/<run-id>/`, verify hashes, record costs and
   retained remote resources, then run `$science-provenance` and `$science-review`.

## Stop conditions

Stop for unknown ownership, host-key changes, missing authorization, secrets in a
planned command, unapproved private-data transfer, unavailable cancellation,
uncapped paid resources, a full filesystem, or a resource request unsuitable for
the target. Report the blocker without weakening the boundary.
