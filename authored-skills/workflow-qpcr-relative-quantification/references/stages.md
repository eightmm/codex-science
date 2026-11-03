# Synthetic qPCR stages and local contracts

This is an offline synthetic arithmetic fixture, not measured biological evidence.
All input identities are canonical bundle-relative paths plus lowercase SHA-256
of the exact bytes parsed. Inputs are immutable. The validator writes nothing.

## Invocation and identities

Run `python3 scripts/validate_qpcr_relative_quantification_pack.py BUNDLE` with
one `qpcr-pack-v1` JSON file. Success is JSON on stdout with exit 0. Every refusal,
including missing, extra and unknown arguments, is JSON on stderr with exit 2.
`--help` prints plain usage on stdout and exits 0. There is no output option.
The public Python entries are `validate_qpcr_relative_quantification_pack` and
`reference_computation` in `codex_science.qpcr_relative_quantification_pack`.

Open the bundle through pinned directory descriptors from the filesystem root.
No symlinked ancestor or component, special file, noncanonical artifact path,
absolute artifact path, parent traversal or backslash is accepted. Each unique
device-and-inode artifact is read and parsed once, then reread once for final
hash verification. Hardlink aliases share caches and budgets. The entire ancestor
identity chain is compared at both final rechecks, including a replaced parent
that retains the original bundle inode. Replaced, growing or oversized inputs
refuse. JSON refuses duplicate keys, nonfinite numbers, non-object roots,
oversized numbers, deep nesting and incorrect types; booleans are not numbers.

## Pack-local schemas

All local records contain `schema`, integer `schema_version` of 1, and `fixture`
of `synthetic fixture`. Every declared integer must be a real integer, never a
boolean, float or numeric string. Input records admit only their listed fields.

- `qpcr-pack-v1`: `protocol`, `table`, `report`, and `evidence` artifact identities;
  the first three are individual objects, evidence is a list. Also
  `frozen_protocol_sha256` and boolean `frozen_before_cq_read`.
- `qpcr-protocol-v1`: ordered `conditions` of calibrator then contrast, `targets`,
  `reference_gene`, `reference_rule` of `fixed-single-reference`, `assays`,
  `efficiency_range`, `samples`, `ntc_wells`, `ntc_min_cq`,
  `max_technical_spread`, `detection_cq`, `undetermined_rule` of `censored`,
  `statistic` of `log2-fold-change-welch-t`, `confidence` of 0.95, and integer
  `minimum_interval_n` of 3. Each assay has `gene`, `dilution_series`, `efficiency`
  as a fraction, and `r_squared`. Each dilution point has `log10_input`, `cq`.
  Each sample has `id`, `biological_id`, `condition`, integer
  `technical_replicates`, and `wells`. Each planned well has `well_id`, `gene`,
  integer `technical_replicate`. NTC wells have `well_id`, `gene` only. A complete
  gene by technical-replicate grid is required for every sample; biological IDs
  are unique across both conditions, excluding paired and repeated-unit designs.
- `qpcr-cq-table-v1`: `rows`, each exactly `well_id` and `cq`. Cq is finite from
  zero through 100 or the exact string `undetermined`; no imputed value replaces
  an undetermined source. All frozen wells occur once, with no extras.
- `qpcr-report-v1`: `protocol_sha256`, `reference_gene`, boolean `exploratory`,
  `undetermined_rule` of `censored`, `technical_rule` of `refuse-spread`,
  `efficiency_source` of `dilution-series`, `n_unit` of `biological`, `summary`,
  `headline`, `claims`. A changed reference first requires an exploratory label;
  even labelled changes need a separately frozen revision before this pack can
  compute them. Each summary row has `gene`, `reference_gene`, `calibrator`,
  `contrast`, `n`, `censored_n`, `log2_fold_change`, `fold_change`, `interval`,
  `samples`. Count maps use condition names and integer values. An interval is
  `unavailable` or an object with `lower`, `upper`, `confidence`, `df`. Each sample
  quantity has `sample_id`, `biological_id`, `condition`, boolean `censored`,
  `log2_relative_quantity`, `relative_quantity`; censored quantities are
  `unavailable`. All reported values must agree with recomputation.
