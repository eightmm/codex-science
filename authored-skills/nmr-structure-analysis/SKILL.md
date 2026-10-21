---
name: nmr-structure-analysis
description: "Process, assign, and verify molecular NMR evidence. Use for 1D or 2D solution NMR, FID processing, chemical shifts, multiplicities, couplings, integrations, COSY, HSQC, HMBC, NOE or ROE evidence, mixture assessment, and molecular structure or stereochemical analysis."
license: MIT
---

# NMR Structure Analysis

## Decision contract
Act as an analyzer. Define sample, formula/charge and exchangeable-site assumptions, solution state, structural question, evidence cutoff, and permitted level (assignment, connectivity, regio-, relative stereo, absolute stereo). Prespecify what evidence would distinguish candidates, integration/assignment uncertainty, and a falsifier. Ask when missing sample or acquisition information could alter assignments.

## Workflow
1. Record sample, solvent, concentration, temperature, field strength, nucleus, probe, pulse sequence, acquisition parameters, scans, relaxation delay, reference compound/convention, processing software/version, and raw FID versus processed input. Preserve vendor data and parameters; export nmrML or another documented interchange form when practical.
2. Correct digital-filter/group-delay effects before interpreting early points. Declare apodization, zero filling, Fourier convention, phase correction, baseline method, and chemical-shift reference. Compare with minimally processed data; do not erase weak peaks or create resolution by smoothing. Flag solvent/water, sidebands, truncation, folding, radiation damping, exchange, and concentration artifacts. Use `$cx-complex-fourier-analysis` for transform diagnostics and `$cx-experimental-uncertainty-propagation` for quantitative NMR/calibration/integration uncertainty. Use an approved isolated environment for `nmrglue`; do not install it silently.
3. Start from formula, charge, exchangeable sites, and unsaturation when known. Build an atom-to-signal table with shift, integral, multiplicity, coupling, confidence, and competing assignments. Use COSY for coupled networks, HSQC for direct heteronuclear pairs, HMBC for longer-range constraints, and NOE/ROE for proximity only under a declared mixing and motion regime. Treat calculated shifts, database matches, and `$kdense-rowan` predictions as comparisons, not experimental proof.
4. Reconcile proton/carbon counts, symmetry, integrations, couplings, and every claimed 2D correlation. Test alternative referencing, phase, baseline, overlap, exchange, and impurity explanations. Require an independent diagnostic signal/experiment for uniqueness if plausible isomers remain; record absent or ambiguous expected signals without treating non-observation as definitive absence.

## Outputs
Save a processing record, atom-to-signal assignment table, evidence graph, candidate structure identifiers, unresolved overlaps, and per-claim status (`supported`, `contradicted`, `inconclusive`, `unavailable`). Include normalized inputs, dependencies, uncertainty, limitations, smallest experiment separating candidates, raw-data/artifact paths and hashes via `$science-provenance`. Run `$science-review` before a material structural assignment.

## Boundaries
Achiral NMR alone does not establish chirality or absolute stereochemistry. Predicted shifts and database matches are not experimental evidence. Overlap, exchange, impurity, truncation, referencing, and processing ambiguity limit claims; do not silently repair or omit peaks. Stop if essential raw/acquisition data or sample state is unavailable, and retain unresolved assignments as inconclusive. Preserve failed and null observations.

## Source basis
Original workflow informed by the nmrML standard and open NMR processing practice recorded in `../../docs/ANALYTICAL_SOURCES.md`.
