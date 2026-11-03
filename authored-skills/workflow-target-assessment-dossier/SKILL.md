---
name: workflow-target-assessment-dossier
description: "Build an evidence-based target and indication assessment through six fixed stages, identity and dependency gates, an unreviewed go/no-go memo and independent review handoff. Use existing source skills with recorded evidence; do not use for patient treatment, structure prediction, molecule generation or compute execution."
license: MIT
---

# Target Assessment Dossier

Role: conductor. This pack fixes the order, evidence boundaries and handoffs of
existing skills. Their source procedures remain authoritative; this pack adds
no connector, execution engine or global record contract.

## Decision contract

Before inspecting outcomes, freeze target UniProt, Ensembl and HGNC identifiers,
species, isoform, indication ontology ID, population, tissue/cell state, evidence
cutoff, source releases, proposed modality, permitted inference and claim IDs.
Retain submitted labels, mapping alternatives and exclusions using
`$cx-biomedical-entity-normalization`. Unresolved species, isoform or disease
identity stops interpretation; never silently substitute a related entity.

The decision is whether the evidence justifies the smallest discriminating next
experiment, a hold, or no-go. A go is a research prioritization decision and
requires at least one declared independent genetic group and zero open critical
liabilities. It establishes neither efficacy nor clinical readiness. Freeze
controls, readouts, falsifiers, inclusion rules, dependency grouping and the
experiment decision rule before outcomes are seen. Record uncertainty and the
weakest essential evidence link; retain rejected alternatives.

The coordinator selects rigor and owns one existing checkpoint per run, with
ordered IDs `stage-01` through `stage-06`. Use the existing manifest `plan` step
shape from [the plan template](references/plan.json), keeping its pending state
until work actually finishes. Do not create a checkpoint for each source.

## Reference usage

Read [stages and record contract](references/stages.md) before freezing inputs,
building any handoff, comparing evidence or validating the dossier. Read
[the plan template](references/plan.json) before registering the six manifest
steps. Select these routes through `references/index.json`. Record materially
controlling reference paths and SHA-256 hashes in a `reference-use-ledger` with
`$science-provenance`; references guide procedure and are not scientific evidence.

## Workflow

1. **Identity ledger.** Reuse `$cx-biomedical-entity-normalization` for the frozen
   target and indication. Record source identity, species, isoform, mapping
   alternatives and rejected matches before interpreting evidence.
2. **Genetic and association evidence.** Reuse `$cx-opentargets-search`,
   `$cx-gwas-catalog-search`, `$cx-gnomad-search` and `$cx-clinvar-search`.
   Preserve cohort, population, direction, source propagation and dependency
   groups. Two portals sharing one cohort count once. Absence of a record is
   `unavailable`, never negative evidence or no association.
3. **Expression and context.** Reuse `$cx-expression-cell-context`,
   `$cx-hpa-search` and `$cx-gtex-search`. Keep tissue/cell state, assay, unit,
   normalization and population attached to each record. RNA expression does
   not establish target dependence or protein activity.
4. **Structure and chemical matter availability.** Reuse `$cx-pdb-search`,
   `$cx-alphafold-structure-analysis`, `$cx-chembl-search` and `$cx-pubchem-search`
   solely for recorded availability. Do not launch prediction or generation.
   An available structure or ligand does not establish druggability. Keep IC50,
   Ki and percent inhibition, assay conditions and units separate unless an
   explicit per-record normalization and rationale are preserved for review.
5. **Safety, tractability and competition.** Reuse `$cx-openfda-search`,
   `$cx-clinical-trials-search`, `$cx-translational-pharmacology-evidence` and
   `$cx-indication-dossier`. Preserve failed controls, negative results,
   terminated programs, uncertainty and open liabilities. A registration is not
   a result; an adverse-event report is not causal evidence.
6. **Decision memo and review handoff.** Reconcile modality with genetic effect
   direction, citing an explicit rationale for disagreement or unknown direction.
   Write go, no-go or hold; disclose every liability and the smallest controlled,
   falsifiable next experiment. Run `python3 scripts/validate_target_assessment_pack.py
   <bundle-directory>` from the plugin root. Correct all findings as one batch
   or downgrade/hold the decision. Register artifacts with `$science-provenance`
   and hand off contract, source snapshots, dependency records, exclusions,
   claim register, controls, limitations and hashes to independent `$science-review`
   in record, source and method modes. The pack always returns review pending.

For offline replay, use the labelled synthetic bundle at
`examples/workflow-target-assessment-dossier/synthetic/`; no connector is called.
For any separately authorized retrieval, load the existing named skill before
using it, start with the smallest discriminating query, and preserve its exact
query, release, response and hash. Follow its bounded retry rules; do not invent
a response, download a replacement, or retry unavailable essential evidence
indefinitely. Record unavailable evidence and block only dependent claims.

## Outputs

Return `dossier.json` (`target-assessment-pack-v1`), `snapshots.json`
(`target-assessment-snapshots-v1`), and six ordinary domain records named
`stage-1.json` through `stage-6.json` (`target-assessment-stage-v1`). Each stage
binds immutable input paths plus SHA-256 hashes and names its source records.
The memo is the sixth stage record; machine-readable claim text uses literal
source attribution so unsupported paraphrases are refused.

Also return the separate existing `claims.json` claim-register sidecar, the
single coordinator checkpoint, manifest, assumptions, dependencies, conflicts,
exclusions, uncertainty, applicability limits and reference-use ledger. Register
domain records as ordinary artifacts with a descriptive kind, never as a
claim-register. Domain observations use `recorded` or `unavailable`; claim
adjudication uses the existing claim-register statuses. A replicated memo claim
requires two independent groups or sources after merging shared dependencies.
Schema and policy versions use real integers; booleans and floats are refused.
No new global schema or receipt key is introduced. Hash changes invalidate downstream handoffs and
require a new review packet under the coordinator's existing rules.

## Boundaries

- Refuse identity mismatch across sources, dependent cohorts counted as
  independent support, availability promoted to druggability, unnormalized
  mixed potency measurements, and absent records reported as no association.
- Refuse genetic direction/modality disagreement without a cited rationale,
  go with any open critical liability, and claims stronger than cited evidence.
- Association is never causality; numerical agreement is never physical or
  clinical validity; independent review approval is never scientific truth.
  The validator refuses those inference classes and retains failed/negative
  records. Its pass is record consistency only, not empirical validation.
- The memo never recommends treatment for a patient and must contain:
  `This memo never recommends treatment for a patient.`
- Proceed on approved, reversible offline work. Human gates apply before
  installation, restricted transfers, new hosts, GPU/remote/heavy compute or
  interpretation-changing choices. This pack itself implements none of those
  actions. Missing evidence is a scientific limitation, not a new permission.
- Preserve failures and null results; do not repair source identities or hide
  controls to obtain a go. Unresolved essential evidence keeps affected claims
  unavailable or unsupported. The coordinator owns rigor and independent
  review; this pack cannot mark its own output reviewed.

L4 covers deterministic synthetic acceptance checks only. It does not establish
live connector fidelity, semantic completeness or biological validity.
