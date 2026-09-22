# Scientific compute

Codex Science uses computer resources only inside an active, user-scoped research
task. Desktop GUI and browser automation are out of scope.

## Local

- Read and write task-relevant files under the current project.
- Run shell, Python, R, Julia, Jupyter, container, CPU, and GPU workflows.
- Prefer an existing environment for inspection; isolate new dependencies per run.
- Probe capabilities without collecting hostnames, environment variables, SSH
  configuration, credentials, or dataset contents.
- Keep code, logs, environment metadata, failures, and output hashes under
  `artifacts/<run-id>/`.
- Reuse the current project's Python lock/venv, R `renv`, Julia project, Jupyter
  kernel, or reviewed container contract. Never mix another project's environment.

## Source identity

Durable local and Slurm jobs may opt into `source_snapshot.mode: git-archive`
with an exact Git commit. This strict route rejects a moved `HEAD`, tracked
changes or nonignored untracked files, tracked symlinks and submodules, unhashed
path inputs, and oversized bundles. Submit creates a deterministic, owner-only archive and a
fingerprinted receipt; execution verifies and materializes the archive inside
the job directory, and collection reads outputs from that isolated copy.
Digest-bound ignored inputs are normalized in that copy: newly added files are
non-executable, directories are owner-only, and empty nested directories are not
part of the source identity. A Slurm render produced before submission is only a
preview; the submitted `job.sh` and `source-receipt.json` contain the exact
archive size and digest.
Local and strict Slurm extraction preserve the same normalized archive modes;
the managed job directory remains owner-only.

This binds the initial job-local working tree and declared relative path inputs;
it is not a hermetic sandbox. Absolute command arguments and inherited values
such as `PATH` or `PYTHONPATH` can still reach software or data outside the
snapshot and must be pinned or disabled separately when they affect a claim.

Schema-v1 specs that omit `source_snapshot` retain the legacy live-working-tree
source route, serialization, and fingerprint. That route remains useful for
exploration but does not establish exact source identity. Slurm directive fields
require safe single tokens when a new script is rendered or submitted, including
on the legacy route; previously persisted job records remain readable for
status, cancellation, and collection. Source binding is separate from
environment, model-weight, database-release, and external-input pinning.

The strict bundle contains Git blob bytes, not checkout filters. Content managed
by Git LFS or another smudge filter must therefore be declared as a digest-bound
path input when the materialized content, rather than its committed pointer, is
required by the job.

A strict Slurm job directory is single-attempt state. Scheduler requeue or an
operator restart must use a new submission/job directory so the verified source
copy and terminal receipt cannot be silently reused.

Strict Slurm materialization requires Linux `/proc`, Bash, and the verifier tools
reported by preflight. The submitted script records their resolved paths and
starts Bash without inherited startup files/functions, then clears archive
transform options. The owner-only setup umask is restored before the user command.
Its bounded copy timeout scales with archive size at a conservative 1 MiB/s floor
(minimum 30 seconds). Directory inputs must be quiescent while the bundle is
built; concurrent writers require a separately staged immutable input. Keep the
managed job state outside the source worktree or gitignore it before the exact
commit, otherwise later strict preflight will correctly report the generated
state as an untracked change.

## Remote

- Use only existing SSH aliases, Slurm/HPC accounts, cloud GPU profiles, and
  private object stores.
- Keep long, GPU, or high-CPU work off login nodes; submit through the scheduler.
- Record the remote job/instance ID, resource request, logs, terminal status,
  accounting, checkpoints, retrieval hashes, costs, and cleanup state.
- Never create accounts, broaden IAM, weaken SSH verification, print secrets, or
  make storage public implicitly.

## Approval

No additional approval is needed for read-only inspection or a small calculation
in an existing environment. One explicit approval packet is required before new
package/network/image access, sensitive-data movement, remote writes, scheduler
submission, or paid allocation. It names the target, command/revision, transferred
data, resource envelope, time/cost cap, outputs, and cancellation plan.

Approval does not extend to a different host, new data boundary, higher cost,
larger resource request, destructive cleanup, or interpretation-changing method.

## Local result view

After manifest validation, generate `index.md` from the manifest. Generate
offline `index.html` only when requested. The views verify artifact existence and
hashes, escape untrusted text, use no hosted assets, and remain derived navigation
files rather than evidence. Display primary raster figures in the Codex response
and link all other artifacts by absolute local path. Generate a static figure
only when it is a data-derived, labeled view that improves interpretation; never
fabricate an illustrative image and present it as scientific evidence.
