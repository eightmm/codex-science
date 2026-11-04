---
name: workflow-nucleic-acid-quant-purity
description: "Check supplied nucleic-acid absorbance readings with frozen dsDNA/RNA conversion factors, path length, dilution, A320 background, matched blank and purity-ratio bands. Use for synthetic spectrophotometric arithmetic; exclude sample suitability and downstream-use conclusions."
license: MIT
---

# Nucleic Acid Concentration and Purity Ratios

Role: conductor with an offline reference analyzer. All checked-in readings, questions and expected artifacts are synthetic fixtures. This pack checks arithmetic for already-measured readings; it never acquires data or establishes sample quality.

## Decision contract

Before opening readings, freeze the question, descriptive claim IDs, sample/analyte identities, system, evidence cutoff, assumptions, comparison baseline, uncertainty, falsifier and exclusions. Hash rules fixing dsDNA at 50 and RNA at 40 ng/µL per A260 unit at 1 cm, path length, per-sample dilution factor, matched blank identity, subtraction rules, ordered A230/A260/A280/A320 wavelengths, inclusive corrected-A260 linear range, per-analyte purity bands, minimum replicates and relative agreement bound. Hash declarations establish identity, not historical preregistration.

Only background-corrected and blank-subtracted absorbance enters concentration and ratio arithmetic. Technical replicates do not increase sample n. Missing readings, negative corrected absorbance, out-of-range A260 and non-positive or relatively singular denominators remain unavailable. Purity-band flags are comparisons with frozen numbers, never sample suitability decisions. The smallest smoke fixture requires dsDNA 400 ng/µL, RNA 200 ng/µL and both ratios 2, checked independently by hand. Conversion accuracy, blank matching and physical validity remain assumptions requiring independent method review.

## Reference usage

Read [the reference index](references/index.json) and [stages and local record shapes](references/stages.md) before rule freeze, reading admission, numerical computation, validation or claim handoff. Reuse [the ordered plan](references/plan.json) in the existing manifest step shape. Record controlling reference paths and hashes in the existing reference-use-ledger; procedural references are never scientific evidence.

## Workflow

1. **01-rule-freeze.** Frame uncertainty with $cx-statistical-decision-analysis and preserve rules.json with $science-provenance before admitting readings. Freeze all controls and thresholds above; preserve original revisions and rejected alternatives. A post-outcome purity-band change requires an explicit exploratory label and recomputation under the reported bands.
2. **02-reading-qc.** Admit an immutable path-plus-hash nuc-readings-v1 table. Check unique sample and replicate identities, finite readings, explicit unavailable readings, the separate measured blank and exact frozen sample coverage. Subtract A320 from each wavelength, then subtract the matched background-corrected blank. Preserve failed controls and negative results.
3. **03-quant-purity.** Run scripts/validate_nucleic_acid_quant_purity_pack.py on the synthetic fixture first. Check corrected A260 against the inclusive frozen range, subtract background and blank before ratios, apply conversion factor times dilution divided by path length, and check replicate agreement. Invalid replicates make all their ratios and concentration unavailable, never zero; one invalid replicate also prevents sample-level pooling. Keep per-replicate flags and all exclusions.
4. **04-summary.** Preserve every sample, replicate, corrected value, flag and unavailable result. Summarize sample n and quantified, unavailable and flagged denominators without mixing analytes into a concentration mean. Report assumptions, uncertainty, sensitivity to blank/path/dilution, conflicts and limitations. Ratio-band excursions remain flags and never establish contaminant identity.
5. **05-handoff.** Register domain records as ordinary artifacts with $science-provenance and separate existing claim-register entries. Give rules, readings, hashes, controls, failures, execution/environment identities, reference ledger, dependencies, bounded claims and rejected alternatives to $science-review in record, source and method modes. The coordinator owns rigor classification and independent receipt registration. The pack leaves review unavailable.

Use one coordinator checkpoint with these five ordered stage IDs. There is no new execution engine. Retry only after correcting a named input defect; preserve failed revisions. Stop for missing essential input or an interpretation-changing choice; resolve reversible display preferences internally.

## Outputs

Pack-local schemas are nuc-pack-v1, nuc-rules-v1, nuc-readings-v1, nuc-report-v1, nuc-evidence-v1 and nuc-result-v1. Exact fields and limits are in the stages reference. Existing manifest, receipt, claim-register and MCP contracts remain unchanged.

Return normalized inputs and assumptions; immutable identities; corrected absorbance, concentration and ratios or unavailable values; replicate agreement; flags and denominators; dependencies, conflicts, uncertainty, applicability, limitations, inclusion/exclusion rationale and the smallest falsifiable next measurement. Record supported, contradicted, inconclusive and unavailable interpretations separately in the coordinator's claim register. Computed agreement cannot support positive scientific claims.

Synthetic acceptance artifacts and seeded defects are in examples/workflow-nucleic-acid-quant-purity/. Frozen questions and CPU budgets are in benchmarks/workflow-nucleic-acid-quant-purity/tasks.json. L4 denotes offline synthetic fixture acceptance in tests/test_workflow_nuc_pack.py; it does not establish assay or biological validity.

## Boundaries

Refuse claims of sample quality, suitability, sequencing, cloning, PCR or any downstream use. Association is never causality. Numerical agreement is never physical or clinical validity. Review approval is never truth. Refuse the conservative English wording families documented in the stages reference regardless of claim kind; that lexical check includes negations and is incomplete. Positive claims cannot cite computed or review-approval records. Any unavailable evidence or empty evidence list requires unavailable status without a positive assertion. This synthetic fixture cannot establish replication. External, independent and preregistered labels must not alias own artifacts by path or hash.

This route uses local CPU, standard library code and offline synthetic fixtures only. No network, download, installation, GPU, remote or heavy compute occurs. Human gates apply only before installation, restricted transfer, a new host, GPU/remote/heavy compute or an interpretation-changing choice, never at every admitted stage. Preserve failed controls and negative results. Absence of evidence remains unavailable, never negative evidence.
