# cBioPortal cohort and claim semantics

## Claim classes and assignment

- **Portal/study description:** assign when a statement repeats study metadata, profile labels, or reported counts. Cite the exact study/profile and retrieval date; do not imply a reanalysis.
- **Cohort estimate:** assign only when alteration definition, molecular profile, eligible sample list, sample-versus-patient unit, numerator, denominator, and missing/unprofiled cases are explicit. State the target cohort as the records actually queryable, not all people with the cancer.
- **Association:** assign only for an explicitly defined comparison with outcome, comparator, analysis population, endpoint/time origin, and method available from the source or supplied analysis. Preserve the reported effect and uncertainty. Portal stratification is not evidence of a causal effect.
- **Survival association:** require endpoint definition, follow-up/censoring context, group definition, denominator, and reported statistical output. Treat exploratory cutpoint search or unreported adjustment as a limitation. Do not infer treatment benefit or individual prognosis.
- **Clinical interpretation:** cBioPortal alone is insufficient for diagnosis, prognosis, therapy choice, or patient-level advice; route elsewhere and retain this source as one bounded evidence record.
- **Unavailable, contradicted, inconclusive:** unavailable means the relevant source/query/field is inaccessible or absent; contradicted means the inspected source conflicts with the scoped claim; inconclusive means the source is compatible with multiple interpretations or lacks the required denominator/analysis. A missing record is not a negative result.

Use statuses consistently: `supported` when inspected in-scope evidence meets its stated criterion, `contradicted` when it conflicts, `inconclusive` when criteria or interpretation remain unresolved, and `unavailable` when the source prevents inspection. Status is not a probability.

## Source dependencies and independence

Keep the source study, molecular profile, sample list, clinical table, and any derived portal view as separate nodes. Record stable study/profile IDs, source publication, data release/update marker actually returned, query/filter version, and access time. Pin the current API contract and the response's release metadata when available; if the source provides no immutable data revision, state that limitation and preserve response hashes.

One publication can describe multiple studies or profiles, and multiple portal studies can reuse the same cohort, institutions, or samples. Compare cohort provenance and inclusion dates before treating them as independent evidence. Patient and sample counts are not interchangeable: a patient may contribute multiple samples, and a sample list can have a different denominator from a clinical endpoint. Do not sum overlapping cohorts or count repeated portal representations as replication.

Record links between profile, sample list, endpoint, paper, and any outside source used to resolve gene identity. Gene aliases map to a biological target but do not establish identical variant consequences or assay coverage. For multi-cohort work, use `$cx-cancer-genomics-evidence` to reconcile dependencies and avoid combining incompatible definitions.

## Uncertainty and missingness

Report numerator and denominator with units and the exact eligibility rule. Preserve unprofiled samples, failed assays, filtered records, missing clinical outcomes, and null values separately. If the portal does not expose a count or filter, state it as unavailable rather than estimating it. Distinguish data uncertainty (measurement/call quality), sampling uncertainty, missingness, and analysis uncertainty.

Use source-reported uncertainty when available. For a computed proportion or contrast, label the calculation as derived, state method and assumptions, and do not attach precision that the data do not support. Small cohorts, sparse events, multiple testing, censoring, and uncertain eligibility can dominate a nominal estimate. Carry these limitations into each claim status and summary; do not hide them in a pooled score.

## Cohort estimate reporting

For an alteration frequency, record whether the unit is a sequenced sample or a unique patient and whether a patient contributes multiple samples. Define the profile's alteration categories and any filter used (for example, mutation class or copy-number call threshold) from source documentation; do not merge unlike call classes into one estimate without an explicit rationale. Include zero-event cohorts only when the eligible denominator and profile coverage are known.

Keep a flow count: eligible records considered, records with profile coverage, records excluded by the query, and records used in the estimate. If counts cannot be reconciled, report the estimate as unavailable or inconclusive. The portal's sample count is not automatically the denominator for an outcome-specific analysis.

For cross-study summaries, report each cohort estimate separately before any combination. Do not pool if populations, assay profiles, eligibility, alteration definitions, or units are incompatible. When pooling is justified by a separate analysis contract, retain cohort-specific estimates and dependence warnings alongside the pooled result.

## Association interpretation

An association claim must state whether it is directly reported by the source or recalculated from returned data. Record comparator, effect measure, uncertainty, endpoint, and any adjustment actually applied. If p-values or effect estimates are absent, do not infer them from plots or group labels. If multiple tested genes, endpoints, or cutpoints are evident but correction is not described, mark multiplicity uncertainty.

