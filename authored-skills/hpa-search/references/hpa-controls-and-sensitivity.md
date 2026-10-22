# HPA controls, sensitivity, and failure handling

## Controls and sanity checks

When data exist in a compatible release and assay, query a broadly expressed housekeeping gene (for example, RPLP0) and a tissue-restricted gene appropriate to the tissue (for example, ALB in liver). Record expected pattern, gene IDs, tissue, assay, metric, and antibody/reliability details before evaluating the target. A pattern mismatch prompts review of identifier mapping, tissue/cell mapping, assay, normalization, response coverage, and antibody reliability. Controls are diagnostic checks, not universal expression truths and not proof that the target assay is valid.

Do not compare RNA control values to protein controls as if they shared a measurement scale. For a localization question, use a known compartment marker only when a suitable same-assay/source record is available; otherwise mark that control unavailable. Do not select controls after observing the target without labeling the choice exploratory.

## Sensitivity analyses

Prespecify expression thresholds and reliability inclusion criteria. Re-evaluate the target under reasonable alternative score or abundance cutoffs, including the source's reported categorical interpretation where available. Do not invent universal cutoffs. Re-evaluate tissue groupings and ontology mappings; keep the source label when a mapped grouping is uncertain. A change in claim status, tissue ordering, or protein/RNA interpretation under a reasonable alternative is fragile and must be reported.

For cross-assay comparison, report RNA and protein claims separately, then ask whether their qualitative pattern agrees within matched gene, tissue, and release context. Agreement is not replication and disagreement is not automatically a biological contradiction because modality, sample set, sensitivity, and protein turnover differ. Record which evidence streams are shared or independent.

## Failure modes and detection

- **Absence of evidence called absence of expression:** detect by separating no match, zero, null, omitted, filtered, and unmeasured states; empty search results are unavailable.
- **RNA treated as protein or vice versa:** detect the assay and field before claim assignment; split the claim by modality.
- **Antibody score omitted or treated as concentration:** detect missing antibody/reliability metadata or unsupported quantitative interpretation; qualify or stop the protein claim.
- **Localization treated as function:** detect functional or causal language unsupported by an assay observation; downgrade to localization description.
- **Tissue treated as cell type:** detect aggregate tissue labels or uncertain ontology mapping; retain the source label and narrow the claim.
- **Gene symbol collision:** detect disagreement between symbol, Ensembl ID, and returned record; preserve alternatives and stop if unresolved.
- **Release or route drift:** detect changed response metadata, columns, or endpoint; split records and reconcile before comparison.
- **Incomplete structured result treated as complete:** detect truncation, count/page mismatch, malformed fields, or endpoint errors; set coverage incomplete and status unavailable/inconclusive.
- **Threshold-driven narrative:** detect a supported status that changes with a reasonable cutoff or grouping; report fragility and avoid a categorical summary.

## Evidence boundary

This procedure supports bounded reading of HPA records; it does not validate antibodies independently, establish function, prove absence, or make RNA/protein assays interchangeable. Retain raw/bounded extracts, serialized query, release, exclusions, reliability annotations, and hashes with the evidence record.

## Sources

- Uhlén et al. “Tissue-based map of the human proteome.” *Science* (2015).
- Thul et al. “A subcellular map of the human proteome.” *Science* (2017).
- Uhlén et al. “A proposal for validation of antibodies.” *Nature Methods* (2016).

## Comparison record

For each result, report the matched gene, source tissue label, assay, release, metric, and reliability category. A cross-tissue statement should name included and excluded tissues and the grouping rule. For a cross-assay statement, show the RNA and protein records separately with their own evidence source and uncertainty; qualitative agreement is descriptive and does not mean the assays are calibrated.
