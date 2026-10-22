# Bgee controls, sensitivity, and failure handling

## Controls and sanity checks

When comparable records exist, inspect a broadly expressed housekeeping gene such as RPLP0 and a tissue-restricted gene appropriate to the queried species, anatomy, and developmental stage. Freeze the control choice before examining the target. Record gene mapping, condition, release, evidence type, observed/propagated state, and call quality. A mismatch prompts review of species, gene ID, ontology mapping, call coverage, propagation, and contributing experiments. It is not permission to alter the query until a desired result appears.

A control pattern in one species or stage is not automatically a control in another. If there is no suitable tissue-restricted control or no comparable evidence type, mark it unavailable. Controls are sanity checks and do not validate target-specific assays.

## Sensitivity analyses

Where the release supplies confidence/call-quality categories, compare the result under inclusion of high-confidence calls versus the broader declared set; do not invent cutoffs or assume ordinal labels are calibrated probabilities. For rank/score claims, vary a prespecified inclusion threshold and retain its denominator and ranking universe. Re-evaluate alternative defensible anatomy groupings and developmental-stage aggregations, preserving direct versus propagated state.

A conclusion is fragile if the claim status changes, a present/absent interpretation reverses, a rank ordering materially changes, or a propagated record is mistaken for direct evidence under a reasonable alternative. Record every filter, ontology mapping, record count, and changed outcome. If no comparable alternative can be computed, state the sensitivity analysis as unavailable.

## Failure modes and detection

- **No result interpreted as absence:** detect by verifying whether Bgee returned an explicit absent call versus no matching record; only the explicit call can support the bounded absent-call claim.
- **Propagated call presented as observed:** detect the source propagation annotation and ontology path; label propagation and retain source granularity.
- **Integrated call counted as many replications:** inspect contributing experiments and shared datasets; count source experiments with dependencies, not display rows or propagated conditions.
- **Call quality treated as probability:** check release documentation for scale meaning; report the native label if calibration is not defined.
- **Orthologs or species merged:** compare taxon and canonical IDs; require an explicit orthology mapping and separate claims by species.
- **Tissue, cell, or stage overgeneralized:** compare source label and UBERON/CL/stage mapping; retain unmatched dimensions and stop direct comparison.
- **Missing evidence treated as zero expression:** distinguish absent annotation, no call, explicit absent call, filtered row, null, and failed retrieval.
- **Partial or stale data treated as current/complete:** inspect release metadata, endpoint response, counts, pagination, and truncation; split releases and mark incomplete coverage unavailable/inconclusive.
- **Threshold chosen after seeing target result:** compare against recorded prespecified threshold; label post hoc analyses exploratory and report fragility.

## Evidence boundary

This procedure interprets release-pinned Bgee records and their source-defined integration. It does not establish true biological absence, exhaustive condition coverage, protein expression, function, localization, or causal relevance. Preserve source records, exclusions, query parameters, release, ontology mappings, and hashes.

## Sources

- Bastian et al. “The Bgee suite: integrated curated expression atlas and comparative transcriptomics in animals.” *Nucleic Acids Research* (2021).
- Bgee expression-call documentation for the selected database release.

## Comparison record

For each condition comparison, list the species, gene ID, anatomy and stage terms, direct/propagated state, call quality, release, and included records. Keep rank universes and evidence types explicit. If ontology aggregation changes which conditions contribute, show the before/after record set and describe the result as fragile when its interpretation changes.
