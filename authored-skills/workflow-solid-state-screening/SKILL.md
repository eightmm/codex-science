---
name: workflow-solid-state-screening
description: "Conduct CPU materials-model screening through fixed normalization, analytic control, convergence, uncertainty-aware ranking, and independent review stages. Use for supplied solid-state models and synthetic offline controls; the bundled tight-binding reference checks stage contracts, not materials-property accuracy."
license: MIT
---

# Solid-State Screening Workflow

Role: conductor composed with existing units, solid-state, numerical-validation,
and uncertainty skills. The offline reference is a synthetic open tight-binding
chain. It validates the workflow contract, not materials-property accuracy.

## Decision contract

Before outcomes are seen, freeze the supplied structure/model identity and hash,
Hamiltonian, dimensionality, boundary conditions, lattice convention, state,
observable, source and working units, candidate IDs, uncertainties, covariance
assumption, model-choice sensitivities, controls, complete refinement schedule,
and acceptance thresholds. Assign claim IDs and falsifiers. Record the evidence
cutoff and applicability domain in the coordinator contract.

The reference route minimizes lowest energy plus combined standard uncertainty;
it is a declared conservative score, without a calibrated coverage probability.
Its input/model/numerical components are assumed independent. The two synthetic
candidates and sensitivity reversal are fixtures, not a materials discovery.
Reject an unsupported model or unresolved covariance; do not silently substitute
the toy model for a supplied DFT or ML-potential calculation.

## Reference usage

Inspect [the reference index](references/index.json). Read [the stage and record
contract](references/stages.md) before normalization, control, refinement,
ranking, or handoff, and [the plan template](references/plan.json) before starting
the coordinator's single checkpoint. Copy its existing manifest `plan` step
shape, preserving ordered `stage-1` through `stage-5` IDs. Record controlling
reference paths and hashes in a `reference-use-ledger`; procedure is not evidence.

## Workflow

1. **Normalize.** Use `$cx-dimensional-analysis-units` and
   `$cx-condensed-matter-solid-state`; read their selected references. Preserve
   source structure/model path plus SHA-256, source units and assumptions.
   Produce `normalized.json`; refuse missing/inconsistent units. The offline
   reference uses the existing unit runtime to convert energy to eV and length
   to nm, without new dependencies.
2. **Pass the analytic control first.** Execute the fixed dimer limiting case
   and compare both eigenvalues with the independent closed form at the frozen
   absolute tolerance. Preserve `analytic-control.json`, including failures.
   A missing or failed control stops candidate scoring and ranking.
3. **Refine every candidate.** Use `$cx-numerical-analysis-error-control` and
   `$cx-computational-physics-validation`; retain every scheduled level,
   failed level, reference limit, numerical error and decision. Require the
   full schedule, monotone error within frozen slack, and final error within
   tolerance. Never truncate `convergence.json` to conceal non-convergence.
4. **Rank with uncertainty and sensitivity.** Use
   `$cx-experimental-uncertainty-propagation`. Include every declared component
   and the numerical error, report the score rule and independence assumption,
   and evaluate every declared model alternative. Report all order reversals
   in `ranking.json`; a reversal makes the decision model-sensitive. Label
   changed thresholds `exploratory` in normalization and the handoff.
5. **Hand off independently.** Produce `review-handoff.json` with claim
   dispositions, dependencies, conflicts, applicability, limitations, rejected
   alternatives, failed controls, negative results and the next falsifiable
   action in its coordinator sidecars. Register domain records as ordinary
   artifacts with `$science-provenance`, with separate claim-register entries.
   The coordinator owns rigor classification and `$science-review`; this pack
   leaves review pending and never attests its own output reviewed.

Run the read-only offline validator with
`python3 scripts/validate_solid_state_screening.py examples/workflow-solid-state-screening`.
An exit of zero means contract checks passed, with an explicit exploratory
status when applicable; it establishes neither physical validity nor review.
Retry only after correcting the named defect, preserving the failed snapshot
and using a new snapshot identity. Do not relax thresholds to obtain a pass.

## Outputs

- `contract.json`: `solid-state-screening-contract-v1`, frozen synthetic inputs.
- Five ordered `solid-state-screening-stage-v1` records: `normalized.json`,
  `analytic-control.json`, `convergence.json`, `ranking.json`,
  `review-handoff.json`. Each binds the contract and previous stage by path and
  hash. The exact schemas and supported offline envelope are in stages.md.
- Existing coordinator manifest, one checkpoint, claim register, reference-use
  ledger, execution/code/environment identities and independent review packet.
  These retain existing schemas; the pack adds no engine or global record keys.

The checked-in example and negative mutation cases are labelled synthetic
fixtures. `benchmarks/workflow-solid-state-screening/tasks.json` freezes their
questions, acceptance criteria and CPU budgets. Tests exercise both Python and
CLI entry points without network access.

## Boundaries

- Refuse numerical agreement promoted to physical or clinical validity,
  association promoted to causality, absent experimental records promoted to
  negative evidence, or review approval promoted to truth. Missing is
  `unavailable`; preserve failed controls and negative results.
- Synthetic spectra have no matched experimental observable. They cannot
  establish experimental agreement, a measured gap, material stability, or
  generalization to real materials. Correlated calculations are not replication.
- Missing inputs, failed controls, unconverged series, omitted uncertainties,
  hidden sensitivity reversals and unlabelled post-hoc thresholds are refusals,
  not advice. Keep unresolved scientific conclusions inconclusive/unavailable.
- DFT and ML potentials are named extension points only. Installation, restricted
  transfers, new hosts, GPU/remote/heavy compute and interpretation-changing
  choices require the coordinator's approval gate before action. None is run by
  this offline pack. Existing approval is reused within its scope; routine
  reversible stage transitions require no extra prompt.
