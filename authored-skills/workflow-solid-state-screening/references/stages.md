# Stage and record contract

## Scope and invocation

This reference controls normalization, analytic control, convergence, ranking
and review handoff. All example data are synthetic fixtures, redistributable
under the repository MIT license. The toy checks a workflow contract, not
materials-property accuracy. No external solver, network, GPU or installation
is invoked. The Python module is `codex_science.solid_state_screening`; its
`chain_spectrum`, `reference_bundle`, `encode_record` and `validate_bundle`
entry points compute in memory or read existing records, without writing them.

From the plugin root:

```sh
python3 scripts/validate_solid_state_screening.py examples/workflow-solid-state-screening
```

The sole positional argument `bundle` is the directory holding the six records.
The CLI emits JSON to stdout on success, a labelled error to stderr and exit 1
on refusal. `--help` documents usage. There is no output-file option. The
success statuses are `contract-validated` or `exploratory`, always synthetic,
with `review_status` pending. The evidence boundary is returned explicitly.

## Ordered stages

Every stage input is an immutable path plus SHA-256 of the exact file bytes,
including whitespace. Stage 1 binds `contract.json`; every later stage binds
that contract and the immediately preceding stage. All filenames are fixed
bundle-relative regular files, never symlinks. The root is pinned by walking
every absolute ancestor with directory descriptors and refusing symlinks or
identity changes. Records are opened relative to the pinned descriptor, with
identities checked around each read. Before success the reader rechecks the
root, every record, and the root again. Each record is at most 64 MiB;
the reader checks the opened file's type and size before a bounded read and
refuses growth past that limit. Unique input bytes are capped at 384 MiB per
snapshot, preserving all six records at the existing per-record maximum.
Hardlink aliases share cached bytes and are read once per capture/recheck pass.
The reference model has always emitted exactly these six records and integer
dimer sites. JSON objects must have unique keys at every
depth, including escaped spellings of the same key. The same bytes are parsed
and hashed. A changed input requires a new snapshot and new downstream
identities, not reusing reviewed evidence.

| ID | Accepted input identities | Existing skills/scripts to use | Output / schema | Controls and failure handling | Human gate |
| --- | --- | --- | --- | --- | --- |
| stage-1 | Supplied structure/model in coordinator manifest; `contract.json` path/hash | dimensional-analysis-units / references/unit-dimension-runtime.md; condensed-matter-solid-state / references/solid-state-evidence.md; existing units_runtime.convert_value | normalized.json / solid-state-screening-stage-v1 | Source energy/length dimensions must convert to eV/nm; preserve source file; reject unsupported Hamiltonian/boundary or missing units | Only an interpretation-changing convention or missing essential identity |
| stage-2 | contract.json and normalized.json path/hash | condensed-matter-solid-state analytic limits; computational-physics-validation / references/verification-validation-protocol.md | analytic-control.json / solid-state-screening-stage-v1 | Fixed dimer, onsite 0 eV, hopping 1 eV; expected spectrum [-1, 1] eV; max absolute error at most frozen analytic_abs; failed control blocks scoring | No routine stage gate |
| stage-3 | contract.json and analytic-control.json path/hash | numerical-analysis-error-control / references/numerical-verification-runtime.md; computational-physics-validation | convergence.json / solid-state-screening-stage-v1 | Full frozen [4,8,16,32] sites; no missing/reordered levels; each absolute error increases by at most monotone_slack; final error at most convergence_abs; preserve failed snapshots | Approval before substituting heavy compute or changing physical interpretation |
| stage-4 | contract.json and convergence.json path/hash | experimental-uncertainty-propagation / references/uncertainty-runtime.md | ranking.json / solid-state-screening-stage-v1 | Sum independent variances for input/model/numerical components, rank energy plus standard uncertainty ascending; disclose every declared alternative and reversal; deterministic ID tie break | Interpretation-changing model/covariance choice; no routine ranking approval |
| stage-5 | contract.json and ranking.json path/hash; coordinator binds all artifacts transitively and directly in manifest | science-provenance and science-review | review-handoff.json / solid-state-screening-stage-v1; existing claim-register sidecar separately | Producer leaves review pending; numerical and unavailable-experiment claims remain distinct; preserve failures and negative results | Coordinator selects rigor and independent reviewer; approval is never truth |

