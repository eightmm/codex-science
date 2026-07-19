---
name: science-review
description: Independently review a scientific run by checking claims against the approved plan, saved artifacts, citations, environment, and execution record. Use after scientific analysis or writing, before presenting conclusions, and when users ask to verify calculations, citations, reproducibility, methods, figures, or evidence fidelity.
---

# Science Review

Review the record adversarially; do not assume the producing agent's conclusion, selected method, or confidence is correct.

## Inputs and review mode

Require the decision contract, approved plan, artifact manifest, claim register, query and execution logs, outputs, environment, lane receipts, cited sources, and prior findings. Report missing evidence rather than filling gaps from memory.

Declare one review mode:

- `record`: audit internal consistency and evidence fidelity without rerunning.
- `reproduction`: independently rerun specified material computations from recorded inputs.
- `method`: assess whether design, controls, metrics, assumptions, and inference support the claim.
- `source`: verify retrieval, source identity, citation attribution, study dependence, and evidence cutoff.

A review may combine modes, but never imply a computation was reproduced when only its record was inspected.

## Review workflow

1. Run `<plugin-root>/scripts/validate_artifact.py <manifest> --review-output <run-dir>/review.json` for deterministic structural checks.
2. Build a claim register from the deliverable and manifest. For each material claim, record type, inference level, supporting and contradicting evidence, dependencies, uncertainty, and required review mode.
3. Verify execution integrity: successful command and exit status, input and output hashes, code and configuration identity, environment and model revision, seed handling, log consistency, and agreement between reported values and saved outputs.
4. Verify retrieval integrity: exact query or request, source and release, access date, identifier normalization, inclusion and exclusion decisions, snapshot or response identity, source-dependency links, and whether duplicated portals expose the same underlying study.
5. Resolve every citation or persistent identifier. Confirm that the cited source supports the exact attributed claim; distinguish primary from secondary evidence, peer-reviewed work from preprints, registry entries from results, and current from superseded versions.
6. Trace every figure and table to inputs and code. Check units, axes, legends, sample or donor counts, denominators, transformations, aggregation, missingness, and consistency with raw or minimally processed artifacts.
7. Challenge the design and inference: estimand, controls, baseline, data split, leakage, pseudoreplication, confounding, multiple testing, calibration, uncertainty, sensitivity analyses, model-training overlap, applicability domain, and external-validity boundary as relevant.
8. Test alternative explanations and counterevidence. Check whether the conclusion depends on one cohort, portal, assay, microstate, threshold, model, seed, or post-hoc choice; require sensitivity analysis when that dependence is material.
9. Check every approved plan step and objective criterion. Mark incomplete, changed, exploratory, failed, blocked, or unsupported work explicitly; do not accept a moved success threshold or a process-completion claim as a scientific result.
10. Compare the deliverable with the artifact record. Flag unsupported computed claims, contradictions, overstated confidence, missing negative results, citation mismatch, stale source state, and any conclusion exceeding the weakest essential evidence link.
11. Emit findings with stable ID, severity, affected claim or artifact, evidence, rationale, required correction or validation, owner, and resolution status. Do not silently edit the producer's record.
12. Re-review corrections. Preserve the original finding, resolution evidence, and residual risk; a finding is resolved only when the changed claim or new evidence passes the same check.

## Finding severity

Use [references/review-checklist.md](references/review-checklist.md). `critical` changes trust in the run or exposes fabrication, leakage, or contradiction; `major` can change a material conclusion; `minor` affects clarity or reproducibility without changing the central result. Mark non-blocking suggestions separately.

## Receipt and independence

Save the final machine-readable receipt under the run directory with `status`, `reviewer`, `independent`, `review_modes`, `reviewed_claims`, `findings`, `limitations`, and referenced artifact hashes. Set `independent: true` only for a genuinely separate reviewer.

Use a separate subagent when available. Give it the decision contract, raw run artifacts, and approved plan without the intended answer or suspected bug. If no separate agent is available, state that the work was a second pass rather than an independent review.

After every blocking finding is resolved and `status` is `passed`, let the coordinator attach the receipt with `science_checkpoint.py review --artifact-ref <path>`; do not self-attest independence. The checkpoint validates and hashes the receipt's statement but cannot authenticate reviewer identity.

## Boundary

A record review does not rerun analyses, and deterministic validation cannot judge domain validity by itself. Reviewer success reduces inconsistencies and unsupported claims; it does not establish scientific truth, clinical validity, safety, or regulatory compliance.
