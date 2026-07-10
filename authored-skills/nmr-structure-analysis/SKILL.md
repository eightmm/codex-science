---
name: nmr-structure-analysis
description: "Process, assign, and verify molecular NMR evidence. Use for 1D or 2D solution NMR, FID processing, chemical shifts, multiplicities, couplings, integrations, COSY, HSQC, HMBC, NOE or ROE evidence, mixture assessment, and molecular structure or stereochemical analysis."
license: MIT
---

# NMR Structure Analysis

## Define the experiment

Record sample, solvent, concentration, temperature, field strength, nucleus, probe, pulse sequence, acquisition
parameters, scans, relaxation delay, reference compound and convention, processing software/version, and whether
the input is raw FID or processed data. Preserve vendor data and acquisition parameters; export nmrML or another
documented interchange form when practical.

## Process the signal

1. Correct digital-filter and group-delay effects before interpreting early points.
2. Declare apodization, zero filling, Fourier convention, phase correction, baseline method, and chemical-shift reference.
3. Compare processed results with a minimally processed spectrum; do not erase weak peaks or create resolution by smoothing.
4. Flag solvent, water, spinning sidebands, truncation, folding, radiation damping, exchange, and concentration artifacts.

Use `$cx-complex-fourier-analysis` for transform diagnostics and `$cx-experimental-uncertainty-propagation` for
quantitative NMR, calibration, and integration uncertainty. Use an approved isolated environment for `nmrglue`;
do not install it silently.

## Assign structure evidence

- Start from formula, charge, exchangeable sites, and degree of unsaturation when known.
- Build an atom-to-signal table with shift, integral, multiplicity, coupling, confidence, and competing assignments.
- Use COSY for coupled networks, HSQC for direct heteronuclear pairs, HMBC for longer-range constraints, and NOE/ROE
  for proximity only under a declared mixing and motion regime.
- Treat calculated shifts, database matches, and `$kdense-rowan` predictions as supporting comparisons, not experimental proof.

## Verify

- Reconcile proton and carbon counts, symmetry, integrations, couplings, and every claimed 2D correlation.
- Check assignments under alternative referencing, phase, baseline, overlap, exchange, and impurity explanations.
- Distinguish constitutional, regio-, relative-stereo-, and absolute-stereo evidence; do not infer chirality from achiral NMR alone.
- Require an independent diagnostic signal or experiment for a unique assignment when plausible isomers remain.
- Report absent or ambiguous expected signals without treating non-observation as definitive absence.

## Deliver

Provide the processing log, assignment table, evidence graph, unresolved overlaps, candidate structures, confidence by
claim, and the next experiment that best separates remaining candidates.

## Source basis

Original workflow informed by the nmrML standard and open NMR processing practice recorded in
`../../docs/ANALYTICAL_SOURCES.md`.
