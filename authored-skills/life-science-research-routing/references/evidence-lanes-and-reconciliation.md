# Evidence lanes and reconciliation

## Claim semantics

Assign stable claim IDs and use a claim class that describes the inference: **descriptive** (what was measured or recorded), **associational** (co-variation without intervention identification), **causal** (an intervention or defensible identification strategy supports a counterfactual contrast), **mechanistic** (evidence supports a specified biological process), **predictive** (performance on data independent of model development under a defined deployment domain), **comparative** (a stated contrast between methods, interventions, or groups), **translational** (evidence bridges a specified model or population to another domain), **clinical** (patient-level diagnostic, prognostic, or therapeutic claim), or **operational** (a workflow, system, or resource behaved as recorded). State required support, a material falsifier, population/species, assay, endpoint, time scale, and applicability domain. Status is planned, supported, contradicted, inconclusive, or withdrawn. Confidence cannot exceed the weakest essential evidence link.

Use evidence labels consistently: **direct** addresses the claim with the measured entity/population and endpoint; **replicated** has independent evidence with compatible design and outcome; **suggestive** is relevant but indirect, underpowered, or dependent; **absent (negative evidence from a prespecified search)** means the prespecified search/evaluation found no qualifying evidence; **contradictory** means material evidence supports incompatible conclusions; **unavailable** means evidence could not be retrieved or evaluated. Keep absent evidence distinct from missing, filtered, stale, and unavailable results.

## Source dependencies and independence

Pin each source, version/release, access date, exact query, inclusion/exclusion rule, and record ID. Build dependency groups for shared cohorts, donors, samples, publications, registries, source portals, copied/propagated records, templates, model training data, code, and transformations. A second article or portal is not replication when it reuses the same cohort or upstream assertion. A second model is not independent if its training data overlap or its features/labels derive from the same records. Record uncertain overlap and lower the evidence weight instead of assuming independence.

Create lanes only for questions that can be evaluated independently. Each receipt links claim IDs to exact retrieved and excluded records, artifacts, dependencies, limitations, confidence, and unresolved questions. Keep normalization, dependency deduplication, and final claim status in the coordinator; route cross-lane conflict reconciliation to `$cx-biomedical-evidence-reconciliation`. Do not pass the intended conclusion to an independent reviewer lane.

## Uncertainty

Record the source of uncertainty: sampling, measurement, missingness, confounding, mapping, model, publication, retrieval, or interpretation. Use intervals or calibration only when the method and target population justify them; otherwise use a qualitative level and concrete rationale. Preserve conflicting estimates and their denominators rather than averaging incompatible populations or endpoints. Separate uncertainty within a study from uncertainty about transport to the target domain. State whether a negative finding had enough sensitivity, power, coverage, and measurement quality to test the claim; otherwise mark it inconclusive or unavailable.

## Controls and sanity checks

- **Positive control:** use a known relevant record, intervention, entity mapping, or benchmark outcome to confirm that the query and extraction path can detect expected evidence.
- **Negative control:** use an irrelevant entity, incompatible population, or outcome expected not to support the claim; inspect false matches and leakage.
- **Retrieval integrity:** inspect pagination, truncation, response validation, and stable identifiers; reconcile counts against source results when possible.
- **Claim linkage:** verify every material statement traces to evidence or an artifact with the correct claim ID and scope.
- **Independence check:** deduplicate cohorts, samples, propagated assertions, and training data before counting replications or validation sets.
- **Reviewer separation:** provide the reviewer the frozen evidence and claim contract without desired conclusion or mutable search state.

Controls test the retrieval and interpretation path; a passing control does not establish completeness or truth outside the evaluated sources.

## Sensitivity analysis

Reassess claims under plausible changes to source release/cutoff, query expansion, inclusion/exclusion rules, entity mapping, dependency grouping, evidence class, population restrictions, endpoint definition, and confidence assumptions. For quantitative synthesis, vary justified effect measures and heterogeneity assumptions; do not combine incompatible outcomes merely to obtain a pooled value. A result is fragile if a plausible choice changes support status, direction, material rank/order, or applicability. Report the exact assumption and records responsible, and preserve the primary analysis alongside sensitivity variants.

## Applicability domain

The workflow routes evidence synthesis; it does not guarantee source coverage, causal identification, mechanistic truth, predictive calibration, clinical utility, or transfer across species, ancestries, assays, tissues, platforms, or time. Clinical and high-stakes decisions require appropriate specialist and regulatory processes. Public or observational evidence cannot alone justify patient-specific advice. Stop or qualify when essential evidence is inaccessible, the claim lacks an identifiable test, or the evidence domain excludes the intended population.

## Common failure modes and detection

| Failure | Detection |
| --- | --- |
| Association described as causation | Check intervention/identification assumptions, confounders, temporality, and claim class. |
| Duplicate cohort counted as replication | Compare cohort, donor, sample, publication, and registry provenance; group shared records. |
| Search failure reported as absent evidence | Inspect query logs, pagination, errors, access state, and coverage; distinguish absent from unavailable. |
| Prediction called validated | Confirm frozen independent evaluation data, leakage controls, target metric, and deployment domain. |
| Conflicts averaged across incompatible endpoints | Compare population, assay, comparator, endpoint, and time scale before synthesis. |
| High confidence from one weak link | Trace the claim-evidence graph and cap confidence at the weakest essential dependency. |
| Intended conclusion leaks into review | Inspect reviewer inputs and confirm separation from the coordinator's desired answer. |
| Retrieved result treated as complete source coverage | Check release, query syntax, pagination, truncation, and source-specific missingness. |

## Sources

- PRISMA 2020 (Page et al., 2021): transparent reporting of search, selection, and synthesis; reporting completeness does not eliminate bias.
- GRADE (Guyatt et al., 2008): structured certainty assessment across evidence bodies; apply domain-appropriate criteria rather than treating labels as numeric probabilities.
- ROBINS-I (Sterne et al., 2016): risk-of-bias assessment for non-randomized intervention studies; not a substitute for a causal design.
- STROBE (von Elm et al., 2007): transparent observational-study reporting, including limitations and participant flow.
- CONSORT (Schulz et al., 2010): trial design and reporting context; a reported trial is not automatically applicable to another population.
- FAIR Guiding Principles (Wilkinson et al., 2016): provenance and reuse metadata for research objects; FAIR status is not evidence validity.