For survival, preserve the source's named endpoint and time origin. Check whether follow-up and censoring are described and whether group size/event counts are available. A Kaplan-Meier separation or log-rank output does not establish adjusted prognosis or treatment effect. Keep all source-reported caveats with the evidence record.

## Query and response integrity

Store the exact query string, filters, tool/API identity, page bounds, and response completeness alongside any derived table. Repeated pages or overlapping filters can duplicate samples; deduplicate only using documented stable identifiers and retain the rule. If the source returns only an aggregate and no record identifiers, do not claim record-level exclusion auditing.

When direct API fields differ from the portal display, preserve both responses with access timestamps and report the mismatch. Do not select whichever view better supports the expected conclusion. If query coverage cannot be established, describe the returned records as a partial search rather than a complete cohort census.

For time-sensitive questions, state the evidence cutoff separately from retrieval time; a response accessed later may contain studies or annotations published after the cutoff.

## Controls and sanity checks

- **Identity positive control:** confirm a well-known gene identifier or a deliberately selected study gene resolves to the expected stable identifier and profile; record the crosswalk used.
- **Query negative control:** use an impossible or clearly invalid identifier/filter only as a parser/query sanity check, never as biological evidence. Confirm that an empty result is distinguished from a failed request.
- **Denominator check:** reconcile displayed/query counts with the eligible sample list and profile coverage. A frequency without a matching denominator fails this check.
- **Clinical consistency check:** confirm endpoint values and sample/patient joins align to the same unit; inspect duplicate or missing join keys before interpreting survival or phenotype strata.
- **Reference comparison:** where feasible, compare a small known record or study metadata with its cited publication or repository record. Agreement checks retrieval, not independent replication.

## Sensitivity analysis

For frequencies, vary only defensible choices: sample versus patient unit, study inclusion, assay/profile coverage, alteration class, and treatment of unprofiled or missing records. For associations, additionally vary a prespecified endpoint definition, strata/cutpoint only if clinically or analytically justified, and reported adjustment set. Mark any post hoc choice exploratory.

Call a result fragile when its direction, approximate magnitude, status, or ranking changes under a plausible eligibility/missingness/profile choice; when one study drives the aggregate; or when sample overlap changes the apparent replication. Preserve each variant's numerator, denominator, assumptions, and result. If the source cannot provide enough information to test a material choice, report the limitation and downgrade certainty.

## Applicability domain

cBioPortal is useful for exploring deposited cancer-genomics studies and their associated clinical profiles. Its searchable content, update cadence, assay coverage, and study-level curation vary. It does not represent a population-based sampling frame by default. Portal presence does not establish representativeness, assay comparability, complete follow-up, or clinical validity. Mutation, copy-number, expression, and other profile types have different measurement and missingness processes; do not treat them as interchangeable.

## Common failure modes and detection

- **Alias or variant mismatch:** detect with stable identifiers and review of genomic/transcript context; retain aliases and refuse silent remapping.
- **Wrong profile or sample set:** detect by checking study/profile IDs, assay type, and query counts against the decision contract.
- **Denominator drift:** detect by recomputing eligible counts from the matching sample list and recording sample/patient unit.
- **Missing-as-wild-type error:** detect by separating unprofiled, filtered, null, and negative calls in the table.
- **Duplicate cohort counted twice:** detect shared publication, institution, enrollment dates, and sample provenance; mark overlap unresolved if IDs are unavailable.
- **Survival overclaim:** detect absent censoring, endpoint, time-origin, group, or adjustment details; downgrade from association or stop.
- **Stale or truncated response:** detect response release marker, page/count reconciliation, schema validation, and preserved completion fields.
- **Terms violation:** detect study-specific usage restrictions before export or redistribution; retain citation and do not redistribute restricted data.

## Sources

- Cerami et al. (2012), “The cBio Cancer Genomics Portal: An Open Platform for Exploring Multidimensional Cancer Genomics Data,” *Cancer Discovery*.
- Gao et al. (2013), “Integrative analysis of complex cancer genomics and clinical profiles using the cBioPortal,” *Science Signaling*.
- cBioPortal Web API documentation and study-specific data/usage information. These sources describe portal access and data context; they do not validate a biological association or establish a cohort as representative.
