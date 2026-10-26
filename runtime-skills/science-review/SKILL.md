---
name: science-review
description: Independently review a scientific run by checking claims against the approved plan, saved artifacts, citations, environment, and execution record. Use after scientific analysis or writing, before presenting conclusions, and when users ask to verify calculations, citations, reproducibility, methods, figures, proofs, statistics, numerical results, or evidence fidelity.
---

# Science Review

Review the record adversarially; do not assume the producing agent's conclusion, selected method, or confidence is correct.

## Reference usage

Reference files are step-gated; do not read them at orientation.

- The reviewer reads [the review checklist](references/review-checklist.md) before assigning severity, deciding whether a review passes, or closing a material finding. The coordinator reads it only when resolving findings. Use the indexed headings rather than loading unrelated reference material. Do not infer a pass rule or downgrade a finding from prose convenience.
- The coordinator reads [the independent reviewer packet contract](references/independent-review-runtime.md) at review time, not at orientation: after `prepare-review` and before handing the packet to any reviewer (subagent or external), read at least its "Independence boundary" and "Review packet transport" sections (sensitive-metadata check, approved destination, data approval, independence requirements); read the rest before `science_reviewer.py finalize`, accepting a reviewer response, or claiming independence or reproduction. A reviewer reads its "Reviewer response contract" section only to write findings.
- Read [the quantitative review contract](references/quantitative-review.md) before reviewing a statistical, mathematical-proof, counterexample, numerical-convergence, dimensional, or uncertainty artifact.

If a checklist materially controls a review receipt, include its SHA-256 in the run's `reference-use-ledger`. A reference defines review procedure; it does not prove the reviewed conclusion true.

## Inputs and review mode

Review packets include `review_priority` and an advisory `review_order_policy` with `suggested_first_claim_ids`.
The ordering tier affects review order only; full coverage of material claims remains mandatory.
Choose an explicit tier with the reviewer CLI's `--tier` option when a caller-selected ordering is needed.

Require the decision contract, approved plan, artifact manifest, claim register, query and execution logs, outputs, environment, lane receipts, cited sources, and prior findings. Report missing evidence rather than filling gaps from memory.

Declare one review mode:

- `record`: audit internal consistency and evidence fidelity without rerunning.
- `reproduction`: independently rerun specified material computations from recorded inputs.
- `method`: assess whether design, controls, metrics, assumptions, and inference support the claim.
- `source`: verify retrieval, source identity, citation attribution, study dependence, and evidence cutoff.

A review may combine modes, but never imply a computation was reproduced when only its record was inspected.

## Review workflow

1. Run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/validate_artifact.py" <manifest> --review-output <run-dir>/deterministic-review.json --require-passed-review` for deterministic artifact-byte, sidecar-schema, and record/source checks, writing to a separate, unreviewed path. Never point `--review-output` at the independent review receipt or any reviewed artifact. Do not use this flag for the producer's first diagnostic pass when unresolved findings are expected.
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
12. Batch every finding from one review round into a single correction pass. Scope the re-review to the original findings, the changed claims/artifacts and their direct dependents; do a full re-review only when a correction changes a central conclusion, the included evidence set, or the method. Minor findings that cannot change the decision may stay open and be disclosed per the pass rule; never start a new correction/re-review round only to fix minor findings. Preserve the original finding, resolution evidence, and residual risk; a finding is resolved only when the changed claim or new evidence passes the same check.

## Completion gate

Run this once the deliverable and sidecars are final. Literature runs (`$cx-literature-review`) use `prepare-review`, which runs the refresh, citation trace, claim-sufficiency check, output refresh, and deterministic review (writing `deterministic-review.json`) and builds `review-task.json`; do not run those checks separately. Resolve every listed finding in one batch and rerun once.

```
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/package_run.py" prepare-review --run-dir <run-dir> --tier <tier>
# read independent-review-runtime.md (independence, transport), then spawn the independent reviewer on <run-dir>/review-task.json; it runs `science_reviewer.py respond` (writes reviewer-response.json)
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_reviewer.py" finalize <run-dir>/review-task.json <run-dir>/reviewer-response.json --output <run-dir>/review-receipt-v2.json
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/science_checkpoint.py" review <run-dir> --artifact-ref review-receipt-v2.json
```

