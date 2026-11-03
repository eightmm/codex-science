---
name: workflow-hts-plate-qc
description: "Check supplied plate-well screening signals against frozen control layouts, Z-prime, SSMD, positional drift and replicate-agreed robust-z hit rules. Use for already-read primary-screen plates; excludes raw instrument processing and compound activity or potency conclusions."
license: MIT
---

# Plate Screen Quality Control and Hit Calling

Role: conductor with a small offline reference analyzer. All checked-in inputs are redistributable synthetic software fixtures. A hit states screening signal only and is never an active compound.

## Decision contract

Record the screening question, assay, instrument, system, signal units, evidence cutoff, plate inventory, sample identities, replicate unit, claim IDs, uncertainty and falsifier. Start from already-read signals; this pack does not operate an instrument or infer a compound's biological properties. Use `$science-provenance` for immutable identities. Retain unavailable assay context explicitly.

Before reading any signal table, freeze and hash the complete layout and rules: rows and columns (normally 16×24 for 384 wells), disjoint positive, negative and solvent control sets, edge exclusion or flagging, minimum control and sample counts, Z-prime and absolute SSMD minima, maximum positional drift, robust-z threshold and direction, and replicate agreement requirement. Control wells must span multiple rows and columns. Keep the original freeze if an interpretation-changing rule changes; require an exploratory label. Hashes prove content identity, never historical timing.

The deliverable is an unreviewed screening-signal record. Acceptance uses two 6×6 synthetic plates: P1 passes control separation with planted sample HIT and flagged drift; P2 fails Z-prime and contributes neither hits nor a replicate mean. Edge sample A3 is excluded under the frozen rule. The two passing HIT replicates have mean signal 60. Loss of control separation or replicate agreement falsifies the screening hit; fixture agreement never validates biology. Missing identities stop admission. Missing evidence remains unavailable, never negative evidence.

## Reference usage

Read [the index](references/index.json), then [stages and record shapes](references/stages.md) before freezing, admitting, computing, validating or handing off results. Use [the plan](references/plan.json) with the existing manifest step shape. Record materially controlling reference paths and hashes in the existing `reference-use-ledger`; a procedural reference is not scientific evidence.

## Workflow

1. **01-freeze — layout and rule freeze.** Preserve the original hashed layout before reading signals. Resolve interpretation-changing ambiguity; record safe presentation defaults. A changed threshold or edge rule requires exploratory status and the retained original identity.
2. **02-inventory — table admission.** Check unique plate IDs and unique plate-well IDs, complete grids, all three control sets, instrument and assay identity, observed finite signals and unique sample replicate identities. Missing signals are refused; no zero filling or silent sample deletion. Retain the raw synthetic fixture or real input unchanged.
3. **03-qc — per-plate control separation.** Calculate sample-SD Z-prime, signed SSMD, signal/background, and row/column negative-control median drift. Flag drift strictly above the frozen limit. Below-minimum Z-prime or absolute SSMD, zero variance, equal control means, zero background, insufficient samples or zero MAD produce a failed plate with reasons and retained measurements. A failed plate contributes no hits and no replicate mean. Drift alone is flagged, not automatically failed; its interpretation requires independent review.
4. **04-hits — within-plate robust scores.** Calculate median and MAD from all sample wells on the same plate, before edge exclusion; scale MAD by 1.4826. Apply the frozen directional threshold inclusively. Exclude or flag edges exactly as frozen. Controls never become hits. Require the frozen count of distinct, agreeing sample replicate IDs from passing plates; preserve disagreements and every failed plate in the input handoff. Average only the agreeing hit signals, recording each contributor. This is within-screen agreement, not independent study replication.
5. **05-handoff — bounded claims.** Register domain records as ordinary artifacts with immutable path-plus-hash identities through `$science-provenance`. Keep separate entries in the existing claim register. Provide the decision contract, complete input inventory, control failures, positional flags, all exclusions, robust scores, replicate contributors, negative results, assumptions, dependencies, conflicts, uncertainty, rejected alternatives and smallest falsifiable follow-up measurement to `$science-review` in record, source and method modes. The coordinator owns rigor classification, independent review and receipt registration.

Use one coordinator checkpoint per run with these five ordered stage IDs. The validator adds no checkpoint, manifest, review receipt or execution engine. Correct an identified defect before a bounded retry; preserve the failed evidence and original freeze. Do not relax a control to obtain hits. Real studies require assay-specific control placement, replicate independence and follow-up measurement review.

## Outputs

Pack-local schemas are `hts-pack-v1`, `hts-layout-v1`, `hts-signals-v1`, `hts-evidence-v1` and `hts-result-v1`; exact fields and public Python and CLI signatures are in the stages reference. They extend no existing manifest, claim-register or receipt. The CLI prints JSON and writes nothing.

Return frozen identities, complete plate QC and reasons, drift flags, all admitted raw signals by immutable reference, sample median/MAD, replicate-agreed hits with edge flags, contributor identities and mean signals, claims, limitations, `evidence_level: screening-signal-only` and `review: unavailable`. The coordinator separately records supported, contradicted, inconclusive and unavailable conclusions with existing claim semantics. Empty support requires unavailable status; any unavailable citation requires unavailable status even when mixed with observed evidence.

The synthetic fixture is `examples/workflow-hts-plate-qc/pack.json`; hand-checked `expected.json`, all negative recipes and input-hardening cases are exercised by `tests/test_workflow_hts_pack.py`. Frozen questions, acceptance criteria and CPU budgets are in `benchmarks/workflow-hts-plate-qc/tasks.json`. L4 means synthetic software acceptance under unittest discovery, never a validated real screen or biological result.

## Boundaries

Refuse causal, mechanistic, therapeutic, clinical-action, efficacy, activity, potency, binding, affinity or inhibition claims for a screening hit, regardless of the claim's kind label. Numerical agreement never proves physical or clinical validity; review approval never proves truth. Check evidence kind and result, not labels alone. External, independent or preregistered labels must not alias this study's own input or output path or hash. One synthetic study cannot establish replicated status. The conservative English wording filter is incomplete and specified in the stages reference; independent review must assess meaning and unlisted paraphrases.

Refuse hits from failed plates, control wells, excluded edges or insufficient agreeing replicates, averages that include failed plates, unflagged positional drift, zero-variance controls reported passing, duplicated identities, missing solvent controls, zero-filled missing signals, and unlabelled post-outcome rule changes. Preserve failed controls, null and negative results. Do not interpret missing evidence as an absent effect.

This route is CPU-only, offline and standard-library-only. No network, installation, downloads, GPU or remote execution is authorized. Human decision gates apply before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices; routine admitted local stages need no extra gate. Process success, fixture agreement and reviewer approval cannot establish biological truth.
