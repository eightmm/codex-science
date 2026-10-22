---
name: bindcraft-binder-design
description: "Run a pinned BindCraft campaign for de novo protein binders using AlphaFold2 optimization, ProteinMPNN, PyRosetta, and configurable filters. Use only when the target structure, hotspot strategy, candidate budget, dependency licenses, and experimental handoff are explicit."
license: MIT
---

# BindCraft Binder Design

Use `$cx-modeling-problem-execution` for a concrete target and continue through
pilot, campaign, filtering, orthogonal validation, and review.

## Decision contract

Before compute, record the target and structure source, intended binder function,
hotspot rationale and numbering, candidate and final-design budgets, compute
envelope, selection criteria, and experimental non-goals. Define falsifiers such
as failed interface geometry, target-specificity concerns, or failure to
reproduce the pilot. Treat ranking and filters as prespecified selection rules.
Call design scores computational evidence only; experimental binding, expression,
and function each require their own assay and controls.

## License and gate

Ask once before running the installer, using conda/mamba, downloading AlphaFold2
weights, accepting PyRosetta terms, and launching GPU/Slurm compute. Pin BindCraft
release/commit and every dependency; state target, candidate/final-design budget,
wall time, storage, and experimental non-goals. Check the terms for code, weights,
and dependencies separately; MIT for this skill's code does not grant rights to
AlphaFold2 weights or PyRosetta.

## Reference usage

Read [references/bindcraft-evidence.md](references/bindcraft-evidence.md) before
choosing filters, interpreting model confidence or interface metrics, comparing
campaigns, or making any claim about predicted binder quality. It defines claim
classes, dependence, controls, uncertainty, sensitivity, and applicability.

## Workflow

1. **Gate (ask before proceeding).** Before installer/conda/mamba use, weight
   download, PyRosetta terms acceptance, or GPU/Slurm compute, present the pinned
   release, target, design budget, estimated resources/storage, and terms; record
   approval or stop without executing the gated action.
2. Audit target structure, assembly, chain/residue numbering, missing regions,
   ligands, hotspot rationale, intended epitope, binder length, and plausible
   off-targets; continue only if the binding surface is interpretable, and record
   source identifiers, hashes, and unresolved structure caveats.
3. Pin release/commit, checkpoint hashes, dependencies and licenses, settings,
   filter/advanced JSON, algorithm, seeds, stop criteria, ranking rule, and
   resources; proceed only when the configuration matches the declared objective,
   and record the frozen manifest before the pilot.
4. Run the matching official example and a small target-specific pilot; continue
   only if the command completes and outputs pass basic structure/sequence
   integrity checks, and record all attempts, failures, and resource use.
5. Run the approved campaign into `artifacts/<run-id>/bindcraft/`; retain every
   trajectory, sequence, structure, metric, config, log, candidate ID, and reject;
   stop at the declared budget and record the complete generation denominator.
6. Apply prespecified filters and rank candidates only when required fields and
   thresholds are available; report counts and exclusion reasons at every stage,
   plus all generated candidates as the denominator to expose selection effects.
7. Re-score finalists with a predictor independent of the design trajectory and
   evaluate diversity, novelty, interface geometry, clashes, confidence, and
   off-target hypotheses; call agreement computational support only, and record
   model/version, scRMSD or relevant structural comparison, each metric,
   disagreement, and failure reason.
8. Vary seeds, hotspot choices, noise/settings, and filter thresholds; treat
   changes in retained candidates, ranks, or conclusions as sensitivity, and
   record the prespecified perturbations and resulting funnel.
9. Verify the manifest, hashes, denominators, evidence statuses, and claim-to-file
   links; preserve inputs and outputs with `$science-provenance`, then use
   `$science-review` before candidate selection, and record the review receipt and
   any unresolved findings.

## Outputs

Produce one `binder-design-evidence-v1` record containing: run identifier
(`run_id`); target and structure identifiers/hashes (`target`); pinned tool,
weight, and dependency identities/terms (`software`); frozen configuration and
resource envelope (`configuration`); seeds (`seeds`); candidate identifiers and
stage denominators (`funnel`); per-candidate metrics, exclusions, and reasons
(`candidate_evidence`); observed resource use (`resource_use`); control and sensitivity results (`controls` and
`sensitivity`); claim identifiers, classes, statuses, evidence, and limitations
(`claims`); uncertainty and applicability limits (`uncertainty` and
`applicability`); unresolved risks (`unresolved_risks`); smallest falsifiable
experimental or computational next step (`next_step`); artifact paths/hashes
(`artifacts`); provenance and review receipts (`handoffs`). Assign each material
claim an ID and status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- ipTM and in-silico filters are not affinity or experimental validation.
- Predicted interface quality does not establish expression, folding, specificity,
  function, safety, or wet-lab success.
- Do not auto-order or synthesize candidates. PyRosetta and model assets have
  separate terms; this skill does not grant commercial rights.
- Report the full funnel and rejected candidates; survivor-only rates conceal
  selection and denominator effects.
- A reference describes method interpretation; it is not evidence that a design
  binds the target.
