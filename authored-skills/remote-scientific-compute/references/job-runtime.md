# Durable job runtime: local and Slurm

Read this reference before constructing a job spec, approving a non-local job, submitting local or Slurm work, polling state, cancelling, or collecting outputs.

## Backend boundary

Implemented execution backends:

- `local` — durable worker process, terminal receipt, wait, cancel, and hash-based output collection;
- `slurm` — script rendering, approved `sbatch` submission, `sacct`/`squeue` polling, `scancel`, and shared-filesystem output collection.

Not implemented by this runtime:

- implicit SSH credential discovery;
- remote object-store transfer;
- cloud-provider provisioning;
- GA4GH TES/WES submission;
- software installation;
- scheduler account or partition discovery by trial submission.

Those routes require separate adapters and approval contracts. Do not pass an unsupported backend name and do not disguise a remote shell command as `local`.

## Job spec

A job spec is a JSON object:

```json
{
  "schema_version": 1,
  "backend": "local",
  "name": "compute-rmsd",
  "command": [
    "python",
    "scripts/measure_pose.py",
    "--input",
    "poses.sdf",
    "--output",
    "metrics.json"
  ],
  "working_directory": "/absolute/path/project",
  "source_snapshot": {
    "mode": "git-archive",
    "commit": "0123456789abcdef0123456789abcdef01234567"
  },
  "environment": {
    "OMP_NUM_THREADS": "4"
  },
  "inherit_environment": true,
  "inputs": [
    {
      "id": "poses",
      "path": "poses.sdf",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  ],
  "outputs": [
    "metrics.json"
  ],
  "resources": {
    "cpus": 4,
    "memory_mb": 8192,
    "gpus": 0,
    "gpu_type": null,
    "wall_time_seconds": 1800,
    "partition": null,
    "account": null,
    "qos": null
  },
  "timeout_seconds": 1800,
  "cost_cap": null,
  "approval_required": false,
  "scientific_run_id": "run-014",
  "checkpoint_paths": []
}
```

### Required semantics

- `command` is an argv list, never a shell command string;
- `working_directory` must already exist;
- `source_snapshot` is optional for schema-v1 compatibility. When present, it
  must select `git-archive` and name the exact 40- or 64-hex commit at `HEAD`;
- outputs and checkpoints are safe paths relative to the working directory;
- input hashes are recorded when available;
- secret-like environment keys are rejected;
- timeout is positive;
- local resource requests are recorded but not scheduler reservations;
- non-local submission requires approval even when `approval_required` is false in an invalid user-supplied spec.

The spec fingerprint covers all fields, including the optional exact source
commit, command, environment values, resource request, input hashes, outputs,
timeout, and cost cap. Omitting `source_snapshot` preserves the legacy live-tree
serialization, fingerprint, and source execution. New Slurm rendering and
submission require names, partitions, accounts, QoS values, and GPU types to be
safe single tokens on both routes. Persisted legacy job records remain readable
for status, cancellation, and collection.

### Strict Git source snapshot

Use `source_snapshot.mode: git-archive` when a result may support a scientific
claim or matched comparison. Preflight and submit require:

- an exact commit equal to the current `HEAD`;
- a clean worktree with no tracked changes or nonignored untracked files;
- no tracked symbolic links or submodules;
- a SHA-256 for every declared file input and a directory Merkle root for every
  declared directory input;
- source and input bytes within the runtime's bounded archive limits.

Ignored, digest-bound inputs may be overlaid into the committed source. The
runtime verifies them before and after copying. Submit produces an owner-only,
deterministic source archive plus a fingerprinted receipt containing the commit,
tree, working-directory location inside the tree, archive SHA-256 and size, and
input IDs. Local and Slurm jobs verify and materialize that archive in their job
directory immediately before execution. Output collection reads that isolated
directory, never the mutable checkout.

Ignored input overlays have normalized execution metadata: a new file is
non-executable, committed target files retain their commit-bound executable bit,
directories are owner-only, and empty nested input directories are omitted.
Their declared content digest remains the identity boundary.
Local and strict Slurm extraction preserve these archive modes identically inside
the owner-only managed job directory.

Committed blobs are materialized without checkout filters. If Git LFS or another
smudge filter supplies bytes needed at runtime, declare that path as a hashed
input so those materialized bytes replace the committed pointer under the same
receipt.

Directory inputs must be quiescent for the duration of bundling. If another
process may change their entries or types, first stage them into a reviewed
immutable directory and bind that staged Merkle root.

