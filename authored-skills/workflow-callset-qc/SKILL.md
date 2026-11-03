---
name: workflow-callset-qc
description: "Check cohort quality in an already-called synthetic small-variant genotype table using frozen filters, controls-only exact Hardy-Weinberg tests, trio consistency and X heterozygosity. Use for offline arithmetic checks of tab-free JSON fixtures; never for VCF parsing or variant interpretation."
license: MIT
---

# Synthetic Callset QC

This conductor checks cohort-level arithmetic for already-called synthetic biallelic SNPs. It adds no execution engine and never interprets individual variants.

## Decision contract

Record the exact question, synthetic cohort, genome build label, input paths and SHA-256 values, sample sheet, declared controls, sex and family declarations, and trio membership. Freeze site quality, depth, missingness and controls-only Hardy-Weinberg thresholds; sample call-rate and heterozygosity limits; Ti/Tv expected range; heterozygote allele balance; ambiguous-strand handling; multiallelic refusal; and the X heterozygosity check before opening genotypes.

The baseline is the hand-counted synthetic fixture. Acceptance means matching its arithmetic and preserving every removal reason and failed control. A mismatch falsifies the arithmetic deliverable. No physical, biological, clinical, diagnostic or causal validity follows. Historical freezing, source authenticity and sex identity cannot be established by declared timestamps or hashes.

## Reference usage

Read [references/index.json](references/index.json), then [references/stages.md](references/stages.md) before freezing rules, reading tables, running the validator, registering artifacts or drafting claims. Read [references/plan.json](references/plan.json) before initializing the coordinator-owned checkpoint. Record the selected reference path and hash in the ordinary reference-use ledger; procedural references are not evidence.

## Workflow

1. **01-freeze:** preserve and hash original rules before genotypes. Record the approved decision contract and one coordinator-owned checkpoint for the run. The five manifest steps use the existing id, description and status shape from `references/plan.json`. A changed rule needs preserved original rules and an explicit exploratory label.
2. **02-table-qc:** admit exact, immutable path-plus-hash identities. Refuse duplicate or unsorted sites, duplicate samples, invalid alleles, undeclared ploidy, invalid genotype vocabulary, negative or non-finite numbers, and unspecified strand handling. Missing genotypes remain unavailable.
3. **03-metrics:** run the stdlib reference on the smallest synthetic fixture first. Compute sample call rate, heterozygosity and Ti/Tv, site missingness, exact Hardy-Weinberg enumeration in declared controls on autosomes, every autosomal trio error, and the declared X check. Apply only frozen filters in one pass, without recomputing thresholds after exclusions. Preserve failed and unavailable controls even at removed sites or samples.
4. **04-summary:** compare the submitted report with independent recomputation; retain each removed site and sample with all named reasons. Report negative, null, conflicting and unavailable observations separately. Save the unreviewed result and explicit uncertainty and limitations; never silently repair input or retry with relaxed rules.
5. **05-handoff:** register all domain records as ordinary artifacts with `$science-provenance`, with separate claim-register entries, dependencies, contradictions, inclusion and exclusion rationale, and a smallest falsifiable next check. Complete the matching manifest and checkpoint steps. The coordinator selects rigor and invokes `$science-review`; this pack never marks itself reviewed.

## Outputs

Use the pack-local schemas named in `quality.json`: `callset-qc-pack-v1`, `callset-qc-rules-v1`, `callset-qc-table-v1`, `callset-qc-report-v1`, `callset-qc-evidence-v1`, `callset-qc-result-v1`. Their exact fields, limits and failure handling are in `references/stages.md`.

Return normalized inputs and assumptions, path-plus-hash handoffs, all per-site and per-sample metrics, exclusions with reasons, trio and X discrepancies, failed controls, unavailable denominators, bounded claims, dependency and contradiction records, applicability, rejected alternatives and uncertainty. The checked-in files in `examples/workflow-callset-qc/` are synthetic fixtures, never a reviewed cohort result.

## Boundaries

Refuse pathogenicity, causal variant, disease association, diagnosis and clinical actionability claims. Association is never causality; numerical agreement is never physical or clinical validity; review approval is never truth. Absence of a record is unavailable, never negative evidence. The conservative English wording gate is incomplete and can refuse negations; exact families are in the stages reference and quality declaration.

Stop for missing essential rules or identities, malformed data, report disagreements or an interpretation-changing choice. Retain original files and the named refusal; correct the source or declare a new exploratory revision, never weaken a check to pass. Bounded retries mean one rerun after a documented input correction. No network, downloads, installation, GPU, remote or heavy compute is part of this CPU-only offline pack. Only the coordinator can approve installation, restricted transfers, new hosts, expensive compute or an interpretation-changing choice. Ordinary read-only stages need no new gate.