Read the selected existing skill's referenced protocol before running its
controlled operation. The fixture reuses their methods and existing unit
conversion implementation; it does not fabricate their runtime receipts.
DFT and ML-potential adapters remain unimplemented named extension points:
stop for approval before installation, restricted transfer, new hosts or
GPU/remote/heavy compute. Approval does not expand their evidence boundary.

## Pack-local schemas

Only these two schemas are new. They are ordinary domain artifacts, not new
global artifact kinds, receipt fields, coordinator plan fields or MCP tools.

`solid-state-screening-contract-v1` requires `schema`, `synthetic` true,
`seed` 1729 (no random sampling), `model`, `observable`, `energy_unit`,
`thresholds`, `refinements`, `candidates`, and `sensitivity`.
`model` supplies name `open-tight-binding-chain`, dimension 1, boundary `open`,
and positive `lattice_spacing` with `value` and source `unit`. The observable
is `lowest-energy`. Candidate `id` values are unique nonempty strings;
`onsite`, nonnegative `hopping`, and nonnegative `uncertainty.input` and
`uncertainty.model` use the source energy unit. Values must be finite JSON
numbers, without boolean/string coercion. The normalized working units are
eV/nm; the original contract retains source units. Thresholds `analytic_abs`,
`convergence_abs`, `monotone_slack` are nonnegative **working eV** values,
fixed before outcomes. Each nonempty sensitivity scenario has unique `id`,
nonnegative dimensionless `hopping_scale` and `onsite_shifts` mapping every
candidate ID to a finite **working eV** shift. No undeclared covariance is
inferred: this reference supports independent components only.

The reference CPU envelope is 1..32 sites for `chain_spectrum`, with precisely
[4,8,16,32] refinement levels for a bundle. For onsite epsilon and hopping t,
the open-chain eigenvalues are epsilon - 2 t cos(m pi/(N+1)), m in 1..N.
The implementation instead applies the tridiagonal Hamiltonian to sine modes
and evaluates their Rayleigh quotients. The infinite-chain lower edge is
epsilon - 2 t. Error to that known edge is a finite-size numerical bound for
this toy, not a model-discrepancy estimate for real materials. The dimer limit
has eigenvalues [-1,1]. Zero hopping has the degenerate onsite spectrum.

`solid-state-screening-stage-v1` requires `schema`, `synthetic` true, ordered `stage_id`,
`inputs` (objects with `path` and `sha256`) and `data`:

- Normalization data: `energy_unit`, `length_unit`, `lattice_spacing`, normalized
  `candidates`, `thresholds_used`, boolean `exploratory`. Effective thresholds
  differing from the contract require the exploratory label even when stricter.
- Analytic data: boolean `ran`, integer `sites` 2 (excluding booleans and floats),
  `observed` and fixed `expected` spectra.
- Convergence data: `candidates` in contract order, each with `candidate_id`,
  full `series` of `sites`/`value`, `reference_limit`, `final_error`, `converged`.
  Values are recomputed against the declared Hamiltonian; plausible monotonic
  fabricated values do not establish convergence.
- Ranking data: `rule` minimize-energy-plus-standard-uncertainty, `covariance`
  independent-components, `rows`, `order`, `sensitivity`. Each row contains
  `candidate_id`, `energy`, `uncertainty_components` input/model/numerical,
  `combined_uncertainty`, and `score`. Each sensitivity has `id`, full `rows`,
  `order`, and boolean `flips`. The finite-size error supplies the numerical
  component under the declared conservative independent-component convention;
  this quadrature is a fixture assumption, not a calibrated physical interval.