`render-slurm` before submission emits a clearly marked preview with fail-closed
source placeholders. Only the script saved by `submit`, together with
`source-receipt.json`, carries the exact archive size and digest. Treat a strict
Slurm job directory as one attempt: scheduler requeue or a manual restart
requires a new submission rather than reusing materialized source state.
Strict Slurm setup requires Linux `/proc`, Bash, and every verifier tool reported
by preflight; the submitted script records resolved verifier paths and removes
inherited Bash startup files/functions and ambient tar transformation options
before extraction. Its owner-only setup umask is restored before the user command.
Archive copying is bounded by a size-derived timeout with a 1 MiB/s floor and a
30-second minimum.

Place `--state-dir` outside the source worktree or gitignore it in the exact
commit. A generated, nonignored state directory is intentionally treated as an
untracked change by the next strict preflight.

The compatibility route without `source_snapshot` still executes in
`working_directory`. It is appropriate for legacy or exploratory jobs, but its
receipt does not prove an immutable source state. A source snapshot also does not
pin the Python/R/Julia environment, container, model weights, database release,
or external identifier-only inputs; record those separately. It changes the
initial cwd, not the process's entire filesystem namespace: absolute command
arguments and inherited `PATH`, `PYTHONPATH`, or equivalent values can still
reach mutable external paths. Pin or disable them when they affect a claim.

## CLI overview

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs preflight ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs approve ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs render-slurm ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs submit ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs status ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs wait ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs cancel ...
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir .science-jobs collect ...
```

Every command writes a JSON receipt to `--output`.

## Local execution

### Preflight

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  preflight \
  --spec artifacts/run-014/job-spec.json \
  --output artifacts/run-014/job-preflight.json
```

Preflight checks:

- backend matches;
- executable is resolvable;
- working directory exists;
- spec validates;
- resource request and spec fingerprint are recorded.
- when strict source binding is selected, the commit, clean-tree state, Git tree
  entry types, path-input hashes, and bundle limits are valid.

A successful preflight does not prove that imports, model weights, databases, input semantics, or scientific assumptions are correct.

### Submit

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  submit \
  --spec artifacts/run-014/job-spec.json \
  --output artifacts/run-014/job-submitted.json
```

The command starts a detached Python worker and returns a state receipt:

```json
{
  "schema_version": 1,
  "job_id": "local-...",
  "backend": "local",
  "job_spec_sha256": "...",
  "state": "submitted",
  "worker_pid": 12345,
  "stdout_path": "stdout.log",
  "stderr_path": "stderr.log",
  "fingerprint": "..."
}
```

The job directory contains:

```text
jobs/jobs/local-.../
  spec.json
  state.json
  source-receipt.json  # strict source route only
  source.tar           # strict source route only
  source/              # verified materialization and outputs
  stdout.log
  stderr.log
```

`state.json` is written atomically. It is mutable operational state, not scientific evidence. Save terminal receipts and output hashes in the run manifest when they support a claim.

### Status and wait

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  status \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-status.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  wait \
  --backend local \
  --job-id local-... \
  --timeout 120 \
  --poll 0.2 \
  --output artifacts/run-014/job-terminal.json
```

States:

```text
submitted
running
completed
failed
timed-out
cancelled
lost
```

Failure classes distinguish at least:

```text
nonzero-exit
wall-time
executable-not-found
worker-exception
worker-lost
user-cancelled
```

A process exit code of zero means only that the command completed according to the operating system. It is not a scientific acceptance result.

### Cancel

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  cancel \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-cancelled.json
```

Cancellation is idempotent for terminal jobs. The local backend sends `SIGTERM` to the worker process group and records `user-cancelled`.

### Collect outputs

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  collect \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-collected.json
```

Collection is allowed only after a terminal state. Declared outputs are resolved
inside the isolated materialization for a strict source job, or the live working
directory for a legacy job:

- files receive streaming SHA-256 and size;
- directories receive a Merkle root, total bytes, and entry count;
- missing outputs remain explicit with `artifact_type: missing`.

Do not remove a missing output from the receipt to make a run appear complete.

## Approval receipt

Create approval for a spec only after reviewing target, resource, cost, transfer, cancellation, and scientific scope.

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  approve \
  --spec artifacts/run-014/slurm-job-spec.json \
  --approved-by <reviewer-name> \
  --target hpc-cluster-a \
  --output artifacts/run-014/slurm-approval.json
```

The receipt binds:

```json
{
  "job_spec_sha256": "...",
  "backend": "slurm",
  "target": "hpc-cluster-a",
  "approved": true,
  "resource_cap": {},
  "cost_cap": null,
  "fingerprint": "..."
}
```

Changing the job spec invalidates the approval. Approval authorizes execution boundaries; it does not endorse scientific validity.

## Slurm execution

### Render before submitting

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  render-slurm \
  --spec artifacts/run-014/slurm-job-spec.json \
  --job-id preview \
  --output artifacts/run-014/slurm-preview.sh
```

