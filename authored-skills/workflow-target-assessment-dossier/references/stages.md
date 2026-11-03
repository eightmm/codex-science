# Fixed stages and pack-local records

All checked-in inputs, outputs and negative cases are synthetic fixtures. None
contains a real target, cohort, clinical conclusion or patient recommendation.
This document controls workflow order and internal attribution, not scientific
truth. Existing source skills own query syntax, source caveats and execution
limits; do not restate or replace their procedures here.

## Common handoff and decision rules

Before inspecting outcomes freeze the question, identity, population, cutoff,
modality, inclusion/exclusion rules, cohort and source dependency groups,
controls, uncertainty rule, assay scales and decision thresholds. For this v1
record contract a research go requires at least one independent genetic group
and zero open critical liabilities. A hold or no-go may retain zero support.
Do not change thresholds to fit outcomes; interpretation-changing changes need
a recorded coordinator decision and a new protocol revision.

The coordinator creates one checkpoint using the existing checkpoint API, with
IDs `stage-01` through `stage-06`, and uses the existing manifest `plan` list in
`plan.json`. The example uses a valid legacy schema-v1 checkpoint to demonstrate
compatibility; real runs use the coordinator's current writer. The pack does
not write, advance or complete checkpoints, classify rigor, invoke connectors,
perform compute or create review receipts.

An artifact reference is exactly `{"path": "relative-file", "sha256": "64 lowercase hex"}`.
Paths must be canonical relative POSIX paths inside the bundle, without symlinks
or parent traversal. Every input must be a regular file, checked with `lstat`
before opening; FIFOs and other special files are refused with `PACK_INPUT`.
The per-file limit is 64 MiB (67,108,864 bytes), inclusive, checked before and
after reading. This includes the dossier, snapshots, stages and existing
checkpoint and claim-register sidecars. Hash the actual UTF-8 file bytes,
not reserialized JSON; parse those same bytes.
Stage 1 accepts the snapshot reference. Every later stage accepts that same
snapshot reference followed by the preceding stage output reference. Preserve
the original file and record; create a new revision when inputs change. Rebuild
downstream hashes and invalidate review rather than editing a reviewed bundle.

Register every domain record, raw snapshot and memo as an ordinary hashed
artifact with a descriptive kind such as `target-assessment-domain-record`.
Keep `claims.json` a separate existing `claim-register` sidecar and bind its IDs
and text to the memo; manifest claim IDs must match under the coordinator's
ordinary bundle validation. No domain JSON is a nested claim-register.

## Stage 1: identity

- Accepted input: `snapshots.json` plus its SHA-256, with submitted labels and
  source-specific identities; freeze the canonical identity before outcomes.
- Reuse `$cx-biomedical-entity-normalization` and its existing mapping protocol.
- Output: `stage-1.json`, schema `target-assessment-stage-v1`, ID `stage-01`.
  Data includes `target`, `rejected_alternatives`, source IDs and observations.
- Controls: exact UniProt/Ensembl/HGNC, species, isoform and disease ontology
  identity match across all sources; zero unresolved identity substitutions.
- Failure: `TARGET_IDENTITY`; retain alternatives and stop dependent synthesis.
  A decision changing species, isoform or disease scope needs human resolution.

## Stage 2: genetics and association

- Accepted inputs: snapshot and `stage-1.json` references, each path plus hash.
- Reuse `$cx-opentargets-search`, `$cx-gwas-catalog-search`, `$cx-gnomad-search`
  and `$cx-clinvar-search` with the fixed cutoff and population.
- Output: `stage-2.json`, schema `target-assessment-stage-v1`, ID `stage-02`.
  Data adds `support_record_ids` and `independent_support_count`.
- Controls: source cohorts and propagation groups determine connected
  dependency groups, including transitive overlap. Multiple records from one
  source remain dependent. Unknown cohorts share an unresolved group rather
  than claiming independence. Declared support is a nonnegative integer no
  greater than the number of independent selected groups. Count only recorded
  associations; empty source results remain unavailable.
- Failure: `GENETIC_DEPENDENCE` or `SOURCE_UNAVAILABLE`. Preserve null and negative
  results; a missing association record cannot support no association.
  No routine permission gate is added here.

## Stage 3: expression and context

