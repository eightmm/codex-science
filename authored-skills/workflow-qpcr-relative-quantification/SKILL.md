---
name: workflow-qpcr-relative-quantification
description: "Check already-measured real-time PCR Cq tables with dilution-derived amplification efficiencies, frozen reference genes, censored nondetections, replicate controls and biological-unit fold-change intervals. Use for offline synthetic arithmetic checks; never infer gene regulation or clinical relevance."
license: MIT
---

# Relative quantification of real-time PCR Cq

This conductor checks synthetic fixtures of already-measured Cq values. It does
not acquire measurements or establish biological validity.

## Decision contract

Freeze the two conditions, calibrator, sample sheet, biological and technical
replicate identities, target genes, one fixed reference gene, dilution series,
efficiency range, NTC threshold, technical spread, detection cutoff and 95 percent
biological-unit Welch interval before reading the Cq table. Hash the protocol
bytes first. The question is whether the supplied arithmetic and controls agree
with that frozen contract. A failed control falsifies admission. No biological,
mechanistic, biomarker, target-validity or clinical decision is supported.

Use one fixed single reference; this pack does not implement geNorm selection.
Changing it requires an exploratory label and a separately frozen revision.
Record the organism, system, measurement date and evidence cutoff in the
coordinator's existing research contract; the supplied example is synthetic.
Stop for an interpretation-changing ambiguity. Safe defaults do not replace a
missing sample identity, dilution series or control.

## Reference usage

Read [references/index.json](references/index.json), then [references/stages.md](references/stages.md) before rule freeze,
table admission, arithmetic, summary or claim authoring. Read
[references/plan.json](references/plan.json) before creating the coordinator plan. Record materially
controlling reference paths and SHA-256 identities in a reference-use-ledger.
References constrain procedure; they supply no scientific evidence.

## Workflow

1. **01-freeze:** hash `qpcr-protocol-v1`, including the sample sheet and all
   thresholds, before reading Cq values. Copy the existing five-step plan shape
   into one coordinator checkpoint; never mark declaration as execution proof.
2. **02-qc:** admit canonical path-plus-hash table identities, unique planned
   wells, finite Cq or explicit `undetermined`, clean per-assay NTCs and bounded
   technical spread. Recompute dilution efficiencies and report R-squared.
   Preserve censored values and failed controls. Refuse silent repair.
3. **03-quantification:** call the stdlib-only reference on the smallest
   synthetic fixture first. Compute efficiency-corrected sample quantities
   against the calibrator using the frozen reference. Count biological units;
   technical replicate wells never increase n. With fewer than three detected
   units in either condition, the interval is `unavailable`.
4. **04-summary:** compare the entire `qpcr-report-v1` summary, including sample
   quantities, detected and censored n, fold changes and intervals. Record null,
   negative and censored outcomes; do not filter an unfavorable contrast.
5. **05-handoff:** run the read-only CLI described in the stages reference.
   Register protocol, table, report, evidence and result as ordinary artifacts
   using `$science-provenance`, with separate claim-register entries. Transfer
   immutable path-plus-hash identities, controls, negatives and limitations to
   `$science-review`; the coordinator owns rigor and independent review.

There is no network, installation, GPU, remote execution or automatic retry.
Correct an identified source error in a new bundle and rerun once; preserve the
refused bundle. Cancellation or concurrent calls leave inputs unchanged.

## Outputs

The local schemas and complete fields are in `references/stages.md` and listed
in `quality.json`. Return normalized frozen assumptions, `qpcr-result-v1`, the
complete summary and input hashes, claim IDs and statuses, evidence dependencies,
conflicts, exclusions, unavailable evidence, uncertainty and limitations.
The result has status `arithmetic-only` and review `unavailable`.
The example includes expected results, a small-n case and named negative cases.
Their acceptance criteria establish software behavior only.

The smallest falsifiable next action is an independent check of the frozen
sample identities, dilution calculations and hand-derived synthetic contrast.
Rejected alternatives include assuming perfect efficiency, imputing a late Cq,
changing the reference after outcomes, and counting wells as biological units.

## Boundaries

The validator refuses failed controls, missing intervals, unlabelled reference
changes, unsupported claims and unavailable evidence promoted to a result.
Association is never causality; numerical agreement is never physical or clinical
validity; reviewer approval is never truth. Missing evidence remains
`unavailable`, never negative evidence. Failed controls and negative results stay
in the immutable handoff.

Every material conclusion requires `$science-review`. The producer cannot mark
its output independently reviewed. English lexical claim checks are conservative
and incomplete; review must inspect paraphrases too. Stop before installation,
restricted transfer, a new host, GPU, remote or heavy compute, or a material
interpretation-changing choice. This offline pack performs none of those actions.
