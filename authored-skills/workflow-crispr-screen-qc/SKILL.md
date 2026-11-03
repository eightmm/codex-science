---
name: workflow-crispr-screen-qc
description: "Check guide counts from an already-sequenced pooled CRISPR knockout screen against a frozen guide library, matched replicates and non-targeting controls. Use for synthetic count-table QC, guide log2 changes and gene summaries; exclude essentiality, drug targets and biological conclusions."
license: MIT
---

# Pooled CRISPR Screen QC

Role: conductor with an offline arithmetic reference. Every checked-in input and expected artifact is a redistributable synthetic fixture. No wet-lab work, sequencing, network access or execution engine is added.

## Decision contract

Before reading counts, record the question, system, evidence cutoff, intended arithmetic deliverable, claim IDs, permitted descriptive inference, guide-to-gene library identity and non-targeting guides, sample identities, two conditions, matched replicate IDs and ordered timepoints. Freeze and hash the library, design and complete rules: minimum total reads, minimum detection fraction, one normalization choice, positive pseudocount, median guide log2 aggregation, minimum guides, minimum controls and replicates, concordance threshold, absolute fold-change threshold, alpha, full-family Benjamini-Hochberg correction, permutation seed and draw count.

Baseline: the frozen non-targeting guide null. Acceptance: the synthetic fixture's hand-derived read totals, Gini skew, normalized fold changes, perfect replicate concordance, empirical p-value and BH q-value; the one-guide gene remains unavailable. A falsifier is a mismatch with these arithmetic quantities or acceptance of any seeded defect. These checks do not justify power, guide specificity, library representation in a real screen or biological interpretation. Missing essential identities stop admission. Only interpretation-changing choices require a human decision; choose reversible display details internally.

## Reference usage

Read [the index](references/index.json), [stages and exact local shapes](references/stages.md) before freezing, admitting counts, computing, validating or handing off. Reuse [the plan](references/plan.json), which uses existing manifest `id`, `description`, `status` steps. Record controlling reference paths and hashes in the existing `reference-use-ledger`. References control procedure and are not independent evidence.

## Workflow

1. **01-freeze — fix rules before outcomes.** Use `$cx-statistical-decision-analysis` for decision framing. Preserve frozen rule bytes and SHA-256, library and sample design hashes before counts are opened. Choose total-count or median-of-ratios normalization once. Preserve all later revisions; a changed rule requires an exploratory label. This reference supports only median-guide-log2 aggregation; a different method needs a separately reviewed implementation.
2. **02-count-qc — preserve guide identity.** Admit synthetic non-negative integer counts with unique guide IDs all present in the frozen library and columns exactly matching the design. Report library coverage, per-sample detection, zero fraction, read totals and Gini-style skew. Require the frozen number of non-targeting guides, detected in every sample. Preserve failed QC and negative results; absent guides never become negative evidence.
3. **03-guide-changes — test replicate concordance.** Normalize with the chosen frozen rule, add the frozen pseudocount and compute selected/baseline guide log2 changes for each matched replicate. Center on the per-replicate median non-targeting change. Compute Pearson concordance for every pair of replicate change vectors within the condition contrast. A failed sample or a correlation below the frozen threshold makes pooling unavailable. Never silently exclude a replicate to pass. Zero-variance vectors are refused.
4. **04-gene-summary — retain unavailable results.** Aggregate eligible guides by the frozen median rule. Draw control-guide subsets without replacement using the frozen seed and count; use two-sided empirical p-values with the plus-one correction. Apply BH across every observed gene, then the absolute fold-change threshold. Keep genes with too few measured guides, too few controls for their guide count, failed sample QC or failed concordance as `unavailable` with null p, q and significance. They are never negative. Preserve measured nonsignificant results separately. Run `python3 scripts/validate_crispr_screen_pack.py examples/workflow-crispr-screen-qc/pack.json` for the smallest offline smoke check.
5. **05-handoff — independent review.** Register all pack-local records as ordinary artifacts through `$science-provenance`; write separate entries in the existing claim register. Return input paths and hashes, thresholds, QC failures, guide and gene denominators, p and q values, null and unavailable results, assumptions, dependencies, conflicts, limitations, rejected alternatives and the smallest falsifiable next measurement. Hand the complete bundle and reference-use ledger to `$science-review` in record, source and method modes. Rigor classification and independent receipt registration remain with the coordinator. This pack never marks its own output reviewed.

Use one coordinator checkpoint per run and these five ordered IDs. The validator writes nothing and creates no manifest or checkpoint. Correct a specific input defect before retrying, preserve its failed revision, and do not repeatedly relax thresholds. Sensitivity to normalization, pseudocount or guide membership is a separately labeled exploratory revision with its own identities; numerical stability does not establish real-screen validity.

## Outputs

Eight pack-local schemas: `crispr-pack-v1`, `crispr-rules-v1`, `crispr-library-v1`, `crispr-design-v1`, `crispr-counts-v1`, `crispr-report-v1`, `crispr-evidence-v1`, `crispr-result-v1`. Exact shapes and bounds are in the stages reference. These are ordinary artifacts; no existing manifest, receipt, claim-register, global schema or MCP key changes.

Return the normalized assumptions and immutable handoffs, QC and guide changes, gene rows with explicit observed/unavailable status, supported/contradicted/inconclusive/unavailable interpretation IDs in the separate claim register, and review `unavailable`. Examples and expected results: `examples/workflow-crispr-screen-qc/`. Frozen questions and budgets: `benchmarks/workflow-crispr-screen-qc/tasks.json`. L4 means synthetic arithmetic and seeded-refusal acceptance in `tests/test_workflow_crispr_pack.py`, never real biological validation.

## Boundaries

Refuse essentiality, drug-target, therapeutic, causal, mechanism, efficacy, clinical-action and physical-validity claims, including claims mislabeled descriptive. Association is never causality; numerical agreement is never physical or clinical validity; reviewer approval is never truth. Positive claims cannot cite a computed or review-approval record, checking both kind and result. Every claim citing any unavailable source must be unavailable, even with other observed citations. An empty evidence list requires unavailable status; unavailable text cannot assert positive support. Replicated status is refused because this synthetic study cannot establish replication. External, independent and preregistered labels must pass path/hash anti-alias checks against study inputs and outputs.

The stages reference states the conservative, incomplete English lexical gate. Preserve failed controls and negative results. CPU-only offline fixtures use the standard library. No installation, download, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice; never at every admitted offline stage.
