# Open Targets association evidence interpretation

## Claim semantics

Use the narrowest class supported by the returned records. A **retrieval claim** says that a specified API release returned a record for the normalized target-disease pair. An **association-evidence claim** says that one or more returned evidence records support an association under their own methods and contexts. A **rank claim** says only that a pair ranks above another under the named release, score definition, filters, and weights. A **mechanistic or causal claim** requires evidence that identifies a causal relationship; an aggregate portal score does not qualify. A **clinical/actionability claim** requires fit-for-purpose clinical evidence and cannot be assigned from association score or known-drug annotation alone.

Open Targets calculates source-level association scores by a normalized harmonic sum of evidence scores, with rank-position weighting; datatype and overall aggregation apply data-source weights and their documented scaling. The overall score is a bounded aggregate of datatype/source evidence, not a probability, calibrated confidence, effect size, p-value, or posterior. Its value depends on evidence availability and scoring rules. The skill must report the score as returned and name its field/release; never convert it to a probability or compare numeric values across incompatible releases or weight settings.

Potential evidence categories include genetic, somatic, known drug, literature, animal model, and expression evidence. These are provenance families, not six independent replications. Assign `direct` only when the returned evidence directly links the resolved target and disease under its source method. Assign `indirect_or_propagated` when a link depends on ontology ancestry, inferred target mapping, text-mined co-mention, shared annotation, or another intermediate. Preserve the source's own directness signal if present; otherwise state that directness is unknown rather than infer it from the aggregate.

## Source dependencies and independence

For each component, retain source identifier, evidence identifier, source dataset or publication, cohort/study, method, target/disease mapping, and any propagation path returned. Collapse duplicate records only when identity is demonstrable; otherwise flag possible duplication. Two records are not independent merely because they have different rows, data types, or provider names: inspect shared cohorts, primary papers, reused summary statistics, common curation, copied annotations, and ontology propagation. Literature mining can re-express evidence already represented in genetic, clinical, or model databases.

Pin the Platform release/version reported by the response and record retrieval time, query, filters, fields, and any user-selected weights. If release is not reported, record `unknown`; do not substitute the date or current website state. A longitudinal comparison requires a fixed identifier mapping, compatible score semantics, and an explicit reconciliation of changed source records and weights.

## Uncertainty and controls

Carry uncertainty at the record level: absent, null, unresolved identifier, incomplete page coverage, unavailable source, ambiguous mapping, or unknown directness are distinct. An empty search is evidence only that this query returned no records in the observed scope/release, not that no association exists. Report under-coverage, study bias, evidence-source method limitations, and whether a score is dominated by one source.

Use a prespecified well-established target-disease pair as a positive retrieval/control check and a biologically unrelated or otherwise justified pair as a negative query control. Controls check query construction, identifier resolution, expected service behavior, and gross specificity; they do not validate every association. Also sanity-check one returned evidence record against its source identifier and expected entity IDs. If a positive control fails or a negative control returns plausible records, inspect identifier mapping, filters, query variables, and text-mining leakage before interpretation.

## Sensitivity and fragility

Repeat the ranking or claim after (a) excluding literature/text-mining evidence, (b) varying datatype/source weights across a justified range or using the unweighted/default configuration, (c) removing propagated/indirect evidence, and (d) aligning the cutoff/release where feasible. Record the exact setting and affected records for each run. Call the conclusion **fragile** if the target ordering, claim class, or decision-relevant interpretation changes under a reasonable prespecified setting; do not hide a weight-driven reversal behind one aggregate value. These checks assess robustness to representation choices, not causal validity.

## Applicability domain and failure detection

This method applies to retrieval and structured comparison of records exposed by the specified Open Targets Platform API release. It is weak for poorly studied diseases or targets, non-human contexts not represented by the query, entities with unstable mappings, and conclusions requiring individual-level estimates, causal identification, treatment effect, safety, or clinical utility. The Platform score reflects available evidence and its aggregation procedure, so low score can mean sparse coverage and high score can reflect repeated or propagated sources.

