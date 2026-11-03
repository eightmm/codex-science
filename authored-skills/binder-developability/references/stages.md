# Stage contracts

## intake

Freeze binder class, construct/chain sequences, target and protected framework/disulfide positions.

## plan

Choose sequence/structure/assay analyses and freeze user-declared limits, matched panel endpoints and controls.

## pilot

Validate chain and residue maps; check controls and optional external predictor compatibility.

## sequence

Compute chain-local sequence observations without assigning uncalibrated developability probabilities.

## panel

Evaluate complete construct-matched on/off-target response panels, retaining predicted versus measured source kind.

## select

Apply explicit limits and control outcomes; retain all rejected and unavailable cases with reasons.

## review

Review computational evidence and propose expression, aggregation or specificity measurements as appropriate.

## Pack-local record

The input has `schema_version: 1`, frozen `contract` and canonical
`contract_sha256`. Contract fields include `binder_class` (`minibinder`, `VHH`,
`paired_Fv`), `target_id`, optional `source_chains`, `limits`, and nullable `panel`.
For VHH the source/candidate chains must be H; paired Fv requires H and L. Every
source chain carries `sequence` and nonempty, unique one-based
`protected_positions`. The supplied set must include the intended framework and
disulfide constraints; the helper cannot annotate these positions. No insertion or
deletion mapping is inferred: length changes require the binder-design campaign's
source-residue mapping validation before a new mapped contract is supplied.

Candidates have unique `id`, `construct_id` and canonical uppercase `chains`.
Repeated chain/sequence identities are refused. Observations are chain-local
length, Cys positions, aromatic residue counts (F/W/Y), K/R minus D/E residue
count (not net charge or pI), and overlapping N-X-S/T tripeptides with X not P.
This tripeptide observation is not a PROSITE database implementation and does
not include a fourth-residue exclusion. It is neither a glycosylation prediction
nor proof of a glycan. Motifs never bridge two chains. `limits` may contain
`max_nglyco_sequons`, `max_aromatic_fraction`, and
`max_basic_minus_acidic_count`; all are explicit user choices, never universal
biophysical acceptance thresholds.

A `panel` declares nonempty distinct `off_target_ids`, common `assay_id`, `unit`,
`metric`, `source_kind`, `direction` (`higher`/`lower` means stronger response) and
finite `minimum_margin`. Each candidate's `panel_results` has at most one result
per declared target and each row carries the exact `construct_id` plus endpoint
identity and finite `value`. Missing targets make the panel unavailable and
exclude that candidate. For higher-is-stronger, margin is on-target minus each
off-target; reverse for lower-is-stronger. Margins are response differences in
the declared unit, not binding free energies or affinity ratios. Aggregated
replicate results must be computed upstream using an explicit uncertainty model;
this helper accepts one declared estimate per endpoint and does not infer assay
replicate independence.

Controls have unique IDs and boolean `passed`; absent/failed controls prevent
retention and admissible panel-margin conclusions, while preserving observations.
No panel permits sequence-only triage but explicitly leaves selectivity unavailable.
A predicted/computed panel cannot establish experimentally measured selectivity.

## Output and acceptance

Sequence observations and supplied matched-panel margins only; no TAP/TNP execution, aggregation/solubility/expression/immunogenicity predictor, antibody annotation, independent assay or clinical assessment.

The synthetic fixture exercises `binder-developability-result-v1` only. Preserve every candidate and
exclusion reason; zero survivors and unavailable endpoints are valid outcomes.
A frozen hash detects edits, not prospective preregistration or authentic assays.

## Execution and measured-outcome handoff

See the shared [campaign guide](../../../docs/CAMPAIGN_WORKFLOWS.md) for
`scripts/run_campaign.py` with explicit local stage inputs, code, outputs and
dependency records, and `capture_campaign_runtime.py` for actual executable and
model/database file identities. These interfaces do not turn a supplied panel
into a newly executed assay.

Later assay feedback uses a separate contract for
`scripts/import_campaign_feedback.py CONTRACT.json ASSAY.csv`. Keep binder
candidate/construct IDs distinct from the target construct; match the exact assay,
unit and replicate identity, preserving failures/censoring. Holdout outcomes may
evaluate predictions but cannot update candidate selection. A handoff must not
silently rename this pack's `contract` to the feedback schema.