- Handoff data: `review_status` pending, boolean `exploratory` matching stage 1,
  `claims`, `experimental_comparison`, `failed_controls`, `negative_results`,
  `next_action`. Claim `id`, `kind`, `status`, `basis` are local dispositions,
  not a replacement claim-register. Permitted kinds are descriptive and
  associational; basis is numerical-verification or experiment. Numerical
  status is supported/inconclusive/unavailable; experiment is unavailable.
  Experimental comparison is status unavailable, observable null for this
  synthetic route. External measurements require their own matched-observable
  evidence lane and independent review, outside this reference schema.

The coordinator keeps full claim-register entries (required support, falsifier,
dependencies, uncertainty, applicability and status) separately and registers
all domain artifacts with paths and hashes. The synthetic example manifest.json
and claims.json use existing manifest/claim-register schemas to illustrate this
registration; tests validate them with the existing artifact-bundle validator.
The pack's read-only CLI validates the six domain records; the coordinator's
existing artifact validator checks its manifest and separate sidecars.
Use exactly one coordinator
checkpoint per run; copy only the `plan` array from plan.json into its existing
manifest, and advance matching ordered IDs with existing checkpoint tools.
The validator itself creates no checkpoint, review receipt or manifest.

## Refusals and retained evidence

The negative-cases.json synthetic fixtures mutate the indicated path in a copy
of the positive bundle and rebind downstream hashes, so identity errors cannot
mask scientific-contract defects. Tests require the following labelled errors:

| Defect | Refusal |
| --- | --- |
| Missing, symlinked or non-regular record | SS_MISSING_RECORD |
| Record over 64 MiB, aggregate over 384 MiB, or size changes during reading | SS_RECORD_SIZE |
| Duplicate JSON object key at any depth | SS_SHAPE |
| Missing/inconsistent units | SS_UNITS |
| Control not run / outside tolerance | SS_ANALYTIC_NOT_RUN / SS_ANALYTIC_TOLERANCE |
| Absent/truncated series / increasing error / failed convergence | SS_CONVERGENCE_SERIES / SS_NONMONOTONE / SS_NOT_CONVERGED |
| Omitted declared uncertainty / hidden sensitivity reversal | SS_UNCERTAINTY / SS_SENSITIVITY |
| Changed threshold without exploratory disclosure | SS_POSTHOC_THRESHOLDS |
| Numerical agreement promoted to physical or clinical validity | SS_PHYSICAL_VALIDITY |
| Experimental claim without matched measurement / mismatched observable | SS_MISSING_EVIDENCE / SS_EXPERIMENT |
| Association promoted to causality / missing evidence called negative | SS_CAUSALITY / SS_MISSING_EVIDENCE |
| Producer marks itself reviewed | SS_REVIEW_TRUTH |

Malformed records, nonfinite numbers, changed identities and reordered stages
also fail with labelled ValueError codes; the CLI never exposes a traceback
for input refusals. A missing record is unavailable, never negative evidence.
Keep failed controls, non-converged runs, exclusions and negative results as
immutable artifacts when correcting a snapshot. One bounded retry after fixing
the named cause is sufficient; stop and investigate a repeated failure.

## Verification scope

The fast gate discovers tests/test_workflow_solid_state_screening.py and the
scripts/check.sh contracts step runs the read-only example validator. This adds
only offline CPU checks, with no new CI job or matrix. The focused module has a
60-second acceptance budget; the two native/reference audits check packaging,
not physical validity. Inventory, wrappers and global maturity-count prose are
regenerated by the owning coordinator at batch integration.

## Concurrency and interruption

The validator and reference model write no files, refs or records. Two calls
over an unchanged bundle return the same result. A kill leaves no partial
output artifact (stdout may be truncated). A concurrent producer can change
the files; hash-bound stage checks detect inconsistent reads, but the reader
does not lock or authenticate snapshots. The coordinator must publish immutable
snapshots; hash consistency alone cannot prove when thresholds were chosen.
