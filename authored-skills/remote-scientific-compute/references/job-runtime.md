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
- outputs and checkpoints are safe paths relative to the working directory;
- input hashes are recorded when available;
- secret-like environment keys are rejected;
- timeout is positive;
- local resource requests are recorded but not scheduler reservations;
- non-local submission requires approval even when `approval_required` is false in an invalid user-supplied spec.

The spec fingerprint covers all fields, including command, environment values, resource request, input hashes, outputs, timeout, and cost cap.

## CLI overview

```bash
python scripts/science_job.py --state-dir .science-jobs preflight ...
python scripts/science_job.py --state-dir .science-jobs approve ...
python scripts/science_job.py --state-dir .science-jobs render-slurm ...
python scripts/science_job.py --state-dir .science-jobs submit ...
python scripts/science_job.py --state-dir .science-jobs status ...
python scripts/science_job.py --state-dir .science-jobs wait ...
python scripts/science_job.py --state-dir .science-jobs cancel ...
python scripts/science_job.py --state-dir .science-jobs collect ...
```

Every command writes a JSON receipt to `--output`.

## Local execution

### Preflight

```bash
python scripts/science_job.py \
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

A successful preflight does not prove that imports, model weights, databases, input semantics, or scientific assumptions are correct.

### Submit

```bash
python scripts/science_job.py \
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
  stdout.log
  stderr.log
```

`state.json` is written atomically. It is mutable operational state, not scientific evidence. Save terminal receipts and output hashes in the run manifest when they support a claim.

### Status and wait

```bash
python scripts/science_job.py \
  --state-dir artifacts/run-014/jobs \
  status \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-status.json

python scripts/science_job.py \
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
python scripts/science_job.py \
  --state-dir artifacts/run-014/jobs \
  cancel \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-cancelled.json
```

Cancellation is idempotent for terminal jobs. The local backend sends `SIGTERM` to the worker process group and records `user-cancelled`.

### Collect outputs

```bash
python scripts/science_job.py \
  --state-dir artifacts/run-014/jobs \
  collect \
  --backend local \
  --job-id local-... \
  --output artifacts/run-014/job-collected.json
```

Collection is allowed only after a terminal state. Declared outputs are resolved inside the working directory:

- files receive streaming SHA-256 and size;
- directories receive a Merkle root, total bytes, and entry count;
- missing outputs remain explicit with `artifact_type: missing`.

Do not remove a missing output from the receipt to make a run appear complete.

## Approval receipt

Create approval for a spec only after reviewing target, resource, cost, transfer, cancellation, and scientific scope.

```bash
python scripts/science_job.py \
  --state-dir artifacts/run-014/jobs \
  approve \
  --spec artifacts/run-014/slurm-job-spec.json \
  --approved-by jaemin \
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
python scripts/science_job.py \
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

Rendering is safe and does not submit.

### Submit

```bash
python scripts/science_job.py \
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
- all required data are already staged by an approved route.

The backend does not copy data or credentials.

### Status

```bash
python scripts/science_job.py \
  --state-dir artifacts/run-014/jobs \
  status \
  --backend slurm \
  --job-id slurm-local-... \
  --output artifacts/run-014/slurm-status.json
```

The adapter normalizes scheduler states while retaining the raw state in the message. `OUT_OF_MEMORY`, `NODE_FAIL`, `PREEMPTED`, `TIMEOUT`, and `CANCELLED` are not merged into one generic failure.

### Cancel and collect

```bash
python scripts/science_job.py --state-dir artifacts/run-014/jobs cancel \
  --backend slurm --job-id slurm-local-... --output cancelled.json

python scripts/science_job.py --state-dir artifacts/run-014/jobs collect \
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
- Claiming remote durability when state files exist only on an ephemeral local disk.

## Evidence boundary

The job runtime provides durable execution and collection receipts. It does not establish reproducibility across environments, validate model or database licensing, authenticate scheduler identity, measure cloud cost unless an adapter reports it, or prove a scientific result.