- Accepted inputs: snapshot and `stage-2.json` references, each path plus hash.
- Reuse `$cx-expression-cell-context`, `$cx-hpa-search`, `$cx-gtex-search`.
- Output: `stage-3.json`, schema `target-assessment-stage-v1`, ID `stage-03`.
  Source rows retain tissue, cell state, assay, unit, normalization and donor
  count within their recorded `context`. Preserve source-specific population
  and baseline/disease scope; no cross-assay numerical aggregation is provided.
- Controls: exact target identity and complete observation retention; use the
  existing expression skill for assay sensitivity, controls and applicability.
- Failure: `EXPRESSION_CONTEXT` for missing context or a donor count that is not
  a positive integer. Keep unmatched contexts separate, downgrade affected
  claims and record unavailable evidence; interpretation-changing choices require
  a coordinator decision. No extra gate for ordinary record inspection.

## Stage 4: structure and chemical matter availability

- Accepted inputs: snapshot and `stage-3.json` references, each path plus hash.
- Reuse `$cx-pdb-search`, `$cx-alphafold-structure-analysis`, `$cx-chembl-search`
  and `$cx-pubchem-search` for existing record availability only.
- Output: `stage-4.json`, schema `target-assessment-stage-v1`, ID `stage-04`.
  Data adds `interpretation: "availability-only"` and `potency_groups`.
- Controls: no availability-to-druggability inference; keep experimental versus
  predicted provenance in source statements. Never run prediction or generation.
  A potency record retains `potency: {assay, unit, value}`; values must be finite
  nonnegative JSON numbers, including zero. Never mix IC50, Ki, percent
  inhibition or units in one comparison without explicit normalization.
- A comparison group is `{record_ids, normalisation}`. Use null normalization
  only for a common assay and unit. A mixed group must preserve
  `{rationale, assay, unit, values}` where values maps every cited record ID to
  a finite nonnegative normalized number. This records an explicit proposed
  common endpoint and rationale; it does not certify conversion accuracy or
  assay equivalence. Independent method review must assess those assumptions.
  Separation by assay/unit is the default and needs no conversion.
- Failure: `AVAILABILITY_NOT_DRUGGABILITY` or `POTENCY_MIXING`; retain raw values
  and separate incompatible records. A normalization changing interpretation
  requires a coordinator decision before comparison.

## Stage 5: safety, tractability and competition

- Accepted inputs: snapshot and `stage-4.json` references, each path plus hash.
- Reuse `$cx-openfda-search`, `$cx-clinical-trials-search`,
  `$cx-translational-pharmacology-evidence` and `$cx-indication-dossier`.
- Output: `stage-5.json`, schema `target-assessment-stage-v1`, ID `stage-05`.
  Data adds liabilities `{id, severity, status, evidence}`. Severity is
  critical, major or minor; status is open or closed; evidence cites source
  record IDs. Freeze severity criteria before reviewing outcomes.
- Controls: failed controls, terminated programs, negative results and safety
  signals remain in snapshots and observations. Distinguish source availability
  from absence of liability; the checklist is not proof of safety.
- Failure: `EVIDENCE_PRESERVATION` when records are hidden. Keep open liabilities
  visible and carry them forward. No gate merely because evidence is adverse.

## Stage 6: decision memo and independent handoff

- Accepted inputs: snapshot and `stage-5.json` references, each path plus hash;
  earlier stages remain transitively bound, with all outputs listed in dossier.
- Reuse the coordinator's `$science-provenance` and independent `$science-review`
  workflows; no second source retrieval or self-issued review approval.
- Output: `stage-6.json`, schema `target-assessment-stage-v1`, ID `stage-06`.
  Data adds decision, modality, direction rationale, claims, next experiment,
  patient boundary and review handoff. Decision is go, no-go or hold. Modality
  is inhibition or activation. Go means research prioritization only.
- Direction controls: protective loss of function or risk-increasing gain of
  function aligns with inhibition; protective gain of function or risk-increasing
  loss of function aligns with activation. Unknown, mixed or opposite evidence
  needs `{text, evidence}` citing every mismatched genetic record. This is an
  explicit rationale for review, not proof of a mechanism.
- Claim controls: each memo claim has `{id, text, kind, evidence, status}`.
  Kind is descriptive or associational; association requires association-kind
  source records. Text is exactly the cited record statement, or their ordered
  concatenation separated by `; `. This conservative attribution refuses an
  unsupported paraphrase without pretending to understand unrestricted prose.
  Do not place unregistered material claims in narrative or rationale fields.
  Claim statuses follow the existing sidecar contract; text, status and
  permitted inference must match that separate sidecar.
  A supported, replicated or suggestive claim cannot cite computed or
  review-approval records regardless of its declared kind. The text of such a
  claim also refuses the four whole words `efficacy`, `effective`, `effectiveness` and `efficacious`,
  case-insensitively, with `MEMO_OVERCLAIM`. This narrow lexical check does not
  interpret negation or synonyms; other wording still needs independent review.
