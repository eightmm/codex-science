---
name: workflow-variant-evidence-dossier
description: "Build an evidence-only public variant dossier through fixed normalization, public-source retrieval, dependency reconciliation, bounded claims and independent review handoff. Use for research dossiers with a declared genome build and allele; never use for patient diagnosis, clinical recommendations or unapproved private-data transfer."
license: MIT
---

# Public Variant Evidence Dossier

Role: conductor. This pack fixes the order and handoffs of existing skills; it adds no execution engine. Its deterministic acceptance example is a synthetic software fixture, never a clinical classification.

## Decision contract

Freeze the research question, organism, genome build, chromosome/position, REF/ALT, strand, transcript, phenotype, population, evidence cutoff and intended audience before retrieval. Assign claim IDs, permitted descriptive or associational inference, inclusion/exclusion rules, dependency groups, denominators with units, positive/negative controls, uncertainty, falsifiers and the smallest decision-changing follow-up before seeing outcomes. Record unknowns; unresolved essential identity blocks allele-level synthesis. Use one existing coordinator checkpoint per run and the five ordered IDs from [the plan](references/plan.json).

## Reference usage

Read [stage contracts](references/stages.md) before normalization, retrieval, reconciliation, claims, validation or handoff. It names every pack-local schema, acceptance rule, failure action and gate. Copy [the plan](references/plan.json) into the existing manifest `plan`; preserve its `{id, description, status}` step shape and record completion through existing coordinator tools. Read `references/index.json` first and record materially controlling reference paths plus SHA-256 in the existing `reference-use-ledger`. References constrain procedure; they are not scientific evidence.

## Workflow

1. **01-normalize.** Use `$cx-variant-evidence-synthesis` and its identity reference to inspect the supplied variant. Freeze `identity-ledger.normalized.json` with normalized build, allele, forward strand and transcript; its `sources` list is empty until retrieval. Do not silently lift over, swap alleles or select a transcript. Request a decision only for an interpretation-changing ambiguity.
2. **02-retrieve.** Load `$cx-clinvar-search`, `$cx-gnomad-search`, `$cx-dbsnp-search`, `$cx-gwas-catalog-search` and `$cx-ensembl-search` for their supported operations. Reuse the existing connector snapshot/replay contract, exact serialized requests, release/access metadata, pagination and failure receipts. Write a new `identity-ledger.json` that binds the frozen normalization input by path/hash and adds original source identities, explicit mappings and snapshot path/hash bindings. Start with one bounded query per source and one positive/negative control pair per run; retry a transient failure once, retaining both outcomes. Use only already-authorized hosts and transfers. The fixture is offline replay only. Connector gene/trait search results alone do not establish allele identity or an association; mark the missing evidence unavailable. Do not invent connector parameters or replace a failed structured route with web search.
3. **03-reconcile.** Use `$cx-variant-evidence-synthesis` to produce `evidence-table.json`. Before ranking locus-to-gene candidates, compose `$cx-locus-to-gene-prioritization`; use `$cx-gene-burden-evidence` only for supplied compatible burden data, and `$cx-phewas-replication-analysis` only for supplied aligned replication data. Those skills retain their schemas and method rules. This pack does not require new retrieval or compute for an unavailable optional lane. Preserve per-source cohort/dependency groups, denominators, units, controls, rejected alternatives, conflicts, negative results and unavailable rows. Shared or unknown groups cannot establish independent replication.
4. **04-bound-claims.** Write `bounded-claims.json` and `dossier.json`, preserving separate supported, contradicted, inconclusive and unavailable claims. Keep statements within the weakest essential evidence link. Run `python3 scripts/validate_variant_dossier.py <dossier-dir> --require-clean` from the repository, optionally using `--output <outside-dossier.json>`. Fix identities or downgrade claims; do not delete failed controls or negative evidence to obtain a pass.
5. **05-review-handoff.** Register domain records, validation output and source snapshots as ordinary artifacts with `$science-provenance`. Write separate entries in the existing `claim-register`; never register the pack records as a new global sidecar kind. Complete matching plan/checkpoint stages through existing tools, with the final stage meaning handoff only. Send the immutable manifest, claims, source dependencies, exact requests, snapshots, controls, exclusions, limits and unanswered questions to `$science-review`. Rigor classification and independent review remain coordinator decisions. The pack always emits `unreviewed`.

## Outputs

- `identity-ledger.normalized.json` and `identity-ledger.json`: `variant-identity-ledger-v1`, frozen canonical identity followed by a hash-linked ledger with source-to-snapshot path/hash and explicit reconciliation.
- `evidence-table.json`: `variant-source-evidence-v1`, one retained row per planned source, status, evidence type, selected record, cohort/dependency groups, denominator/unit, controls, uncertainty, rationale and limits.
- `bounded-claims.json`: `variant-bounded-claims-v1`, stable IDs, kind, basis, status, supporting source rows, exact text, uncertainty, applicability and falsifier.
- `dossier.json`: `variant-dossier-v1`, ordered stages, hash-bound records, mandatory boundaries and `unreviewed` review status.
- Source snapshots in the unchanged connector format, and `variant-dossier-validation-v1` validation output. See `examples/workflow-variant-evidence-dossier/` for clearly labelled synthetic fixtures and negative cases.

Write artifacts incrementally within one run directory. Freeze path/hash handoffs before the next stage consumes them; a later revision needs a new artifact identity and review invalidation. Do not overwrite another run or a reviewed artifact. The validator is read-only; it cannot reserve concurrently changing inputs. Its optional CLI output is atomically replaced, outside the dossier, and grants no review status.

## Boundaries

Evidence only; no diagnosis or clinical recommendation. Association is never causality. Numerical agreement is never physical or clinical validity. Absence of a record is `unavailable`, never negative evidence. Review approval is never truth; failed controls and negative results are preserved. The validator refuses structured violations of these rules rather than emitting an advisory warning.

Stop on build mismatch, unreconciled allele/strand/transcript, stale hashes, missing controls/denominators, unverified identity, restricted transfer, an unapproved host, installation, or remote/GPU/heavy compute. No such external behavior runs in the validator or tests. Stop only affected interpretation when a source is unavailable; preserve its row and continue authorized evidence work. A failed essential control cannot support a positive claim. Keep uncertainty, ancestry, ascertainment, source propagation, release and applicability limits explicit. Independent source/method review must assess prose semantics and source extraction; deterministic success proves declared mechanical consistency only.
