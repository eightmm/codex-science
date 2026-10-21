---
name: chemical-structure-elucidation
description: "Integrate molecular formula, NMR, MS, IR, Raman, UV-Vis, chromatography, and diffraction evidence into ranked chemical structures with explicit contradictions and confidence. Use for unknown identification, structure confirmation, isomer discrimination, impurity analysis, and planning the smallest discriminating analytical experiment."
license: MIT
---

# Chemical Structure Elucidation

## Decision contract
Act as a conductor: combine at most two modality workflows at a time, then reconcile their evidence centrally. Define the identity question, sample and mixture state, evidence cutoff, formula/charge and stereochemical scope, and intended claim level (formula, class, connectivity, relative stereo, absolute structure). Keep constitutional, regio-, stereo-, tautomeric, salt, solvate, and mixture alternatives distinct. Set the evidence threshold and falsifier before ranking; ask only if a missing sample or claim choice changes interpretation.

## Workflow
1. Preserve sample source, isolation, purity, raw data, acquisition conditions, and checksums. Standardize candidate structures without dropping isotope, stereochemistry, formal charge, tautomer, or component identity. Use `$cx-molecular-input-preparation` when converting molecular formats.
2. Generate formula and unsaturation constraints before searching. Choose the two most discriminating workflows: `$cx-nmr-structure-analysis` for connectivity/stereochemistry; `$cx-mass-spectrometry-identification` for formula/isotope/fragments/library evidence; `$cx-spectroscopy-spectral-inference` for IR/Raman/UV-Vis/fluorescence; `$cx-xray-diffraction-scattering` for crystalline evidence; `$cx-chromatography-quantification` for mixture/purity/retention. Use `$cx-experimental-uncertainty-propagation` for quantitative comparisons.
3. Create stable claim IDs and an evidence matrix: observation, raw-data reference, method/preprocessing, units and uncertainty, predicted candidate outcome, support or contradiction, and dependence group. Separate evidence used to generate candidates from evidence reserved to test them. Track included and excluded signals with reasons; do not count correlated measurements as independent.
4. Verify by reconciling atom counts, charge, isotope pattern, NMR integrals/correlations, functional groups, fragments, diffraction, and purity. Examine matrix, phase, solvent, temperature, ionization, concentration, and instrument mismatches. Test at least one plausible alternative and state the observation that distinguishes it, or that none does. Report failed, null, missing, and ambiguous measurements separately. Rank with transparent rules and sensitivity; do not silently repair inputs.

## Outputs
Save a machine-readable claim register and evidence table with normalized structures/identifiers, claim type and status (`supported`, `contradicted`, `inconclusive`, `unavailable`), evidence links, dependencies, uncertainty, inclusion/exclusion rationale, rejected alternatives, and applicability limits. Include ranked structures, source/library snapshots, unresolved mixture/isomer questions, the smallest falsifiable next experiment, and artifact paths and hashes via `$science-provenance`. Preserve the raw inputs and processing records. Run `$science-review` before presenting any material identification or structural claim.

## Boundaries
Never treat a database or predicted-spectrum match as confirmation when it selected the candidate. State “not uniquely identified” when evidence does not isolate one structure. A missing signal is not definitive absence; MS generally cannot distinguish isomers without discriminating evidence; achiral NMR alone does not establish chirality. Stop if sample identity, essential raw data, or an interpretation-changing state is unavailable; retain the conclusion as inconclusive if candidates remain. Do not claim purity from area percent alone or infer absolute structure from an unsupported modality.

## Source basis
Original workflow synthesizing the modality standards, NIST reference-data practice, and overlap audit in `../../docs/ANALYTICAL_SOURCES.md`.