- `qpcr-evidence-v1`: `records`, each with `id`, `kind`, `result`, `origin`,
  `source` identity. Origin is internal, external, independent or preregistered.
  Noninternal sources must have both a path and hash distinct from all study
  records, including the entry pack, protocol, table, report and evidence files.
  This anti-alias check does not establish real independence.
- `qpcr-result-v1`: `status` of `arithmetic-only`, `review` of `unavailable`,
  `stages`, `exploratory`, `computation`, `claims`, `inputs` identities,
  `limitations`, and the three common local fields. Printed only; no writes.
- `qpcr-negative-fixtures-v1`: test-only `cases`, each with `id`, refusal `code`,
  `base` fixture directory and `changes`. Each change has `target`, `path`,
  `value` and optional boolean `remove`. These synthetic mutation instructions
  are test data, never execution authority or a global record schema.

Claims are separate local entries with `id`, `kind`, `status`, `text`, `evidence`
IDs. Supported, replicated, suggestive, planned, conflicting, unsupported,
withdrawn and unavailable are accepted status spellings subject to the gates
below. The pack does not extend the coordinator's global claim-register schema.

## Limits

The module constants enforce limits before work scales with each dimension:
`MAX_BYTES` 64 MiB per artifact, `MAX_TOTAL_BYTES` 256 MiB across distinct inodes,
`MAX_TOTAL_NODES` 4,000,000 preparse JSON values across the bundle,
`MAX_ARTIFACTS` 256 paths, `MAX_DEPTH` 64 nesting levels, `MAX_ITEMS` 20,000 items
per JSON container, `MAX_TEXT` 4096 characters per key or string,
`MAX_SAMPLES` 256 samples, `MAX_GENES` 32 total genes including the reference,
`MAX_WELLS` 10,000 total wells, `MAX_DILUTIONS` 64 dilution points per assay,
`MAX_TECHNICAL_REPLICATES` 16 per sample, `MAX_RECORDS` 128 claims or aggregate
evidence records, and absolute `MAX_NUMBER` of ten to the power 100.
The preparse allowance conservatively counts the root, commas and nonempty
containers with a streaming match iterator, before JSON allocation. Counts can
overestimate values when strings contain punctuation. It never allocates a
match list. No aggregate byte or node budget is charged twice for a hardlink.

## 01-freeze

Accepted input: hashed `qpcr-protocol-v1` and the coordinator research contract.
Use the existing manifest plan step shape in `references/plan.json`, one
checkpoint per run, and `$science-provenance` for hash identities. Output:
frozen protocol artifact and checkpoint. Freeze all fields above before Cq table
read; missing dilution data, replicate structure or reference choice refuses.
Hashes and the freeze declaration check consistency, not historical timing.
Human gates apply only to interpretation-changing choices or the restricted
actions listed below; routine in-scope inspection proceeds.

## 02-qc

Accepted input: protocol identity and `qpcr-cq-table-v1` identity. The validator
recomputes each assay's least-squares Cq slope against log10 input. Amplification
factor is ten to the power negative one divided by slope; efficiency is factor
minus one. Report R-squared from the same points. Require at least three distinct
dilutions, nonzero input and Cq variance, negative slope, and efficiency within
the frozen inclusive range, itself bounded from 0.01 through 2. Slopes producing
a factor above 3 refuse. No assumption of 100 percent efficiency, no out-of-range
correction override. Dilution log10 input is bounded from negative 12 through 12.

NTC passes only with `undetermined` or Cq strictly above `ntc_min_cq`. Every assay
needs an NTC. Equality is a failed control. For each biological sample and gene,
technical spread is the largest minus smallest finite Cq, including detected and
late finite values. It must be at most the frozen maximum; a rounding tolerance
of one trillionth of a cycle is allowed. Do not average a failed group. If any
technical well is undetermined or at or above `detection_cq`, the entire sample
quantity for that gene is censored. Keep the original wells and censored count.
Output: retained table and QC reflected in a recomputed summary; refusal preserves
the entire original bundle. The CLI does not create a QC file or repair inputs.

## 03-quantification

Accepted input: the same frozen protocol and admitted table identities. Call
`reference_computation`; it is CPU-only and stdlib-only, with no stochastic draw.
For each sample, take the mean Cq of clean technical replicates. Normalized log2
quantity is reference mean Cq times log2 reference amplification factor minus
target mean Cq times log2 target amplification factor. Subtract the calibrator
condition's mean normalized quantity from each sample's normalized quantity.
Exponentiating base two gives relative quantity against that calibrator.

