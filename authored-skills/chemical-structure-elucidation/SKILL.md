---
name: chemical-structure-elucidation
description: "Integrate molecular formula, NMR, MS, IR, Raman, UV-Vis, chromatography, and diffraction evidence into ranked chemical structures with explicit contradictions and confidence. Use for unknown identification, structure confirmation, isomer discrimination, impurity analysis, and planning the smallest discriminating analytical experiment."
license: MIT
---

# Chemical Structure Elucidation

## Establish identity boundaries

Record sample source, isolation, purity, mixture evidence, salt and solvate state, formula and charge evidence, stereochemical
scope, and every raw dataset with acquisition conditions. Standardize candidate structures without discarding isotopes,
stereochemistry, formal charge, tautomer, or component identity. Use `$cx-molecular-input-preparation` when candidates
must be converted between molecular formats.

## Compose at most two modality workflows

Use this conductor with the two most discriminating available modality skills:

- `$cx-nmr-structure-analysis` for connectivity and stereochemical constraints.
- `$cx-mass-spectrometry-identification` for formula, isotope, fragment, and library evidence.
- `$cx-spectroscopy-spectral-inference` for IR, Raman, UV-Vis, or fluorescence evidence.
- `$cx-xray-diffraction-scattering` for crystalline phase or structure evidence.
- `$cx-chromatography-quantification` for mixture separation, purity, and retention evidence.

Use `$cx-experimental-uncertainty-propagation` for all quantitative comparisons.

## Build and test candidates

1. Create an evidence matrix with each observation, uncertainty, preprocessing, candidate prediction, support, contradiction,
   and whether the evidence is independent.
2. Generate formula and unsaturation constraints before database search; keep constitutional, regio-, stereo-, tautomeric,
   salt, solvate, and mixture alternatives distinct.
3. Rank candidates by total evidence, penalizing unexplained strong signals and impossible absences more than weak similarities.
4. Separate evidence used to retrieve or generate candidates from evidence reserved to test them.
5. Never treat a database or predicted-spectrum match as confirmation of a structure already used to select the candidate.

## Verify

- Reconcile atom counts, charge, isotope pattern, NMR integrals and correlations, functional groups, fragments, and purity.
- Search explicitly for one plausible alternative and identify the observation that rules it out—or state that none does.
- Check whether matrix, phase, solvent, temperature, ionization, concentration, and instrument differences explain mismatches.
- Label conclusions as formula-level, class-level, connectivity-level, relative-stereo, or absolute-structure evidence.
- If candidates remain, propose the smallest feasible experiment with distinct predicted outcomes before claiming uniqueness.

## Deliver

Report ranked structures, machine-readable identifiers, evidence matrix, contradictions, confidence by structural level,
unresolved mixture or isomer issues, source/library snapshots, and the next discriminating experiment. Say “not uniquely
identified” when the evidence does not isolate one structure.

## Source basis

Original workflow synthesizing the modality standards, NIST reference-data practice, and overlap audit in
`../../docs/ANALYTICAL_SOURCES.md`.
