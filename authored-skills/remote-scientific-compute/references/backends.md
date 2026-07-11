# Remote backend checklists

Read only the section for the selected backend.

## SSH

- Use an existing alias from the user's SSH configuration; do not copy keys or
  weaken host-key verification. For first contact, stop and require the user to
  verify the presented host fingerprint out of band before trust is recorded.
- Run a short read-only preflight before transfer: working directory, disk quota,
  runtime versions, and scheduler presence.
- Prefer `rsync --dry-run` before an approved transfer. Exclude `.env`, keys,
  credentials, caches, raw sensitive data, and unrelated artifacts.
- Use a remote job manager or scheduler for work that may outlive the connection.

## Slurm/HPC

- Inspect `sinfo`, `squeue -u "$USER"`, and partition/account policy before
  proposing resources. Use a site-specific reference when one exists.
- Put resource directives, pinned command, output/error paths, signal handling,
  and checkpoint interval in a saved submission script.
- Submit with `sbatch`, record the job ID, and monitor with `squeue`/`sacct`.
  Never substitute a login-node process for a queued job.
- Distinguish `FAILED`, `TIMEOUT`, `OUT_OF_MEMORY`, `CANCELLED`, and node failure;
  preserve the log and resource accounting before retrying.

## Cloud GPU

- Require an already configured provider account and CLI/API. Do not create or
  broaden IAM roles from this workflow.
- Quote instance/GPU, region, disk, image, egress, and idle cost before creation.
  Set an explicit maximum lifetime and cost where the provider supports it.
- Persist checkpoints and final outputs outside ephemeral disks. Verify retrieval
  before terminating, then verify termination and record any retained volume/IP.

## Object storage

- Use an existing private bucket/container and least-privilege profile.
- List or dry-run before upload, download, sync, overwrite, or deletion.
- Record source/destination URIs without embedding credentials; verify checksums
  after transfer and document encryption and retention assumptions.
- Treat deletion, public ACL changes, lifecycle changes, and cross-region copies
  as separate destructive or cost-changing approvals.