The condition estimate is mean contrast normalized quantity minus mean calibrator
normalized quantity. Its fold change is two to that power. Biological n counts
detected independent samples; report censored n separately. Censored units are
omitted from detected-value estimates and never treated as zero or Cq 40.
If a condition has no detected biological units, refuse. If either condition has
fewer than three detected units, preserve the estimate with an `unavailable`
interval. This is not evidence of absence or significance.

Otherwise require nonzero variance in each condition and refuse uncertainty
below floating-point resolution. Divide each unbiased
sample variance by biological n; their sum is squared standard error. Welch
degrees of freedom are the square of that sum divided by the sum of each squared
component divided by its condition's n minus one. Scale the components before
squaring to avoid underflow. Use the two-sided Student-t
97.5 percentile for that degree of freedom and multiply by standard error for
the 95 percent margin. The bounded reference evaluates incomplete beta and
bisects the quantile; it never substitutes a normal approximation. Output:
complete summary rows within `qpcr-report-v1`. No multiplicity-adjusted,
paired, longitudinal or geNorm inference is implemented.

## 04-summary

Accepted input: protocol, table and report identities. The validator compares
every reported quantity, interval, integer n and sample censor flag against
recomputation. Require an interval field even when unavailable. Refuse any
provided interval for n below three. Output: `qpcr-result-v1` on stdout, with
every admitted input's hash, all five ordered stage IDs and review unavailable.
The checked-in expected artifact and hand calculations are software criteria.
No installation, remote execution or heavy compute is required.

## 05-handoff

Accepted input: all immutable input and result identities, claim-register entries,
controls, exclusions, negative cases and execution record. Existing
`$science-provenance` registers local records as ordinary artifacts; existing
`$science-review` alone owns independent record, source and method review.
Rigor classification stays with the coordinator. The pack cannot grant review
approval, material interpretation, publication or a new execution privilege.
Human approval gates occur before installation, restricted transfer, new hosts,
GPU, remote or heavy compute, or interpretation-changing choices only.

## Claim boundaries

Refuse causal, therapeutic, clinical-action, efficacy or mechanistic language in
claim text and the headline regardless of the declared claim kind. The English
lexical gate is conservative, case insensitive and incomplete; whole words and
words beginning with these prefixes are refused: caus, mechanis, therap, clinic,
efficac, effective, treat, cure, prevent, recommend, prescri, bind, affinit,
inhibit, activat, regulat, driv and induc. This includes drive and drives.
It also refuses biomarker words, target validity, physical validity and truth.
Negation does not bypass the gate; unlisted paraphrases still need human review.

Positive statuses supported, replicated and suggestive cannot cite a record whose
declared kind or result indicates review, approval, computation, calculation, arithmetic, numerical
agreement, physical or clinical validity, or truth. `replicated` is always refused
because one synthetic bundle cannot establish independent replication.
Any cited record with kind or result `unavailable` requires status `unavailable`,
even when mixed with observed evidence. Empty evidence also requires unavailable.
Unavailable text must not assert supported, replicated, suggestive or significant
findings, and must pass the same forbidden language gate. Missing evidence is
never negative evidence; review approval is never truth; computation is never
physical or clinical validity; association is never causality.

## Acceptance, concurrency and interruption

The redistributable synthetic fixture has two conditions, three biological units
per condition, two technical wells per assay and two NTC wells. Target efficiency
is 1 and reference efficiency is 0.9. Its hand-derived log2 fold change is one
minus log2 of 1.9, fold change is 2 divided by 1.9, and Welch degrees of freedom
is 4. The 95 percent margin is the Student-t quantile at 4 degrees of freedom
times the square root of two thirds. The small-n fixture has two units per
condition and an unavailable interval. `negative-cases.json` names seeded
refusals, including a failing NTC. The focused test module is
`tests/test_workflow_qpcr_pack.py`.

A second concurrent invocation reads the same immutable inputs and has no
shared write state. Killing validation between reads leaves every file unchanged
and no result artifact; any partially captured stdout is not an admitted record.
Fixture files, plan, metadata, docs and benchmark are checked-in artifacts, not
runtime writes. Editing one requires regenerating dependent hashes before use;
a partially updated bundle refuses. No older runtime wrote these new local
schemas; no existing stored record class changes validation or review behavior.
