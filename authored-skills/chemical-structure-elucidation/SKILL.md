---
name: chemical-structure-elucidation
description: "Integrate molecular formula, NMR, MS, IR, Raman, UV-Vis, chromatography, and diffraction evidence into ranked chemical structures with explicit contradictions and confidence. Use for unknown identification, structure confirmation, isomer discrimination, impurity analysis, and planning the smallest discriminating analytical experiment."
license: MIT
---

# Structure elucidation evidence reconciliation

## Decision contract
Act as a conductor: combine at most two modality workflows at a time, then reconcile their evidence centrally. Define the identity question, sample and mixture state, evidence cutoff, formula/charge and stereochemical scope, and intended claim level (formula, class, connectivity, relative stereo, absolute structure). Keep constitutional, regio-, stereo-, tautomeric, salt, solvate, and mixture alternatives distinct. Set the evidence threshold and falsifier before ranking; ask only if a missing sample or claim choice changes interpretation.

## Reference usage
Read [structure-elucidation-evidence.md](references/structure-elucidation-evidence.md) before the workflow steps Select modalities (select-modalities), Build evidence graph (build-evidence-graph), Verify and reconcile predictions (verify-and-reconcile-predictions), Challenge ranking (challenge-ranking), and Report and hand off (report-and-hand-off). These IDs name the numbered actions below; use the reference criteria for orthogonal evidence, rejected alternatives, mixture/isomer ambiguity, and claim limits.

## Workflow
1. **Check gates.** If sample identity, essential raw data or interpretation-changing state is unavailable, stop and ask for the missing premise before reconciliation; if it cannot be resolved, classify the affected conclusion as inconclusive/unavailable and retain alternatives.
2. **Preserve inputs.** Preserve sample source, isolation, purity, raw data, conditions and checksums. Standardize candidates without dropping isotope, stereochemistry, charge, tautomer or component identity; use `$cx-molecular-input-preparation` for molecular format conversion.
3. **Bound formula.** Generate formula and unsaturation constraints before searching. Record assumptions, compatible charge/adduct states and candidate-generation sources separately from validation evidence.
4. **Select modalities.** Choose the two most discriminating workflows when two are needed, combining no more than two at a time: `$cx-nmr-structure-analysis` for connectivity/stereochemistry; `$cx-mass-spectrometry-identification` for formula/isotope/fragments/library evidence; `$cx-spectroscopy-spectral-inference` for IR/Raman/UV-Vis/fluorescence; `$cx-xray-diffraction-scattering` for crystalline evidence; `$cx-chromatography-quantification` for mixture/purity/retention. Use `$cx-experimental-uncertainty-propagation` for quantitative comparisons. Record why selected.
5. **Build evidence graph.** Create stable claim IDs and evidence matrix: observation, raw reference, method/preprocessing, units and uncertainty, predicted candidate outcome, support/contradiction and dependence group. Separate candidate-generating from reserved test evidence; record excluded signals/reasons and shared sources.
6. **Verify and reconcile predictions.** Check atom counts, charge, isotope pattern, NMR integrals/correlations, functional groups, fragments, diffraction and purity. Examine matrix, phase, solvent, temperature, ionization, concentration and instrument mismatches. Record contradictions and missing/ambiguous data distinctly.
7. **Challenge ranking.** Test at least one plausible alternative and state the discriminating observation, or explicitly record that none distinguishes it. Rank by transparent rules and sensitivity; penalize unexplained strong signals and expected absences only when detectability is established, give weak similarities less weight, and vary uncertain assignments, thresholds, candidate set and correlated evidence handling. Downgrade when ranking changes materially.
8. **Report and hand off.** Preserve failed/null measurements and raw processing records. Report ranked structures, source/library snapshots, confidence by structural claim level, unresolved alternatives, applicability limits, and the smallest falsifiable experiment with distinct predicted outcomes; record artifact hashes via `$science-provenance` and run `$science-review` before material identification or structural claims.

## Outputs
`structure-elucidation-evidence-v1` required fields: sample_and_state; candidate_structures_and_identifiers; formula_constraints; modality_and_processing_records; source_library_snapshots; claim_register with statuses (`supported`, `contradicted`, `inconclusive`, `unavailable`); claim_levels_and_confidence; evidence_table; dependency_groups; uncertainty; included_and_excluded_evidence; rejected_alternatives; unresolved_mixture_isomer_questions; ranked_structures; sensitivity_results; applicability_limits; next_experiment; artifact_paths_and_hashes; provenance_receipt; review_receipt.

## Boundaries
Never treat a database or predicted-spectrum match as confirmation when it selected the candidate. State “not uniquely identified” when evidence does not isolate one structure. A missing signal is not definitive absence; MS generally cannot distinguish isomers without discriminating evidence; achiral NMR alone does not establish chirality. Stop if sample identity, essential raw data, or an interpretation-changing state is unavailable; retain the conclusion as inconclusive if candidates remain. Do not claim purity from area percent alone or infer absolute structure from an unsupported modality.

## Source basis
Original workflow synthesizing the modality standards, NIST reference-data practice, and overlap audit in `../../docs/ANALYTICAL_SOURCES.md`.
