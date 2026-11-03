---
name: workflow-dose-response-curve
description: "Fit in-vitro concentration-response curves with frozen assay declarations, labelled biological and technical replicates, control separation, constrained four-parameter logistic curves and potency intervals. Use for EC50 or IC50 evidence; never prescribing or patient benefit."
license: MIT
---

# Dose-response Curve Pack

This conductor composes `$cx-translational-pharmacology-evidence`,
`$science-provenance` and `$science-review`. The local reference computation is
CPU-only and standard-library-only; its checked acceptance uses synthetic fixtures.
It is not a general fitting engine or a validated experimental assay.

## Decision contract

Before fitting, freeze compound identities and forms, assay system and endpoint,
EC50 or IC50, concentration units and series, biological independent units,
technical repeats, vehicle and positive controls, readout normalisation,
minimum concentration/replicate counts, control window and separation threshold,
outlier rule, model constraints, optimizer and bootstrap settings. Hash that
declaration and the observed plate separately; never rewrite frozen inputs.

The deliverable is in-vitro statistical evidence only. Declare claim IDs,
required measured support, falsifiers (failed controls, nonconvergence, boundary
hits or unidentifiable potency), and the permitted descriptive or associational
inference. Numerical agreement cannot establish physical or clinical validity.
Missing essential input is unavailable, never negative evidence. Freeze the
protocol before observing outcomes and before any fit; byte hashes alone do not
prove when a declaration was made.

## Reference usage

Read [stages](references/stages.md) before freezing inputs, fitting, uncertainty
or claims. Read [records](references/records.md) before authoring artifacts or
running the validator. Read [plan](references/plan.json) before checkpoint setup.
The [index](references/index.json) supplies stable IDs and required operations.
Record each materially controlling reference path and SHA-256 in the existing
`reference-use-ledger`; procedural references are not scientific evidence.

## Workflow

1. **01-assay:** inspect compound identity, units, biological independence,
   controls and assay applicability. Compose the translational pharmacology
   skill only for context; do not import a translational claim. Freeze and hash
   `dose-response-assay-v1` and `dose-response-plate-v1` before fitting.
2. **02-qc:** apply the prespecified control window, Z-prime style separation,
   minimum counts and exclusion rule. Record every excluded well and reason;
   preserve failed controls, negative responses and missingness. No silent
   outlier removal, unit conversion or technical-to-biological promotion.
3. **03-fit:** use the declared constrained monotone four-parameter logistic
   model and deterministic bounded reference routine. Record convergence,
   boundary hits, loss, iterations, parameters and exact frozen input hashes.
   Refuse reported potency outside tested concentrations, failed controls or
   nonconverged/boundary fits. An upper plateau not reached precludes full assay
   response. Changes after seeing results require an exploratory label and
   retained original declaration; unsupported models still stop.
4. **04-uncertainty:** resample whole biological curves with the frozen seed;
   first average technical wells within each biological dose. Record 95%
   percentile intervals for potency and Hill slope, and successful resample
   counts. Refuse degenerate data or insufficient converged resamples. Withhold
   intervals when potency is unavailable; never imply biological replication
   from technical wells. Compound ordering requires strictly disjoint intervals.
5. **05-review-handoff:** validate all immutable identities, claim boundaries
   and handoff coverage. Register domain records as ordinary artifacts through
   `$science-provenance`, with separate entries in the existing claim-register.
   Send the decision contract, original and exploratory records, exclusions,
   failures, code/environment provenance, intervals and claim dependencies to
   `$science-review`. Only the coordinator classifies rigor and obtains an
   independent reviewer. This pack returns `ready-for-independent-review`,
   never reviewed. A review approval is not truth.

Use one checkpoint per run and the ordered stage IDs in the existing manifest
plan shape. Complete stages with the existing package/checkpoint tools; do not
add manifest, receipt or MCP fields. Pin Python and code revision in execution
provenance. Start with the checked-in synthetic smoke fixture. Retries are
limited to one identical deterministic rerun after correcting a documented input
error; a different method is an exploratory revision, not a retry.

## Outputs

Return normalized inputs, assumptions, dependencies, conflicts, exclusions,
negative/failed/unavailable outcomes, rejected alternatives, limitations and the
smallest falsifiable next action. Register the local assay, plate, QC, fit,
uncertainty, claims and handoff schemas named in [records](references/records.md)
as ordinary artifacts, preserving their path-plus-hash identities. Keep supported,
conflicting, unsupported and unavailable claim IDs explicit in the separate
claim-register. The local claims artifact supplements that register.

`python3 scripts/validate_dose_response_pack.py examples/workflow-dose-response-curve/synthetic.pack.json`
prints a `dose-response-validation-v1` handoff check and writes nothing. Supplied
offline plates may declare `fixture: false`; that label does not authenticate
an experiment. The
reference fitter cannot prove real pharmacology, independent replication,
preregistration timing or an independent review. Checked-in inputs and expected
artifacts are redistributable synthetic fixtures, not experimental observations.

## Boundaries

Stop on an ambiguous identity, conversion, independent unit, materially changed
endpoint or unsupported model. Ask only for interpretation-changing choices,
installation, restricted transfers, new hosts, GPU/remote/heavy compute, or other
new authority; routine offline stages do not require separate approval. This
pack performs no network, download, install, remote or GPU action.

Refuse positive binding, affinity, inhibition, activation, causal, mechanism,
therapeutic, clinical efficacy, safety or prescribing claims from in-vitro
potency, regardless of a claim's declared kind. Positive
claims cannot cite computed or review-approval records as measured support.
Externally labelled evidence must differ from this run's outputs in both path
and hash; labels never establish independence. Preserve failed controls and
negative results. Empty support requires unavailable status, including for
unsupported, conflicting or withdrawn claims. Association is
never causality; review approval is never scientific truth. Independent review
and real assay qualification remain mandatory before a material conclusion.
