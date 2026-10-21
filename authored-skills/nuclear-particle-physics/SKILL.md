---
name: nuclear-particle-physics
description: "Formulate and verify nuclear and particle physics calculations. Use for reactions, decays, relativistic kinematics, conservation laws, cross sections, lifetimes, quantum numbers, detector yields, backgrounds, and statistical significance."
license: MIT
---

# Nuclear and Particle Physics

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Workflow

1. Normalize inputs, conventions, units, domain, and assumptions; select a method whose assumptions match the stated regime. Retain the domain procedure below, including its method-selection, solution, and verification checks.

**Define the process**

Write the initial and final states, reference frame, four-momenta, masses, charges, quantum numbers, polarization,
units, detector acceptance, and target observable. Distinguish bound-state, decay, scattering, production,
detector, and statistical models. Use current evaluated constants and cite their provenance when precision matters.

**Analyze**

- Apply exact four-momentum conservation and invariant masses before frame-specific algebra.
- Check electric charge, baryon and lepton numbers, angular momentum, parity, and other applicable selection rules.
- Separate matrix element, phase space, flux, branching fraction, luminosity, efficiency, and acceptance.
- For unstable states, state width, lifetime, line-shape, interference, and narrow-width assumptions.
- Model backgrounds and detector resolution before converting theoretical rates to expected counts.

**Verify**

- Check thresholds, allowed phase space, invariant relations, units, and symmetry factors.
- Recompute in a second frame or with an independent invariant construction.
- Confirm cross-section or decay-rate normalization and integrate differential quantities over their stated domain.
- Propagate luminosity, efficiency, calibration, and background uncertainty with correlations.
- Report local and global significance separately; do not describe an excess as discovery without the field's criteria.

**Deliver**

Report process, conventions, conservation audit, kinematics, dynamical assumptions, predicted observable,
uncertainty, detector model, statistical interpretation, and validity limits.

## Outputs

Return a concise summary and machine-readable evidence table with normalized inputs and assumptions; claim IDs and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); method/equations or computational settings; results with units and uncertainty; checks and their outcomes; limitations and applicability domain; rejected alternatives and reasons; and the smallest falsifiable next action. Preserve null, failed, and unavailable results distinctly. Record artifact paths and hashes with `$science-provenance`; `$science-review` is mandatory before presenting material conclusions.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Crowell's openly licensed *Modern Physics* and NIST uncertainty guidance;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