Other standard/full runs replace the first line with these checks, in order: `trace_citations.py --run-dir <run-dir> --require-traced` and `check_claim_sufficiency.py --run-dir <run-dir> --tier <tier>` (run both whenever the run uses `$cx-literature-review` or carries a `study-table` sidecar; skip them only when neither holds), `validate_artifact.py <manifest> --review-output <run-dir>/deterministic-review.json` (a separate, unreviewed output path; never point `--review-output` at the independent review receipt or any reviewed artifact), then `science_reviewer.py prepare <manifest> --mode <record|source|method|reproduction> [--mode ...] --tier <tier> --output <run-dir>/review-task.json`. Resolve every deterministic finding before preparing the packet; an unresolved finding fails the final `--require-passed-review` gate and forces a new review round.

After the receipt passes (no open critical/major finding), do not modify reviewed artifacts: any change invalidates the review. Run `validate_artifact.py <manifest> --review-output <run-dir>/deterministic-review.json --require-passed-review`, then `science_checkpoint.py complete`, then deliver. `science_checkpoint.py review` registers the receipt in the manifest; if it reports `verdict_recorded: false`, run `package_run.py refresh --run-dir <run-dir> --register-receipt <receipt>`.

## Seeded-defect and benchmark review

For literature reviews, verify that duplicate persistent IDs, citation relationships not declared by the study table, supported claims without required evidence, shared cohorts presented as replication, and failed queries used as support are detected. Use the checked-in literature fixture and its living-review diff as a minimum contract.

For structure-based drug discovery, run `"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/audit_sbdd_benchmark.py" <benchmark.json>`. Treat held-out bound-pose pocket information, analog-series or scaffold leakage, cold-target violations, known training overlap, missing subgroup analysis, and affinity or mechanism claims without assay-aware validation as blocking findings. A clean process exit or favorable docking score is not a scientific pass.

For quantitative research, use [the quantitative review contract](references/quantitative-review.md). Treat pseudoreplication, outcome-dependent design, uncontrolled stopping or multiplicity, causal-identification gaps, computation presented as proof, unresolved proof obligations, admitted formal proofs, nonmonotone convergence, failed residual or invariant thresholds, dimensional mismatch, and invalid covariance as blocking according to severity. Run the deterministic quantitative acceptance fixture as the minimum software contract.

For model-backed runs, resolve the model in `<plugin-root>/models/registry.json` and verify the `model-receipt` fingerprint. A model contract, code, weight, database, configuration, or input change invalidates a prior acceptance or review receipt.

## Finding severity

Use [references/review-checklist.md](references/review-checklist.md). `critical` changes trust in the run or exposes fabrication, leakage, contradiction, invalid proof, or invalid causal/statistical independence; `major` can change a material conclusion; `minor` affects clarity or reproducibility without changing the central result. Mark non-blocking suggestions separately.

## Receipt and independence

Save the final machine-readable receipt under the run directory with `status`, `reviewer`, `independent`, `review_modes`, `reviewed_claims`, `findings`, `limitations`, and referenced artifact hashes. Set `independent: true` only for a genuinely separate reviewer.

Use a separate subagent when available. Give it the decision contract, raw run artifacts, and approved plan without the intended answer or suspected bug. Put the whole review task (the `review-task.json` path and the response command) in the spawn message, then wait for the final answer with `wait_agent`; do not `send_message` a running reviewer or message it after completion, and use `followup_task` only to start a new round with a refreshed `review-task.json`. A parent message sent mid-review can leak the intended answer into the review, and a message can abort a pending reviewer tool call. If no separate agent is available, state that the work was a second pass rather than an independent review.

After every blocking finding is resolved and `status` is `passed`, let the coordinator attach the receipt with `science_checkpoint.py review --artifact-ref <path>`; do not self-attest independence. The checkpoint validates and hashes the receipt's statement but cannot authenticate reviewer identity.

## Boundary

A record review does not rerun analyses, and deterministic validation cannot judge domain validity by itself. Reviewer success reduces inconsistencies and unsupported claims; it does not establish mathematical truth, scientific truth, clinical validity, safety, or regulatory compliance.
