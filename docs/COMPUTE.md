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