- **Literature-mining inflation:** detect by tracing publication/source identifiers and comparing rankings with literature evidence removed; report overlap and rank shift.
- **Shared-cohort or copied-record inflation:** detect shared study, cohort, publication, or source lineage; retain a dependency graph and avoid counting duplicates as replication.
- **Propagation mistaken for direct evidence:** inspect the evidence path and ontology mapping; label indirect or unknown and rerun without propagated records.
- **Score treated as probability:** detect claims using confidence/probability language or thresholds without calibration; replace with relative-ranking language and the exact score context.
- **Silent empty result or service failure:** validate status, schema, expected IDs, nulls, result count, and page completeness; report `unavailable` for failed service and `inconclusive`/empty for a successful zero-result query.
- **Release or weight mismatch:** compare reported release and scoring settings before ranking; reconcile or withhold cross-release comparison.

## Evidence-family interpretation

Use evidence-family labels as navigation aids and inspect each source method before assigning meaning.

- **Genetic:** record study/population, variant-to-gene and variant-to-disease mappings, and whether the score is association, colocalization, or another inference. A genetic association alone does not establish that perturbing the target changes disease outcome.
- **Somatic:** record cancer context, alteration type, and whether target and disease are linked by observed alteration, curated knowledge, or an inferred relationship. Do not generalize across tumor types without support.
- **Known drug:** distinguish target-drug and drug-indication records from a causal target-disease experiment. Record development or approval context when returned; missing status remains unknown.
- **Literature:** identify text-mined versus manually curated evidence and the cited publication. Co-mention or repeated review citations can inflate apparent volume without independent experiments.
- **Animal model:** retain species, model, intervention, phenotype, and mapping to human disease. A model phenotype is not a human treatment effect.
- **Expression:** record tissue, assay, direction, and context where available. Differential expression can be consequence, correlate, or artifact rather than causal support.

## Reporting rule

Present the aggregate only alongside evidence components, source dependencies, release, and settings. If an answer must rank targets, state that the ordering is conditional on the portal's evidence coverage and weights. Prefer “the Platform ranks this pair higher under these settings” over “this target is more likely causal.” If no component-level evidence is available, state that the score is opaque for the present question and do not infer which source drove it.

Keep retrieval facts separate from interpretation in the record:

1. Retrieval: entity IDs, response status, release, and returned score fields.
2. Evidence: source records, source-level methods, directness, and dependencies.
3. Interpretation: supported claim class, uncertainty, and sensitivity result.
4. Decision: any external threshold or action rule, with its independent justification.

Do not fill a missing stage from the stage above it. A high score cannot supply absent source-level evidence, and a source-level association cannot supply a clinical decision threshold.

Before writing a rank claim, make the comparison explicit:

- Name both normalized target-disease pairs and the exact score field.
- Hold release, cutoff, filters, and user-selected weights constant.
- State whether the score covers direct evidence only or includes propagated associations.
- Compare score components and source records, not just the overall number.
- Report missing components and whether either pair has materially less evidence coverage.
- Show whether the ordering survives the planned weight and propagation sensitivity checks.
- If any condition differs, describe separate within-release findings rather than a single numeric comparison.

The ranking is conditional on both the scoring algorithm and the evidence made available to it. More records can raise an aggregate without adding an independent experiment, and fewer records can lower a score without contradicting a biological relationship. This is why evidence lineage and coverage belong next to the reported score.

When a GraphQL response exposes directness or datatype fields, preserve those exact values alongside the skill's normalized classification. If the response contains only the aggregate, record directness and component lineage as unknown; do not reconstruct hidden components from a displayed rank.

For repeatable comparisons, retain the GraphQL document and variables verbatim and hash the response artifact. A later run can then distinguish query changes from source release changes and from scoring-weight changes.

## Sources

- Ochoa et al., “Open Targets Platform: supporting systematic drug–target identification and prioritisation” (2021), for harmonic aggregation, evidence scoring, and ontology-propagated associations; it describes the Platform's method and does not validate a specific pair.
- Buniello et al., “Open Targets Platform: facilitating therapeutic hypotheses building in drug discovery” (2025), for the updated Platform scope; its publication does not make aggregate scores causal or clinical proof.
- Open Targets Platform, “Target–disease associations” scoring documentation (living primary documentation; record the release and access date used for current score behavior).
- OLS4: “A new Ontology Lookup Service for a growing interdisciplinary knowledge ecosystem” (2025), for ontology service identity and version-sensitive term context; it does not validate target-disease associations.
