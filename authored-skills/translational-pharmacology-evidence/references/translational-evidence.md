# Translational pharmacology evidence method

## Claim classes and decision semantics

Classify each material claim separately:

- **Target-disease rationale:** a genetic, expression, pathway, or disease-model observation connects target biology to indication. State the evidence type and inference distance; association or expression alone does not establish therapeutic benefit.
- **Binding or biochemical activity:** an assay measures target engagement or activity for a defined compound form and assay system. Record concentration, units, replicate structure, assay conditions, selectivity, and uncertainty. Binding is not functional efficacy.
- **Cellular pharmacology:** a defined perturbation changes a cellular endpoint in a specified model. Record target engagement, concentration, controls, exposure duration, endpoint, and alternative mechanisms.
- **Exposure-response:** measured or modeled concentration/exposure relates to a pharmacodynamic or efficacy endpoint. Distinguish total from unbound concentration, plasma from tissue, observed from simulated values, and correlation from causal mediation.
- **Preclinical efficacy or translation:** an animal or other model shows an outcome under declared dose, route, regimen, and disease context. This is model-specific and does not establish human benefit.
- **Human efficacy:** a clinical study estimates an outcome in a defined population and comparator. Record phase/design, endpoint, estimand, population, effect and uncertainty, analysis set, and multiplicity; trial registration is not an efficacy result.
- **Safety:** an adverse effect, exposure margin, or risk signal in a specified system/population. Preserve severity, denominator, exposure, follow-up, and uncertainty. Absence of a reported event is not evidence of safety.
- **Trial or regulatory status:** a registry state or regulator action at a dated point. It describes process/status only; it is not a result and does not transfer automatically across indications, formulations, or populations.

Keep scientific, clinical, safety, and regulatory conclusions separate. Evaluate go/no-go criteria only after stating the decision threshold, comparator, population, and consequence horizon. A decision label is conditional on those values and evidence boundaries.

## Sources, identity, and dependence

Resolve target identifiers and aliases, compound structure/salt/stereochemistry, active moiety, formulation, route, indication, and registry/trial identifiers. Record resource, release/version or access date, query, stable record ID, and immutable source snapshot/hash. Prefer primary articles, study reports, trial results, and official dated regulatory records for claims they directly establish; databases and registries are discovery/status sources unless they contain the result data.

Map program lineage across papers, compounds, formulations, animal studies, trials, populations, sponsor reports, and registries. Repeated registry mirrors or publications of the same trial are not independent evidence. Note reused cohorts, sites, controls, and shared compounds. For class effects, define the class and mechanism basis; do not treat chemically or mechanistically distinct compounds as independent replication of one compound's efficacy.

## Uncertainty and exposure chain

Carry assay variability, parameter uncertainty, sampling uncertainty, model uncertainty, censoring, missing outcomes, and source-dependence uncertainty separately. Preserve units and denominators; do not convert values without recording the equation, assumptions, and source inputs. Record `not reported` when the evidence omits uncertainty or exposure details.

Build an explicit chain: administered dose and formulation → absorption/distribution/metabolism/excretion context → measured or modeled free exposure at relevant site → target engagement → pharmacodynamic response → efficacy/safety outcome. Identify every unmeasured or modeled link. Scaling across species or systems requires an explicit rationale and uncertainty; otherwise report a discontinuity, not a seamless translation.

Assign confidence per claim and decision criterion. `Supported` means directly relevant evidence with no material unresolved conflict; `replicated` requires independent relevant cohorts or experiments; `suggestive` denotes indirect, imprecise, dependent, or incomplete support; `conflicting` preserves unresolved disagreement; `unsupported within assessed evidence` is scoped, not proof of falsehood; `unavailable` is not a negative result.

## Controls and sensitivity

Check identity and unit controls at every lane: compound form and concentration basis; target construct/species; positive reference ligand or expected assay response where available; vehicle, inactive compound, or target-negative control as appropriate; assay dynamic range; free versus total concentration; dose and route; and endpoint direction. For clinical evidence, verify comparator, enrollment/analysis denominators, outcome definition, and follow-up against the primary report. Failed controls invalidate or downgrade the affected link and remain visible.

Vary free-fraction and tissue-exposure assumptions, dose/regimen scaling, species/model choice, target-engagement threshold, source release, inclusion of shared cohorts, endpoint definition, and whether indirect/predicted lanes are included. A reversal of the exposure-to-effect conclusion, loss of independent support, change in go/no-go decision, or crossing of a prespecified threshold is fragile. Report the perturbation and retain all outcomes; do not tune assumptions to a preferred decision.

## Applicability domain and failure detection

Conclusions are limited to the target, compound form, assay/model, exposure range, indication, population, regimen, endpoint, and source cutoff in the contract. In-vitro potency may not predict achievable free exposure; animal models may miss human biology or toxicity; tissue exposure may differ from plasma; biomarker behavior may be context-specific; historical registry states may be superseded. Another indication's approval does not establish benefit for the target indication.

Detect common failures by matching structure and active moiety across records; checking assay units and concentration basis; comparing nominal dose with unbound exposure; tracing trial identifiers and cohort reuse; checking terminated/withdrawn and null programs; validating registry status against dated result reports; and challenging each inference link for direct support. If a link is missing, mark the chain discontinuity and lower the bounded claim rather than silently interpolate.

## Sources

Use ICH E8(R1) (2021) for clinical-study quality by design, ICH E9(R1) (2019) for estimands and sensitivity analysis, and FDA exposure-response guidance (2003) for concentration-effect reasoning. These are methodological/regulatory frameworks; application and current jurisdictional requirements must be checked in context, and none substitutes for primary evidence.