Inspect:

- command and quoting;
- working directory;
- CPU, memory, GPU, time, partition, account, and QoS;
- stdout/stderr destination;
- environment exports;
- timeout wrapper.
- strict source archive hash verification and isolated materialization, when
  selected.

Rendering is safe and does not submit.

### Submit

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  submit \
  --spec artifacts/run-014/slurm-job-spec.json \
  --approval artifacts/run-014/slurm-approval.json \
  --output artifacts/run-014/slurm-submitted.json
```

Preconditions:

- `sbatch` and `scancel` available;
- `sacct` or `squeue` available;
- approval fingerprint matches the exact spec;
- scheduler account/partition already known and approved;
- working directory is a shared path visible to compute nodes;
- all required data are already staged by an approved route;
- a strict source archive and receipt are hash-consistent with the approved job
  spec, when selected.

The backend does not perform a remote dataset transfer or copy credentials. A
strict job stages its bounded source archive only inside the managed job
directory on the already-approved shared filesystem.

### Status

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" \
  --state-dir artifacts/run-014/jobs \
  status \
  --backend slurm \
  --job-id slurm-local-... \
  --output artifacts/run-014/slurm-status.json
```

The adapter normalizes scheduler states while retaining the raw state in the message. `OUT_OF_MEMORY`, `NODE_FAIL`, `PREEMPTED`, `TIMEOUT`, and `CANCELLED` are not merged into one generic failure.

### Cancel and collect

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run-014/jobs cancel \
  --backend slurm --job-id slurm-local-... --output cancelled.json

"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_job.py" --state-dir artifacts/run-014/jobs collect \
  --backend slurm --job-id slurm-local-... --output collected.json
```

Collection assumes a shared filesystem. Remote object storage or SSH transfer requires a separate approved staging backend.

## Checkpoint and resume

`checkpoint_paths` identify files expected to make a later attempt resumable. The runtime records and collects them but does not infer a program-specific resume command.

Required procedure:

1. verify checkpoint bytes and compatibility with code/config/model revision;
2. create a new job spec for the resumed attempt;
3. include the prior job and checkpoint hashes in run provenance;
4. obtain new approval when target, resources, cost, or command changes;
5. preserve the failed or preempted attempt.

Never rewrite a failed job receipt into a successful resumed job.

## Search patterns

Use these exact searches when reading this reference:

- `## Job spec`
- `## Local execution`
- `## Approval receipt`
- `## Slurm execution`
- `## Checkpoint and resume`
- `## Failure handling`
- `## Common mistakes`

## Failure handling

| Failure | Required response |
| --- | --- |
| executable missing | stop; use the approved environment or installation gate |
| local worker lost | preserve logs/state, inspect cause, create a new attempt |
| wall-time | preserve checkpoint, revise resource/timeout contract, obtain approval if required |
| nonzero exit | inspect stderr and scientific inputs; do not retry unchanged indefinitely |
| OOM | reduce workload or request reviewed resources; record OOM separately |
| node failure or preemption | resume only from verified compatible checkpoint |
| `sbatch` error | do not probe random accounts/partitions; resolve scheduler configuration |
| output missing | keep explicit missing record and leave dependent plan steps incomplete |
| output escapes working directory | reject collection; correct the job spec |
| approval mismatch | create a new approval for the exact spec |
| stale input hash | create a new run or attempt contract before execution |
| dirty tree or moved `HEAD` | commit or restore the intended exact source state, then create a new spec/approval |
| source archive or receipt mismatch | fail closed; preserve the job directory and create a new attempt from verified bytes |
| unsupported symlink, submodule, or oversized source | use a reviewed immutable staging route; do not silently fall back to the live tree |

## Common mistakes

- Passing a shell pipeline as one command string instead of an argv list.
- Recording tokens, passwords, or private keys in the job environment.
- Treating requested local resources as enforced limits.
- Submitting Slurm work before reviewing the rendered script.
- Using a shared login node for heavy computation instead of the scheduler.
- Busy-polling a waiting job.
- Treating exit code zero as scientific success.
- Omitting failed attempts, missing outputs, or cancellation receipts.
- Reusing approval after changing code, command, resources, target, or input hashes.
- Using the live-tree compatibility route for a claim-bearing comparison without
  recording the reproducibility limitation.
- Claiming remote durability when state files exist only on an ephemeral local disk.

## Evidence boundary

The job runtime provides durable execution and collection receipts. A strict
source receipt hash-binds the committed and declared input bytes materialized;
it does not establish reproducibility across environments, validate model or
database licensing, authenticate scheduler identity, measure cloud cost unless
an adapter reports it, or prove a scientific result.