- Next experiment requires nonempty question, control, readout, falsifier and
  decision_rule. This describes the smallest discriminating experiment and
  grants no permission to run it. Preserve limitations, alternatives,
  applicability, exclusions and conflicts in the review packet.
- Require `patient_treatment_recommendation: false`, boundary text exactly
  `This memo never recommends treatment for a patient.`, and
  `review_handoff: "$science-review"`. Root review status stays pending.
- Failure: `MODALITY_DIRECTION`, `CRITICAL_LIABILITY`, `MEMO_OVERCLAIM`,
  `PATIENT_BOUNDARY` or `INDEPENDENT_REVIEW`. Fix findings or hold affected
  conclusions. A go with an open critical liability is always refused.
  Association cannot become causality; numerical agreement cannot become
  physical or clinical validity; review approval cannot become truth.

## Schema and validation entry point

`target-assessment-pack-v1` is a pack-local root object requiring schema,
synthetic (boolean), target, snapshots, stages, checkpoint, claim_register and
review_status. Target contains exactly uniprot, ensembl, hgnc, species, isoform
and indication_id, all nonempty strings. Stages is six ordered objects each
with id and output reference. Checkpoint and claim_register are references to
existing schema records; no field is added to those existing contracts.

`target-assessment-snapshots-v1` requires schema, matching synthetic label and
sources. Each source requires unique id, existing skill, release, exact query,
target, cohorts, dependency_groups and records. Record IDs are globally unique;
each has kind, result and literal statement. Kinds are descriptive,
associational, computed or review-approval. Results are identity, association,
no-association, availability, expression, safety-signal, failed-control, negative,
numerical-agreement or review-approval. Genetic records add effect perturbation
and outcome; expression records retain context; potency records retain potency.
An empty records list means unavailable; an explicit returned negative remains
a recorded negative rather than being erased.

`target-assessment-stage-v1` requires schema, id, matching synthetic label, inputs
and data. Every data object has source_ids and observations. An observation has
source_id, record_ids in source order, and status recorded or unavailable. Each
source belongs to exactly one stage and every returned record is retained.
Stage-specific data is described above. Additional source details can be retained
without promoting them to new global fields.

`target-assessment-benchmark-v1` is the frozen, synthetic test-task manifest in
`benchmarks/workflow-target-assessment-dossier/tasks.json`. Tasks name fixture,
question, expected finding, acceptance criteria and CPU/network/GPU budgets.
It is not an execution engine or a change to existing benchmark contracts.

Run from the plugin root:

```sh
python3 scripts/validate_target_assessment_pack.py examples/workflow-target-assessment-dossier/synthetic
```

The public Python entry point is `validate_target_assessment_pack(directory)` in
`codex_science.target_assessment_pack`. Success returns status passed with review
pending and a record-consistency boundary. Refusals are labelled ValueError
messages; the thin CLI returns JSON with status refused, finding and message,
and exits 1. It never emits a traceback for malformed input. No network,
dependency installation, download, GPU or remote action is present.

## Failure handling and concurrency

Preserve original snapshots, failed controls, negative results and unavailable
sources. Resolve identity before restarting dependent stages; batch corrections
and retry validation once, then surface the remaining blocker. Never weaken a
check, delete evidence or relabel an unavailable source to pass.

The library and CLI only read. Two concurrent calls leave inputs unchanged;
termination between reads leaves no partial output or lock. Each file is hashed
and parsed from the same bytes and rehashed before success to detect concurrent
edits. The final read repeats regular-file and size checks; an unsafe replacement
is `PACK_CHANGED`. Concurrent authors must publish a complete new immutable bundle; this
validator provides no multi-file transaction or defense against a malicious
writer restoring old bytes between checks. The checkpoint writer and review
receipt lifecycle remain owned by existing coordinator APIs.

Human gates occur only before installation, restricted transfer, a new host,
GPU/remote/heavy compute or an interpretation-changing decision. The offline
fixture replay requires none. Independent review remains mandatory for material
conclusions and may find semantic or scientific defects these record checks miss.
