# Indication evidence reconciliation

## Claim classes and assignment

Assign one primary class to each claim, then preserve supporting subclaims rather than blending them.

- **Genetic association:** human inherited variation is associated with a phenotype in a defined population. Record study design, phenotype, ancestry, effect estimate, uncertainty, and whether the evidence is association, fine-mapping, or a causal inference. Do not label association causal without a separate identification argument.
- **Expression:** a transcript, protein, or cellular feature is observed in a named tissue, cell type, state, or assay. Expression locates biology; alone it does not show disease causality, target dependence, or therapeutic effect.
- **Preclinical model:** a perturbation or intervention changes a measured endpoint in a specified in vitro, ex vivo, or animal model. Record model, construct, dose/exposure, endpoint, control, and relevance to the human indication. Model activity is not clinical efficacy.
- **Clinical-trial:** a protocol is registered, recruiting, active, completed, terminated, or has results posted/published. Separate administrative status from outcome evidence; record registry record/version and publication identifier independently.
- **Approval:** a named regulator authorized a product for a specific jurisdiction, population, indication, formulation, and date. Verify primary regulator labeling or decision documents. Approval elsewhere or for a related indication does not transfer.
- **Mechanistic, biomarker, safety, or commercial:** name the narrower claim and its direct evidence. Commercial activity, patents, announcements, and pipeline listings establish activity/status, not biological or clinical benefit.

For every claim, record required support, falsifier, evidence IDs, status (`supported`, `contradicted`, `inconclusive`, `unavailable`), directness to the exact indication, dependencies, uncertainty, and applicability. Keep target-indication rationale distinct from efficacy and from a go/no-go decision.

## Source dependencies and independence

Build a dependency group for shared cohorts, trial participants, samples, cell lines, animal models, target perturbations, authorship programs, source portals, and propagated summaries. Multiple portals reproducing one study count as one underlying evidence source. Link a paper to its registry and sponsor record; do not count these as independent outcome observations.

Pin identifiers and versions: disease ontology and target IDs, paper DOI/PMID, trial registry ID and record version/date, product/regulator identifier, source release/update date, query, and retrieval date. Preserve accession and trial aliases. A pipeline page without an update date is time-sensitive and should be marked age-uncertain.

State the evidence cutoff before retrieval. If a registry, approval record, or pipeline entry changes after cutoff, place it in a dated update lane rather than silently revising the frozen assessment. Record missing pages, unavailable records, and failed queries separately from evidence of absence.

## Uncertainty and bias

Carry uncertainty at the claim and evidence-row level: estimates and intervals when supplied, sample size/denominator, design limitations, indirectness, missing outcomes, source age, and unresolved contradiction. Do not invent precision or convert qualitative evidence grades into numerical probabilities.

Consider publication bias, selective outcome reporting, survivorship bias in visible development programs, and sponsor/publication incentives. An unreported trial result is not a negative result. A terminated program may reflect safety, efficacy, financing, strategy, or operations; do not infer which without evidence. State how each bias could change the dossier conclusion.

## Controls and sanity checks

- Confirm a known identity chain from disease to ontology terms, target IDs, and the intervention; inspect synonyms that could retrieve another indication or paralog.
- For trial claims, compare registry status/date with posted results and linked publications; inspect participant count, primary endpoint, and actual result availability.
- For approval claims, verify regulator, jurisdiction, label, indication, population, and decision date against a regulator source.
- For preclinical claims, check a matched vehicle/control and whether the reported endpoint and model can address the named claim.
- Check whether evidence rows resolve to distinct cohorts/experiments; collapse duplicated portal summaries before counting support.

If a control is unavailable, report the limit and downgrade the affected claim to inconclusive when the missing check is essential.

For directness, explain the chain from the observed population or model to the intended indication. Record each extrapolation step: species or model to human, biomarker to patient outcome, target modulation to treatment effect, and adjacent indication to target indication. A shorter chain can still be weak if the measurement is biased or unreplicated.

Do not combine evidence dimensions into a single opaque score. If a ranking is needed, state the rule, decision threshold, and evidence dimensions it uses, and retain the underlying per-claim judgments. The rule is a decision aid whose result changes when assumptions or thresholds change.

## Reconciliation record

Use one row per source record and one claim register entry per proposition. A concise row should preserve:

- claim identifier and exact proposition;
- source record, version/date, query, and evidence class;
- population/model, endpoint, denominator, estimate, and uncertainty;
- directness, independence group, missingness, and inclusion decision;
- support/contradiction status and reason for any exclusion;
- applicability limits and the next observation that could change the decision.

When two sources disagree, first check whether they measure the same population, intervention, endpoint, and time. If not, retain separate scoped claims. If they do, compare design quality, dependency, precision, recency, and missing results; do not resolve the conflict by majority vote or by choosing the newest portal summary.

The evidence cutoff is the final date through which sources were inspected, not the publication date of the newest included paper. Record retrieval timestamps and source update dates separately so later updates can be reconciled without rewriting the frozen dossier.

## Sensitivity analyses

Re-evaluate the synthesis after varying the evidence cutoff, inclusion of indirect models, minimum directness, duplicate/dependency grouping, publication-only versus registry-plus-publication evidence, and stale-pipeline exclusions. Report any status or decision-threshold change. A conclusion is fragile if a reasonable variation changes claim status, crosses the stated go/no-go threshold, or changes the smallest next action.

Do not search for a favorable cutoff after observing the result. Keep the originally declared analysis primary and label other cutoffs as sensitivity views.

## Applicability domain and failure modes

This workflow organizes public evidence for a defined therapeutic indication; it does not estimate treatment effect, validate a biomarker for clinical use, replace regulatory review, or establish patient-level benefit. Applicability is limited by population, disease subtype/stage, ancestry, assay, model system, intervention, endpoint, geography, source completeness, and cutoff.

| Failure mode | Detection and response |
| --- | --- |
| Trial registration reported as efficacy | Compare registry fields with posted or published outcomes; classify status and results separately. |
| Shared cohort counted as replication | Trace study/sample provenance and group propagated records before synthesis. |
| Target rationale presented as indication efficacy | Inspect the claim's directness and supporting evidence class; split rationale and efficacy claims. |
| Stale pipeline entry treated as current | Check last-updated date and source snapshots; mark age uncertain or exclude from current-state claims. |
| Publication or survivorship bias hides null/terminated work | Search registry and termination/status records; state unresolved missing outcomes and alternative explanations. |
| Related approval generalized across contexts | Verify the exact regulator label and population; restrict or mark the claim unavailable. |
| Mechanism or expression treated as causality | Require direct perturbation or causal evidence appropriate to the claim; downgrade unsupported causal language. |

## Sources

- International Council for Harmonisation, **E8(R1) General Considerations for Clinical Studies** (2021): study-quality and design considerations, not a universal evidence hierarchy.
- U.S. Food and Drug Administration, **Clinical Trial Endpoints for the Approval of Cancer Drugs and Biologics: Guidance for Industry** (2018): endpoint context for oncology drug development, not a general target-validation rule.
- U.S. Food and Drug Administration, **BEST (Biomarkers, EndpointS, and other Tools) Resource** (2016): biomarker and endpoint terminology and context.
