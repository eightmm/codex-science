---
name: nuclear-particle-physics
description: "Formulate and verify nuclear and particle physics calculations. Use for reactions, decays, relativistic kinematics, conservation laws, cross sections, lifetimes, quantum numbers, detector yields, backgrounds, and statistical significance."
license: MIT
---

# Nuclear and Particle Physics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim. Use claim statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`.

## Reference usage

- Read [references/calculation-evidence.md](references/calculation-evidence.md) before a material reaction, decay, cross-section, significance, or approximation claim; it defines calculation classes, units/conventions, checks, uncertainty and failure limits.
- Read [../../docs/TEXTBOOK_SOURCES.md](../../docs/TEXTBOOK_SOURCES.md) when selecting an established text or source. It records what each consulted source covers; do not attribute nuclear cross-section or detector procedures to texts that do not cover them.
- Use current evaluated constants and cite their provenance when precision matters. Check the relevant primary dataset or current evaluation for the actual calculation rather than treating a textbook as a data source.

## Workflow

1. Normalize initial and final states, reference frame, four-momenta, masses, charges, quantum numbers, polarization, units, detector acceptance, and target observable. If essential inputs or conventions are missing, stop or use a labeled safe default; record normalized inputs and assumptions.
2. Classify the desired result as exact, controlled approximation, numerical, or heuristic. Select the method only when its assumptions match the declared regime; for ambiguous perturbative, non-perturbative, bound-state, decay, scattering, production, detector, or statistical regimes, stop and state the unresolved choice. Record the method class, equations, and validity conditions.
3. Apply exact four-momentum conservation and invariant masses before frame-specific algebra. Check electric charge, baryon and lepton numbers, angular momentum, parity, and other applicable selection rules; reject impossible processes or explain any stated violation. Record each applicable balance and result.
4. For decay and scattering observables, separate matrix element, phase space, flux, branching fraction, luminosity, efficiency, and acceptance. For unstable states state width, lifetime, line-shape, interference, and narrow-width assumptions; for detector yields model backgrounds and resolution before expected counts. Record normalization, integration domain, symmetry factors, units, and inputs.
5. **Verify.** Check thresholds, allowed phase space, invariant relations, units, and symmetry factors; recompute in a second frame or with an independent invariant construction. Propagate luminosity, efficiency, calibration, and background uncertainty with correlations. Use limiting cases and independent arithmetic/code checks where relevant; record tests, uncertainty, and discrepancies.
6. Report the predicted observable and units, uncertainty, detector/statistical interpretation, rejected alternatives and reasons, and applicability limits. Report local and global significance separately; do not describe an excess as discovery without the field's criteria. Preserve null, failed, and unavailable results distinctly, record artifacts and hashes with `$science-provenance`, and use `$science-review` before material conclusions.

## Outputs

Return `nuclear-physics-evidence-v1` with: normalized inputs and assumptions; claim identifier (`claim_id`) and claim status (`status`: `supported`, `contradicted`, `inconclusive`, or `unavailable`); method class and equations or computational settings; conventions and units; conservation audit; kinematics and dynamical assumptions; results with units and uncertainty; normalization, detector model, statistical interpretation, and applicability domain; checks and outcomes; rejected alternatives and reasons; artifact paths and hashes; and smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Crowell's openly licensed *Modern Physics* and NIST uncertainty guidance;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
