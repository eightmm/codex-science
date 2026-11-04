---
name: workflow-dissolution-profile-f2
description: "Check supplied synthetic percent-dissolved profiles with frozen shared times, unit counts, CV limits and mean-based f1/f2 factors. Use for offline arithmetic; exclude bioequivalence, product quality and acceptance decisions."
license: MIT
---

# Dissolution Profile f1 and f2

Role: conductor with an offline reference analyzer. All checked-in tables, questions and expected artifacts are synthetic fixtures. Only already-measured percent-dissolved profiles are accepted; this pack performs no experiment and establishes no physical or clinical validity.

## Decision contract

Before opening percentages, freeze reference and test product identities, units per product, shared times, selected times excluding zero, minimum selected points, CV limits, the one-point rule after 85 percent for either product, mean-based arithmetic and the threshold 50 as arithmetic only. Hash the rule bytes before admitting the tables. At least 12 units per product and at least three selected times are necessary for an available f2; a declared smaller count forces unavailable. Fewer units than the frozen count is a refusal. Fix the system, evidence cutoff, descriptive claim IDs, baseline, exclusions, uncertainty, falsifier and missingness; hashes identify declarations but cannot prove historical freeze timing.

The deliverable is f1/f2 recomputed from product means with preserved CV controls, selection and limitations. The synthetic acceptance case has reference means 20, 40, 60, 90; test means 22, 42, 62, 92; f1 = 80/21 and f2 = 50 log10(100/sqrt(5)). These values are software acceptance criteria, never evidence of bioequivalence, interchangeability, product quality, regulatory acceptance or clinical relevance. Uncertainty about representativeness, measurements and sampling remains unresolved; sensitivity to time selection needs an exploratory revision and method review.

## Reference usage

Read [the reference index](references/index.json) and [stages and record shapes](references/stages.md) before freezing rules, admitting tables, computing factors or handing off claims. Reuse [the ordered plan](references/plan.json) using the existing manifest step shape. Record controlling reference identities in the existing reference-use-ledger through $science-provenance. Procedure documents are not scientific evidence.

## Workflow

1. **01-rule-freeze.** Use $cx-statistical-decision-analysis for the decision and uncertainty framing; preserve the original dissolution-rules-v1 path and hash before percentages are opened. Freeze units, times, minimum points, first CV at most 20 percent and later CVs at most 10 percent, cutoff 85, one late point, mean rule and arithmetic threshold 50. Interpretation-changing revisions require a human decision; changed selections must retain an exploratory label and original rules.
2. **02-table-qc.** Admit dissolution-profiles-v1 by path and hash. Require unique unit IDs within each product, aligned times, finite percentages in 0..100 and enough frozen units. Compute product means and sample CVs. Refuse undefined relative CVs and malformed inputs; never silently repair, omit failed controls or convert missing records to zeros.
3. **03-factors.** Run scripts/validate_dissolution_profile_f2_pack.py against the synthetic fixture first. Compute f1 and f2 from per-time-point product means using the frozen selection. Refuse selecting time zero, multiple late points and unit-pair arithmetic as described in the reference. A CV failure retains numeric f2 with variability-too-high status and no threshold comparison or similarity wording. Too few units or times makes f2 unavailable. An empty selection makes both factors unavailable.
4. **04-summary.** Retain unit counts, selected times, means, all CV controls, late-point count and failed-control count in dissolution-report-v1. Report assumptions, dependencies, conflicts, exclusions, negative results, rejected alternatives, sensitivity needs and the smallest falsifiable next measurement. No missing evidence becomes negative evidence.
5. **05-handoff.** Register ordinary domain artifacts through $science-provenance and separate entries in the existing claim register. Send frozen identities, tables, failed revisions, results, environment/code revision, reference ledger and bounded claims to $science-review for record, source and method review. The coordinator owns rigor classification and independent receipts; this pack always leaves review unavailable.

Use one coordinator checkpoint per run and these ordered stage IDs. No new execution engine is added. Retry only after a specific input defect is corrected; preserve the failed revision. Choose reversible presentation details internally.

## Outputs

Pack-local schemas are dissolution-pack-v1, dissolution-rules-v1, dissolution-profiles-v1, dissolution-report-v1, dissolution-evidence-v1 and dissolution-result-v1. The stages reference defines exact shapes, bounds and formulas. Existing manifest, receipt, sidecar and MCP contracts remain unchanged.

Return immutable input identities, normalized assumptions, f1/f2 or unavailable, CV flags and selection, denominators, dependencies, conflicts, rejected choices, uncertainty, applicability and limitations. The coordinator separately records supported, contradicted, inconclusive and unavailable interpretations. Synthetic acceptance inputs and negative cases live in examples/workflow-dissolution-profile-f2/; frozen questions and CPU budgets live in benchmarks/workflow-dissolution-profile-f2/tasks.json. L4 denotes exercised offline fixtures in tests/test_workflow_diss_pack.py, never scientific acceptance.

## Boundaries

Refuse claims of bioequivalence, interchangeability, product quality, regulatory acceptance or clinical relevance, irrespective of the claim kind. The stages reference states the conservative, incomplete English wording gate. Association is never causality; computed agreement is never physical or clinical validity; review approval is never truth. Positive claims cannot cite computed or review-approval records. Any unavailable evidence requires unavailable claims, as does empty evidence. A single synthetic fixture cannot establish replication. External, independent and preregistered labels cannot alias supplied artifacts by path or hash.

This route is local CPU, standard library and offline synthetic fixtures only. No installation, network, download, GPU, remote or heavy compute is performed. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Failed controls and negative results stay preserved. Stop for essential missing input; absence remains unavailable.
