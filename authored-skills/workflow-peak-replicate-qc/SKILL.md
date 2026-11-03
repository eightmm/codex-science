---
name: workflow-peak-replicate-qc
description: "Check supplied genomic enrichment peak intervals, library read counts, FRiP, reciprocal replicate overlap and blacklist exclusions under frozen genome and consensus rules. Use for offline ChIP-seq or accessibility peak QC; no peak calling or biological interpretation."
license: MIT
---

# Replicate Peak QC

Role: conductor with a small offline reference analyzer. All checked-in intervals, counts and expected artifacts are redistributable synthetic fixtures. Arithmetic acceptance cannot establish binding, regulation or function.

## Decision contract

Before reading peaks, record the question, assay, organism/system label, evidence cutoff, claim IDs, genome build, chromosome lengths, replicate identities and availability design, minimum reads per library, minimum fraction of reads in peaks (FRiP), minimum replicate overlap, reciprocal interval match fraction, blacklist path and SHA-256, input-control requirement, consensus support and merge rule. Freeze and hash these rules first. Freeze the uncertainty rule, baseline and falsifier: invalid intervals, failed library controls or insufficient overlap exclude affected replicates, and no retained consensus segment may intersect the blacklist.

This route admits already-called peaks and supplied read counts only. It does not count alignment reads, call peaks, evaluate mapping quality, determine enrichment significance or verify an actual experimental design. Material interpretation choices require coordinator resolution; reversible display preferences do not. Hashes identify the declared freeze but cannot prove that it historically preceded outcomes.

## Reference usage

Read [the index](references/index.json) and [stage and record contracts](references/stages.md) before freezing rules, admitting intervals, computing metrics, validating a bundle or preparing review. Reuse [the plan](references/plan.json), which uses the existing manifest `plan` step shape. Hash materially controlling references in the existing `reference-use-ledger`; references describe procedure and are never independent scientific evidence.

## Workflow

1. **01-rules — freeze.** Use `$cx-statistical-decision-analysis` for decision thresholds and uncertainty framing, then hash the complete rule record and blacklist before peaks are read. Preserve source bytes, code/environment revision, rejected alternatives and failed revisions. Missing essential inputs stop admission. A changed overlap threshold requires an explicit exploratory label; the original rule identity is retained.
2. **02-intervals — admit identities.** Validate path-plus-hash inputs, genome builds, chromosome identities, 0-based half-open coordinates, finite non-negative scores, lexical sorting and non-overlap within each replicate. Count blacklist hits without silently repairing intervals. Record missing data as `unavailable`; an available empty peak set remains distinct. Do not impute zero peaks for an unavailable replicate.
3. **03-qc-consensus — compute controls.** Use `scripts/validate_peak_replicate_qc_pack.py` on the tiny synthetic fixture first. Compute FRiP from supplied original called-peak counts and library totals, exact base-pair Jaccard and directional reciprocal matched-peak fractions. Apply every frozen threshold, flag exclusions and remove entire blacklist-hit peaks. Compute supported consensus segments only from eligible replicates under the frozen merge rule. Failed libraries never silently re-enter consensus.
4. **04-summary — retain denominators.** Return per-replicate QC, pairwise overlap and per-segment support with explicit n, including unavailable, failed and empty states. Compare every supplied report quantity with the reference result. Preserve negative results, failed controls, exclusions, dependencies, conflicts, uncertainty and applicability. Choose the smallest falsifiable next action: inspect a flagged library/control or acquire missing supplied records under a new approved run.
5. **05-handoff — independent review.** Register pack-local domain records as ordinary artifacts with `$science-provenance` and separate entries in the existing claim register. Send the frozen rules, inputs and hashes, complete QC tables, claims, limitations, execution/environment identities and reference-use ledger to `$science-review` in record, source and method modes. Rigor classification, checkpoint ownership and independent review receipts remain coordinator responsibilities. This pack never marks its output reviewed.

Use one coordinator checkpoint per run and the five ordered stage IDs above. The reference adds no execution engine, manifest or checkpoint writer. Correct a specific input defect before retrying and retain each failed revision; do not weaken thresholds to obtain a passing report.

## Outputs

Pack-local schemas: `peak-qc-pack-v1`, `peak-qc-rules-v1`, `peak-qc-blacklist-v1`, `peak-qc-peaks-v1`, `peak-qc-report-v1`, `peak-qc-evidence-v1`, `peak-qc-source-v1`, `peak-qc-result-v1`. Exact shapes and bounds appear in the stages reference. They add no keys to existing manifests, artifacts, claim registers, receipts or MCP contracts.

Return frozen identities, normalized assumptions, n for designed/available/eligible replicates, original and blacklist peak counts, read denominators, FRiP and flags, overlap pairs with n and union/intersection bases, consensus coordinates with replicate identities and support counts, bounded claims and limitations. The coordinator separately preserves supported, contradicted, inconclusive and unavailable interpretations under existing claim semantics. Computed agreement is arithmetic evidence only; it cannot support a positive scientific claim.

Synthetic fixtures, expected artifacts and seeded refusals live in `examples/workflow-peak-replicate-qc/`; frozen questions and CPU budgets live in `benchmarks/workflow-peak-replicate-qc/tasks.json`. L4 means offline acceptance through `tests/test_workflow_peaks_pack.py`, never biological or real-assay validation.

## Boundaries

Refuse binding, enhancer/promoter activity, regulation, causal mechanism, physical validity, therapeutic efficacy, clinical relevance and clinical-action claims, irrespective of the supplied claim kind. Association is never causality, numerical agreement is never physical or clinical validity, and review approval is never truth. The conservative, incomplete English lexical check is specified in the stages reference. Unavailable sources never become negative evidence; a claim citing any unavailable source must remain unavailable. A single synthetic fixture cannot establish replicated evidence.

Inputs are read through pinned directory descriptors with bounded, hash-checked bytes and final ancestor-chain checks. External, independent and preregistered labels cannot substitute for source evidence or alias this study's own artifacts. These checks do not establish actual historical preregistration or experimental independence.

Execution is local CPU-only, offline and standard-library-only: no install, network, download, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfers, a new host, GPU/remote/heavy compute or interpretation-changing choices. An independent producer pass is never an independent review.
