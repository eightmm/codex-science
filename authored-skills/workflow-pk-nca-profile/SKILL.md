---
name: workflow-pk-nca-profile
description: "Check supplied preclinical concentration-time profiles with frozen censoring and terminal-fit rules; calculate observed peaks, trapezoidal exposure and reliable-only geometric summaries. Use for offline animal or in-vitro arithmetic checks, never dose selection or human extrapolation."
license: MIT
---

# Preclinical Concentration-Time Profiles

Role: conductor with a small standard-library reference analyzer. All checked-in data and expected artifacts are **synthetic fixtures**. Output states arithmetic summaries of the supplied profiles only.

## Decision contract

Before reading the profile table, record the question, animal or in-vitro system, subject unit, route, nominal dose and units, time and concentration units, sampling schedule, lower limit of quantification (LLOQ), censoring rule and any explicit substitution, linear-up/log-down trapezoid method, exact terminal point window, minimum terminal points, minimum adjusted R-squared, maximum extrapolated AUC fraction and reported parameters. Freeze and hash these rules before the table is opened. Retain original rules and mark every outcome-informed revision exploratory.

The deliverable is an offline arithmetic check of already-measured profiles, never a dose recommendation. The baseline is the hand-derived synthetic exponential profile: AUC(0-tlast) = 15/ln(2), lambda_z = ln(2), half-life = 1, AUC(0-inf) = 16/ln(2), extrapolated fraction = 1/16. Acceptance requires these values, preserved censored tails, reliable-only group denominators and every seeded refusal. Disagreement is a falsifier of the arithmetic implementation; agreement cannot establish physical or clinical validity. No confidence interval or sampling uncertainty is estimated. Preserve measurement uncertainty and inspect sensitivity in separately labelled exploratory runs. Stop for missing essential identities, incompatible units or interpretation-changing choices; choose reversible presentation details internally.

## Reference usage

Read [the index](references/index.json) and [stages and record shapes](references/stages.md) before rule freeze, profile admission, computation, validation or handoff. Reuse [the plan](references/plan.json) with existing manifest steps. Record controlling reference paths plus hashes in the existing `reference-use-ledger`. References constrain procedure; they are not scientific evidence.

## Workflow

1. **01-rule-freeze.** Use the decision contract and `$cx-statistical-decision-analysis` to frame the decision and uncertainty. Hash rules before profile admission; preserve the frozen and effective path-plus-hash identities. Changed effective rules require `exploratory: true`. This verifies a declaration, never historical preregistration.
2. **02-profile-qc.** Admit unique subject IDs and strictly increasing unique times with consistent recorded units. Concentrations must be finite and non-negative. Carry below-limit values as `censored: true` and `concentration: null`. Numeric substitution is allowed only inside integration when explicitly frozen. Never silently turn a censored tail into zero or bridge an interior censored gap without a substitution rule. Preserve missing and failed controls.
3. **03-subject-parameters.** Run `python3 scripts/validate_pk_nca_pack.py examples/workflow-pk-nca-profile/pack.json` on the synthetic fixture first. Compute observed Cmax and earliest observed Tmax, linear-up/log-down AUC(0-tlast), the frozen-window log-linear terminal slope, adjusted R-squared, ln(2)/lambda_z, AUC(0-inf) and extrapolated fraction. Below-limit points never enter the fit. Too few points, a degenerate/nondecreasing slope, a poor adjusted fit or excess extrapolation leaves half-life and AUC(0-inf) `unreliable`, with reasons retained. Never silently retain them.
4. **04-group-summary.** Report geometric mean, range and n over reliable subjects only, stating the included subject IDs. An empty group has n=0 and unavailable summaries. Nonpositive quantities have unavailable geometric means rather than invented values. Observed parameters remain inspectable for excluded subjects; group summaries exclude those subjects entirely.
5. **05-handoff.** Register domain records as ordinary artifacts through `$science-provenance`; keep claim entries separate in the existing claim register. Preserve normalized assumptions, inclusion/exclusion reasons, dependencies, conflicts, failed controls, negative results, limitations and the smallest falsifiable next measurement. Hand rules, profile table, report, hashes, execution/environment identities and claims to `$science-review` in record, source and method modes. Rigor classification and independent review remain coordinator-owned. This pack never marks itself reviewed.

Use one coordinator checkpoint per run with these ordered IDs. This pack creates no execution engine, checkpoint or manifest. Correct a specific input defect before retrying and retain failed revisions. Do not weaken thresholds to pass. A second producer pass is never independent review.

## Outputs

Pack-local schemas: `pk-nca-pack-v1`, `pk-nca-rules-v1`, `pk-nca-profiles-v1`, `pk-nca-report-v1`, `pk-nca-evidence-v1`, `pk-nca-result-v1`. Exact shapes and limits are in the stages reference. They add no keys to existing global contracts, manifests, receipts or MCP tools.

Return the frozen identities, per-subject arithmetic and diagnostic reasons, reliable-only geometric means/ranges/denominators, exploratory label and fixed arithmetic boundary. The coordinator separately records supported, contradicted, inconclusive and unavailable claim interpretations using existing semantics, uncertainties, rejected alternatives and inclusion/exclusion rationale. Missing records and absent review remain `unavailable`, never negative evidence. Review approval is never truth.

Redistributable synthetic fixtures, expected artifacts and individually exercised seeded failures live in `examples/workflow-pk-nca-profile/`. Frozen questions and CPU budgets live in `benchmarks/workflow-pk-nca-profile/tasks.json`. L4 denotes software fixture acceptance through `tests/test_workflow_nca_pack.py`, never biological validation.

## Boundaries

Refuse bioavailability, safe or recommended dose, exposure-response, human exposure, efficacy, clinical relevance, causality, mechanism or physical-validity claims, regardless of a descriptive label. Refuse positive claims citing review approval or computed records by checking both declared kind and result. Unavailable citations require unavailable claims; an empty evidence list also requires unavailable status. Replicated status is refused for these synthetic fixtures. External/independent/preregistered labels cannot alias this study's own artifacts or hashes. The conservative English lexical gate is incomplete; its exact families are in the stages reference.

Association is never causality. Numerical agreement is never physical or clinical validity. Preserve failed controls and negative results. Hashes do not establish historical freeze timing, authenticity of measured inputs or independence. Arithmetic acceptance does not establish dose safety, terminal model adequacy or real-world applicability.

CPU-only, offline fixtures, standard library only: no network, installation, download, GPU or remote work. Human gates apply before installation, restricted transfers, new hosts, GPU/remote/heavy compute or interpretation-changing choices; not at every admitted offline stage. The validator writes nothing and has no output option.
