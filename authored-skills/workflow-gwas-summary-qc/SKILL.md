---
name: workflow-gwas-summary-qc
description: "Check supplied GWAS per-variant beta, standard error, p, sample size and alleles against frozen genome-build and quality rules; summarize positional loci without genotypes or an LD reference. Use for genomic inflation and lead-variant QC, never causal genes or medical decisions."
license: MIT
---

# GWAS Summary QC

Role: conductor with an offline reference analyzer. All checked-in data are redistributable synthetic fixtures. Outputs state statistical association evidence only.

## Decision contract

Freeze genome build, trait, ancestry label, effect-allele convention, genome-wide p threshold, genomic-inflation limit, minimum sample size, locus window in base pairs, minimum allele frequency and relative normal-tail tolerance before reading the table. Record question, population, evidence cutoff, claim IDs, uncertainty rule and falsifier. Hash original protocol bytes before table admission; retain prior revisions. This reference accepts already-computed effects for biallelic SNVs; no genotypes, LD reference, gene mapping or strand inference.

Acceptance requires the planted synthetic signal, hand-derived normal tails and lambda_GC, preserved inconsistent/ambiguous exclusions, and every seeded refusal. Numerical agreement establishes software behavior only. A material ambiguity about trait, build, ancestry or orientation stops interpretation. Reversible display choices need no further gate. Hash-bound declarations cannot prove historical freeze timing or real independence. Real applications need source/design review and sensitivity to ancestry, population structure, variant selection and threshold choice; the small fixture is no power justification.

## Reference usage

Read [the index](references/index.json) and [stage contracts](references/stages.md) before freeze, admission, computation, validation or handoff. Reuse [the plan](references/plan.json), whose steps use existing manifest id/description/status fields. Record controlling references and SHA-256 values in the existing reference-use-ledger. References constrain procedure and are never independent scientific evidence.

## Workflow

1. **01-freeze.** Use `$cx-statistical-decision-analysis` for decision framing; freeze and hash the rules before opening the table. Do not rewrite thresholds after observing outcomes. A changed threshold or window requires an explicit exploratory label and preserved original freeze.
2. **02-harmonization.** Admit immutable path-plus-hash inputs. Require unique variant IDs and matching build. Record both original and current alleles, with flips only when declared. Flag A/T and C/G strands; exclude them from frequency-dependent checks, validated counts and signals. Never infer an undeclared flip or silently deduplicate.
3. **03-consistency.** Compare z=beta/se with reported p using the frozen relative tolerance and two-sided normal erfc. List and exclude inconsistent p, nonpositive standard errors, out-of-range p/frequency, low sample size and low frequency. Zero/underflowed p and non-finite arithmetic are refusals; never repair rows. Preserve failed controls, negative results, exclusions and denominators.
4. **04-signals.** Run `scripts/validate_gwas_summary_qc_pack.py` on the synthetic fixture first. Compute median(z squared)/0.4549 over QC-passing rows, then greedy lead variants ordered by p and ID; exclude a candidate within the frozen window of an existing lead on its chromosome. Call these positional signals. Inflation above the frozen limit requires the global flag and every signal marked inflated-risk. Threshold equality passes; window equality excludes the neighboring candidate.
5. **05-handoff.** Register all domain records as ordinary artifacts with `$science-provenance` and separate entries in the existing claim register. Preserve assumptions, dependencies, conflicts, unavailable evidence, rejected alternatives, limitations and the smallest falsifiable next observation. Hand hashes, table identity, exclusion records, frozen rules, complete outputs and environment/execution identities to `$science-review` in record, source and method modes. Rigor classification and independent review remain coordinator-owned; the pack never marks itself reviewed.

Use one coordinator checkpoint per run, with the five ordered IDs above. This pack adds no execution engine or global contract. Correct a specific defect before retrying and retain each failed revision. Missing records are unavailable, never negative evidence.

## Outputs

Pack-local schemas: gwas-summary-qc-pack-v1, gwas-summary-qc-protocol-v1, gwas-summary-qc-table-v1, gwas-summary-qc-report-v1, gwas-summary-qc-evidence-v1 and gwas-summary-qc-result-v1. Exact shapes and limits are in the stage reference. No existing manifest, receipt, claim-register or MCP keys change.

Return frozen assumptions, input identities, validated variant IDs, every excluded row with reasons, strand flags and frequency-check IDs, genomic inflation, positional signals, claims and limitations. The coordinator records supported, contradicted, inconclusive and unavailable interpretations with existing claim semantics. Review stays unavailable. Synthetic inputs, expected artifacts and negative cases live in `examples/workflow-gwas-summary-qc/`; frozen questions and CPU budgets live in `benchmarks/workflow-gwas-summary-qc/tasks.json`. L4 means offline fixture acceptance through `tests/test_workflow_gwas_pack.py`.

## Boundaries

Refuse association stated as causality, a causal gene or variant, mechanism, therapeutic target, efficacy, clinical action or physical validity, even with a descriptive claim label. Positive claims cannot cite review approval or computed/numerical agreement; inspect both record kind and result. Review approval is never truth. An empty evidence list or any unavailable citation requires unavailable status; unavailable claims cannot assert positive evidence. Replicated status is refused for this single synthetic fixture. External, independent and preregistered labels must resolve to hashed sources and cannot alias this study's outputs.

The conservative English wording gate is incomplete and documented in the stages reference. The route uses local CPU and offline fixtures, with no third-party dependency, installation, download, network, GPU, remote or heavy compute. Human gates apply only before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices. Validation writes nothing; concurrent calls create no shared state.
