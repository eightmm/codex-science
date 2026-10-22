---
name: computational-physics-validation
description: "Verify computational physics software, quantify numerical uncertainty, and validate models against experiments. Use for convergence studies, manufactured solutions, conservation audits, code-to-code comparisons, calibration, uncertainty quantification, and simulation credibility."
license: MIT
---

# Computational Physics Validation

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [verification-validation-protocol.md](references/verification-validation-protocol.md) before designing a verification or validation study, claiming observed order, extrapolating a solution, comparing with experiment, or combining uncertainty sources. It defines the claim lanes, manufactured-solution procedure, convergence criteria, controls, sensitivity checks, and validity limits.

## Workflow

1. [step-1] Normalize inputs, conventions, units, domain, and assumptions, then define the quantity of interest, governing equations, initial and boundary conditions, acceptance threshold, and failure consequences; stop if a material condition is missing, select a method matching the regime, and record the normalized problem contract.
2. [step-2] Separate code verification (correct implementation), solution verification (numerical error for this run), validation (agreement with experiment for intended use), and uncertainty quantification; assign distinct claim IDs and falsifiers, and record each lane's required evidence.
3. [step-3] Verify code with analytic limits, unit and conservation tests, and a method of manufactured solutions (MMS) where feasible; check that the manufactured forcing and boundary data are derived consistently, and record the exact solution, source terms, and observed errors.
4. [step-4] Refine spatial grid, time step, solver tolerance, precision, and stochastic sample count independently; estimate observed order only within a supported asymptotic regime and use Richardson extrapolation only with an appropriate refinement sequence and error model, recording all levels and assumptions.
5. [step-5] Check conservation, symmetries, positivity, stability restrictions, dimensional consistency, boundary conditions, and residuals; investigate any failed invariant or residual before accepting a result, and record norms, scales, thresholds, and outcomes.
6. [step-6] Compare an independent implementation, formulation, or analytic reference with shared code, data, libraries, and assumptions disclosed; do not count dependent agreement as replication, and record dependency links and discrepancies.
7. [step-7] Calibrate only designated parameters on calibration evidence, then compare prediction residual patterns and quantities of interest with separate measurements and their uncertainties, not point values alone; record measurement provenance and validated conditions.
8. [step-8] Vary important inputs, mesh, time step, solver controls, model form, calibration choices, and sampling seeds; classify conclusions as fragile when a plausible variation crosses the decision threshold, and record the sensitivity analysis and dominant uncertainties.
9. [step-9] Report the validated domain and extrapolation limits, preserve null, failed, and inconclusive findings, and use `$science-provenance` followed by `$science-review` before material conclusions; record the smallest discriminating next test.

## Outputs

Return a concise summary and a machine-readable `computational-validation-v1` record with required fields: `problem_contract`, `normalized_inputs`, `assumptions`, `claim_id`, `claim_type`, `status` (`supported`, `contradicted`, `inconclusive`, or `unavailable`), `verification_lane`, `method`, `code_revision`, `inputs`, `environment`, `seeds`, `raw_outputs`, `post_processing`, `controls`, `checks_and_outcomes`, `refinement_series`, `observed_order`, `extrapolation`, `results`, `units`, `uncertainty`, `dependencies`, `experimental_comparison`, `sensitivity`, `credibility_matrix`, `pass_fail_criteria`, `unresolved_discrepancies`, `rejected_alternatives`, `applicability_domain`, `limitations`, `next_action`, and `artifacts` (paths and hashes). Preserve implementation, numerical, input, experimental, and model-form evidence separately. Preserve null, failed, and unavailable results distinctly; `$science-provenance` is required and `$science-review` is mandatory before material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result. Agreement with one experiment does not establish implementation correctness; grid convergence does not establish physical validity; observed order over a finite range does not prove asymptotic convergence.

## Source basis

Original synthesis informed by NASA verification, validation, and uncertainty-quantification guidance and open
numerical-analysis sources recorded in `../../docs/TEXTBOOK_SOURCES.md`.
