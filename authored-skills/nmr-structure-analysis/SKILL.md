---
name: nmr-structure-analysis
description: "Process, assign, and verify molecular NMR evidence. Use for 1D or 2D solution NMR, FID processing, chemical shifts, multiplicities, couplings, integrations, COSY, HSQC, HMBC, NOE or ROE evidence, mixture assessment, and molecular structure or stereochemical analysis."
license: MIT
---

# NMR Structure Analysis

## Decision contract
Act as an analyzer. Define sample, formula/charge and exchangeable-site assumptions, solution state, structural question, evidence cutoff, and permitted level (assignment, connectivity, regio-, relative stereo, absolute stereo). Prespecify what evidence would distinguish candidates, integration/assignment uncertainty, and a falsifier. Ask when missing sample or acquisition information could alter assignments.

## Reference usage
Read [nmr-evidence-interpretation.md](references/nmr-evidence-interpretation.md) before the workflow steps Process conservatively (process-conservatively), Build candidates (build-candidates), Test correlations (test-correlations), Challenge assignments (challenge-assignments), and Verify and downgrade (verify-and-downgrade). These IDs name the numbered actions below; use the reference criteria for processing, assignment confidence, 2D correlations, stereochemistry, and overlap/exchange.

## Workflow
1. **Check gates.** If essential raw FID, sample state, or acquisition context is absent, stop and ask for the missing information before interpreting; if it cannot be supplied, classify the affected claim as unavailable/inconclusive. Ask before installing nmrglue or changing the approved environment. Use an approved isolated environment for nmrglue; do not install it silently. Record gate decision and missing items.
2. **Freeze provenance.** Capture sample, solvent, concentration, temperature, field strength, nucleus, probe, pulse sequence, acquisition parameters, scans, relaxation delay, reference compound/convention, software/version and whether input is raw FID or processed; preserve vendor data and export nmrML where practical. Record hashes and conversion.
3. **Process conservatively.** Correct digital-filter/group-delay effects; declare apodization, zero filling, Fourier convention, phase, baseline and shift reference. Compare minimally processed data; do not erase weak peaks or create resolution by smoothing. Flag solvent/water, sidebands, truncation, folding, radiation damping, exchange and concentration artifacts. Record alternatives and use `$cx-complex-fourier-analysis` for transform diagnostics and `$cx-experimental-uncertainty-propagation` for quantitative NMR, calibration, and integration uncertainty.
4. **Build candidates.** Apply formula, charge, exchangeable-site and unsaturation constraints where known; keep candidate provenance separate from validation evidence. Record atom/signal assignments with shift, integral, multiplicity, coupling, confidence and alternatives.
5. **Test correlations.** Use COSY for coupling, HSQC for direct pairs, HMBC for longer-range constraints and NOE/ROE only under declared mixing/motion regimes. Treat calculated shifts, database matches and `$kdense-rowan` predictions as comparisons, not experimental proof. Record each observation, expected candidate outcome and dependence group.
6. **Challenge assignments.** Reconcile counts, symmetry, integrations, couplings and each claimed 2D cross-peak; test alternative reference, phase, baseline, overlap, exchange and impurity explanations. Require an independent diagnostic signal/experiment for uniqueness if plausible isomers remain; record absent/ambiguous expected signals without treating non-observation as definitive absence.
7. **Verify and downgrade.** Check the assignment table against raw data and rerun the reference checks for the selected claim class. If the claim depends on an ambiguous peak, altered processing, or non-independent evidence, downgrade to inconclusive and record the failed criterion.
8. **Report and hand off.** Report claim status, uncertainty, unresolved overlap, smallest separating experiment, limitations and raw artifact paths/hashes; preserve failed/null observations with `$science-provenance`, then run `$science-review` before a material structural assignment.

## Outputs
`nmr-assignment-evidence-v1` required fields: sample_and_acquisition; processing_record; atom_to_signal_assignments; candidate_ids; claim_register with statuses (`supported`, `contradicted`, `inconclusive`, `unavailable`); confidence_by_claim_level; evidence_links; dependency_groups; uncertainty; unresolved_or_excluded_signals; applicability_limits; next_discriminating_experiment; artifact_paths_and_hashes; provenance_receipt; review_receipt.

## Boundaries
Achiral NMR alone does not establish chirality or absolute stereochemistry. Predicted shifts and database matches are not experimental evidence. Overlap, exchange, impurity, truncation, referencing, and processing ambiguity limit claims; do not silently repair or omit peaks. Stop if essential raw/acquisition data or sample state is unavailable, and retain unresolved assignments as inconclusive. Preserve failed and null observations.

## Source basis
Original workflow informed by the nmrML standard and open NMR processing practice recorded in `../../docs/ANALYTICAL_SOURCES.md`.
