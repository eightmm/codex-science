# Compute environment and reproducibility

## Claim semantics

Separate an operational claim (a command completed in an environment) from a computational reproducibility claim (the declared inputs/code/environment regenerate an output within a stated tolerance) and a scientific claim (the output passes a domain-specific baseline, invariant, or acceptance criterion). Assign each a distinct claim ID and status. Process completion alone supports only the operational claim.

Record the scientific target, input identities, output units, implementation, environment, expected invariant/baseline, acceptance rule, and limits. A result may be reproducible yet scientifically invalid; a scientifically plausible result may fail exact reproduction because of nondeterminism. Keep these findings separate.

## Environment and source dependencies

Capture operating system and architecture, interpreter/compiler and version, package versions, lockfile hashes, container image digest, relevant system libraries, code revision/hash, model/weight/database revision, and hardware/software accelerator details. Use existing `pyproject.toml`, `uv.lock`, `.venv`, R `renv.lock`/project library, Julia `Project.toml`/`Manifest.toml`, notebook kernel, or reviewed container definition as applicable. Record absent lockfiles and unresolved version ranges as uncertainty.

Record dependencies between results and shared libraries, drivers, firmware, external services, mutable images, and data. Reproduction in the same environment is not independent validation. A clean-environment rerun should begin from the recorded project inputs and lock/image identity, without hidden user-site packages or private configuration.

Keep sensitive material out of capture: never read or print private configuration or account files, environment variables, credentials, SSH keys, tokens, or private dataset content. Record approved external data paths or hashes only where authorized; do not copy sensitive data for convenience.

## Resource controls and uncertainty

Before heavy work, inspect CPU count, memory, disk, GPU model/memory/driver, and expected runtime using read-only probes. Define the smallest representative smoke, resource envelope, output location, and cancellation/checkpoint plan. A visible accelerator is not justification to use it; choose it only when it materially benefits the task and memory fits.

Record deterministic seeds for all exposed random generators, but do not imply that seeds guarantee deterministic GPU kernels, parallel reductions, nondeterministic libraries, or hardware equivalence. State known nondeterministic operations and compare repeated runs with explicit exact or tolerance-based criteria.

Separate uncertainty due to random seeds, floating-point/backend behavior, hardware, library version, data, and algorithm choices. A change is material when it alters the scientific acceptance decision, claim status, reported precision, or key invariant under the declared criterion.

## Controls and sanity checks

- Inspect an allowlisted capability report before resource-intensive work; never print all environment variables or unrestricted configuration.
- Verify OS/runtime/package/lock/image identity against the plan before execution; stop if the environment differs materially.
- Run a small CPU or backend-specific smoke and validate shape, finite values, expected files, and domain invariants before a full run.
- Compare with a baseline, independent implementation, or known invariant appropriate to the task; record shared dependencies that weaken independence.
- Inspect available disk, memory, and accelerator memory before heavy runs; stop or request a changed approval envelope before exceeding it.
- Reproduce from a clean environment for portability claims; distinguish exact bitwise match from tolerance-based match and explain why the criterion fits the method.
- Inspect output paths to ensure scratch files are not represented as durable artifacts; copy or promote outputs only under the declared plan.

## Sensitivity and reproducibility analysis

Vary seeds, thread counts, CPU/GPU backend, deterministic-kernel settings, relevant package/runtime versions, and clean-environment state where they can affect the result and fit the approved scope. Retain each run identity and compare both numerical outputs and scientific decisions. Do not widen version or hardware variation beyond approval.

Classify results as bitwise reproducible, numerically reproducible within a stated tolerance, decision-equivalent but numerically different, or not reproduced. A conclusion is fragile if a reasonable predeclared variation crosses acceptance thresholds, changes status, or changes the principal result beyond tolerance. Report failed reproduction rather than selecting the closest run.

Keep scratch separate from durable output. Declare artifact paths and hashes, preserve logs and failed attempts, and ensure long-lived outputs do not depend on deleted scratch state. Do not claim durability for files that remain only in temporary storage.

## Durable artifact handoff

Before a run, name which outputs are temporary scratch and which are intended durable artifacts. Store durable outputs under the declared project artifact directory or approved destination; keep caches, temporary downloads, and intermediate files in a separate scratch location. Do not move sensitive inputs to durable storage unless the approved plan covers it.

For each durable artifact record its relative path, content hash, producing command/run identity, and validation state. Preserve the original output before any format conversion; link converted files to their inputs and transformation version. A report or figure without its source data and generation record is not a reproducible artifact.

## Environment comparison record

For a clean-environment rerun, state what was held fixed and what changed: operating system, runtime, package resolution, container digest, accelerator, drivers, and relevant configuration. Do not describe a run as clean if it reused untracked packages, mutable model weights, hidden credentials/configuration, or undeclared caches.

When exact identity cannot be recreated, describe the closest valid comparison and its limits. Reproducing only the command while changing inputs, code, model weights, or package resolution is a new run, not an exact reproduction.

Never solve a mismatch by silently installing or changing a dependency. If environment repair requires a package installation or lock change, use the approval gate and retain the original environment record.

Record the reason a clean rerun is necessary: portability across machines, verification of a release artifact, diagnosis of environment contamination, or an explicit reproducibility claim. A same-machine rerun may test stochastic variation but does not test portability.

Report the scope of reproducibility precisely: command-level replay, environment recreation, numerical agreement, or scientific-decision equivalence. State unavailable host details rather than implying that a container digest fully describes the runtime.

If only a subset can be captured safely, document the fields omitted and why. A partial environment receipt must not be described as a complete environment snapshot.

## Applicability domain and failure modes

Environment capture improves auditability but cannot establish that code is correct, data are valid, scientific assumptions hold, or a result generalizes. Applicability is bounded by recorded operating system, hardware, runtime, dependencies, input domain, determinism, and resource envelope. Container digests do not capture host drivers or all runtime conditions.

| Failure mode | Detection and response |
| --- | --- |
| Hidden or drifting dependencies | Compare versions and lock hashes; isolate the run and report unresolved packages. |
| Private configuration leaks into artifacts | Inspect only allowlisted capture fields and output paths; remove the capture from the run and record the issue without printing secret contents. |
| GPU OOM or resource overrun | Compare requested footprint with available memory and monitor run; stop only the owned run and request revised scope before changing envelope. |
| Seed mistaken for determinism | Repeat runs and compare outputs; identify nondeterministic kernels/backend operations. |
| Clean reproduction silently uses user packages | Start in an isolated environment and capture interpreter/package identity; report environment contamination if present. |
| Scratch mistaken for durable output | Verify resolved output paths and hashes; mark temporary artifacts and preserve only through the authorized path. |
| Exit code treated as scientific acceptance | Check baseline, invariants, and declared acceptance criterion independently of process status. |
| Same-stack agreement treated as independent | Trace shared libraries, data, code, and hardware; describe agreement as consistency, not independent confirmation. |

## Sources

- Wilson et al., **Good enough practices in scientific computing** (2017), PLOS Computational Biology: practical project and computational reproducibility practices, not proof of scientific validity.
- Sandve et al., **Ten Simple Rules for Reproducible Computational Research** (2013), PLOS Computational Biology: reproducible-workflow practices, not a guarantee of bitwise identity across hardware.
