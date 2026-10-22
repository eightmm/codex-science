# GTEx sensitivity, validation, and failure handling

## Sensitivity analyses

Prespecify any threshold before interpreting the observed value. For an expression claim, vary the abundance cutoff across scientifically reasonable values and compare the exact tissues and release retained. For eQTL claims, report the endpoint's supplied statistical fields and evaluate the conclusion under alternative prespecified significance thresholds or multiple-testing criteria only when the data support that calculation. Do not infer significance from a rounded display value.

Repeat a tissue comparison under defensible tissue groupings and ontology mappings. A result is fragile if threshold or grouping choice changes the supported/inconclusive status, reverses the ordering, or changes which tissues qualify. Record the values, counts, mapping, and status for every alternative. If cell composition or postmortem/batch effects plausibly drive the change, lower the claim scope or report inconclusive.

## Controls

Use a known housekeeping gene and a known tissue-restricted marker as contextual checks when the same release, endpoint, and tissue make comparison possible. Record missing control data as unavailable rather than failed. A positive sanity-control pattern does not validate the target measurement; it only shows that the query and selected context can recover a plausible reference pattern. Never select a control after seeing target results without labeling it exploratory.

## Failure modes and detection

- **Absence of evidence treated as absence of expression:** detect by distinguishing no-match, zero, null, omitted, and filtered states; a missing record is unavailable, not a negative expression call.
- **Bulk tissue treated as a cell type:** detect when the claim names a cell population but the source reports a tissue aggregate; narrow the claim or use an appropriate cell-resolved source.
- **Donors counted as independent across tissues:** detect shared donor/cohort and release provenance; model/report the shared dependence and do not call it replication.
- **TPM or other normalization misread:** detect against the endpoint field definition and recorded units; stop comparison if metric or processing differs.
- **Postmortem or technical effects ignored:** detect missing relevant covariates, RNA quality, collection context, or batch information; qualify comparisons and avoid causal biological explanations.
- **Wrong gene, tissue, genome build, or allele:** detect against returned identifiers, mapping record, ontology, and allele/build; stop if unresolved.
- **Partial response treated as complete:** detect page/count inconsistency, truncation indicators, or malformed payload; mark coverage incomplete and status unavailable/inconclusive.
- **Release drift silently pooled:** detect release differences in response metadata; split the evidence records and reconcile explicitly.
- **Association presented as causal mechanism:** detect claims about mediation, disease mechanism, or causal effect unsupported by colocalization or intervention evidence; downgrade to association.

## Evidence boundary

This procedure validates interpretation of returned GTEx records and their stated context. It does not certify the source pipeline, establish disease or cell-specific biology, prove causal effects, or replace independent data and review. Preserve response extracts, query ledger, exclusions, release, and hashes with the claim.

## Sources

- GTEx Consortium. “The GTEx Consortium atlas of genetic regulatory effects across human tissues.” *Science* (2020). It describes v8 RNA-seq and QTL analysis in postmortem donor tissues; it does not make every API field universally available.

## Comparison record

For each tissue comparison, report the numerator/denominator or returned estimate and its donor/sample basis, metric, release, ontology mapping, and inclusion rule. Align tissues only at the coarsest anatomy level justified by the samples. If a comparison needs covariate-adjusted inference but adjusted estimates are unavailable, state that the comparison is descriptive and do not imply statistical equivalence.
