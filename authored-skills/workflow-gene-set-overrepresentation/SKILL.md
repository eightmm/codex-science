---
name: workflow-gene-set-overrepresentation
description: "Test a frozen gene list against a versioned local gene-set collection using the tested-gene universe, exact upper tails, BH correction and overlap grouping. Use for gene-set over-representation; exclude pathway activation and phenotype mechanisms."
license: MIT
---

# Gene-set Over-representation

Role: conductor with a small offline reference analyzer. Every checked-in input and expected artifact is a redistributable synthetic fixture. Output states statistical over-representation only.

## Decision contract

Freeze the organism, identifier namespace, upstream tested genes, list-selection rule and selected flags before the set collection is opened. Fix separate directional lists when direction matters, minimum and maximum set size after intersection with the tested universe, BH FDR alpha, collection version and hash, and redundancy Jaccard limit. Hash the complete rule record before reading collection bytes. Assign claim IDs, the intended deliverable, population/system and evidence cutoff in the coordinator contract; retain assumptions, rejected alternatives, uncertainty and falsifiers.

The universe is exactly the genes tested upstream, never a whole genome or the union of the collection. The selected list must match the frozen upstream selected flags. A list selected after inspecting set results requires an explicit exploratory label. Hashes bind the declared inputs; they cannot independently establish historical freezing, collection completeness or biological fitness. Stop for an essential missing input or an interpretation-changing ambiguity. Choose reversible presentation details internally.

Acceptance means the hand-calculated synthetic upper tails, complete-family BH decisions, one redundant finding and all seeded refusals pass. It does not establish biological, physical or clinical validity, power or a phenotype mechanism. The smallest next observation is an independently generated gene list with the same tested-universe and selection rules, followed by source and method review.

## Reference usage

Read [the index](references/index.json), then [stages and record shapes](references/stages.md) before freezing, admitting identifiers, computing, validating or handing off findings. Reuse [the plan](references/plan.json) with the existing manifest step shape. Record controlling reference paths and hashes in the existing `reference-use-ledger`. References guide procedure and are never independent evidence.

## Workflow

1. **01-freeze.** Record `gso-rules-v1` and freeze its bytes and SHA-256 before the collection is read. Reuse `$cx-statistical-decision-analysis` for threshold and uncertainty framing and `$cx-public-omics-dataset-discovery` for upstream provenance. Upstream selected flags define the list independently of the collection. Never silently change a rule to obtain a hit; retain the previous revision and label post-selection exploratory.
2. **02-identity.** Admit hash-bound upstream tested rows, the selected gene list and the versioned collection. Require unique identifiers in the frozen namespace and organism. Require universe equality with upstream tested genes and list membership inside that universe. Separate up/down lists when frozen as directional; mixed or duplicated identifiers are refusals. Missing essential input is unavailable, never negative evidence.
3. **03-testing.** Run the tiny synthetic fixture first with `scripts/validate_gene_set_overrepresentation_pack.py`. Intersect every set with the universe and report all sets. Sets outside inclusive size bounds are untested, never non-significant. For every admitted set use the exact integer one-sided hypergeometric upper tail, then BH across all tested set/list pairs together. Preserve empty overlaps, negative results, failed controls and untested rows. Never substitute raw p for FDR significance.
4. **04-redundancy.** Report pairwise Jaccard between all significant intersected sets. An edge requires overlap strictly greater than the frozen limit. Report each connected component once as one finding, including transitive links and links between directional results. Dependent sets are never independent confirmations.
5. **05-handoff.** Register domain records as ordinary artifacts with `$science-provenance` and separate entries in the existing claim register. Include complete inputs, hashes, computation, failed controls, negative results, untested sets, dependencies, conflicts, limitations and the smallest falsifiable next observation. Hand these to `$science-review` in record, source and method modes. The coordinator owns rigor classification and independent receipt registration. This pack leaves review unavailable.

Use one coordinator checkpoint per run with these ordered stage IDs. The pack adds no execution engine, manifest or checkpoint writer. Correct the specific input defect before retrying, keep failed revisions and never weaken a frozen threshold. A second producer pass is not independent review.

## Outputs

Pack-local schemas: `gso-pack-v1`, `gso-rules-v1`, `gso-upstream-v1`, `gso-list-v1`, `gso-collection-v1`, `gso-report-v1`, `gso-evidence-v1`, `gso-result-v1`, `gso-negative-fixtures-v1`. Exact shapes and limits are in the stages reference. They add no fields to existing manifests, receipts or claim registers.

Return normalized assumptions, immutable path-plus-hash identities, tested and selected denominators, set sizes and overlaps, raw p and BH q, untested/non-significant/significant states, pairwise Jaccard and grouped findings, exploratory status, claim IDs and review unavailable. The coordinator separately records supported, contradicted, inconclusive and unavailable interpretations with uncertainty, applicability, rejected alternatives and inclusion/exclusion rationale.

Synthetic inputs, expected artifacts and negative fixtures live in `examples/workflow-gene-set-overrepresentation/`; frozen questions and CPU budgets live in `benchmarks/workflow-gene-set-overrepresentation/tasks.json`. L4 is offline synthetic software acceptance through `tests/test_workflow_enrichment_pack.py`.

## Boundaries

Refuse activation, regulation, driving, causality, therapeutic benefit, clinical action, efficacy and pathway mechanism claims. Claim kind labels never bypass evidence or wording checks. Association is never causality; numerical agreement is never physical or clinical validity; absence is unavailable; review approval is never truth. Preserve failed controls and negative results. The conservative English lexical check, including its incompleteness, appears in the stages reference.

Every positive claim status checks both evidence kind and result for review approval or computed agreement. Unavailable evidence forces unavailable claims, even mixed with observed evidence. Empty support requires unavailable; unavailable text cannot assert positive evidence. This single synthetic study cannot establish replication. External, independent and preregistered declarations cannot alias this study's inputs or outputs by path or hash, and do not themselves prove independence.

Local CPU, offline fixtures and standard-library computation only: no network, download, installation, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Do not add a gate at each admitted local stage. Independent review remains mandatory for a material conclusion and never establishes scientific truth.
