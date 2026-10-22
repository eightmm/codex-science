---
name: relativity-spacetime
description: "Formulate and verify special- and general-relativity problems. Use for Lorentz transformations, four-vectors, relativistic kinematics, metrics, geodesics, curvature, gravitational fields, horizons, and stress-energy dynamics."
license: MIT
---

# Relativity and Spacetime

## Decision contract

State the physical system, requested quantity or decision, relevant state and boundary/initial conditions, permitted approximation and inference, and evidence cutoff. Record assumptions that materially affect method choice, acceptance checks, or interpretation; use explicit safe defaults for nonblocking choices. Assign stable claim IDs to material conclusions and state what observation or check would falsify each claim.

## Reference usage

Read [relativistic-evidence.md](references/relativistic-evidence.md) before classifying an interval, interpreting an observable, deriving curvature or motion, applying a weak-field/post-Newtonian approximation, or making a relativistic claim. It defines claim classes, convention controls, source dependence, uncertainty, sensitivity, and applicability limits.

## Workflow

1. **Check scope:** identify the requested result and whether events, observers, boundary/initial conditions, physical regime, and evidence are sufficiently specified; if essential choices are unresolved, stop or report them. Record missing inputs and safe defaults.
2. **Fix conventions:** define coordinates, observers, units for `c` and `G`, metric signature, index placement, orientation, curvature convention, and the meaning of each requested observable. Separate coordinate quantities from locally measured quantities. Record each convention.
3. **Classify causal character:** compute the invariant interval or norm and classify the path or vector as timelike, null, or spacelike before manipulating velocities, trajectories, or causal claims. For a purely Riemannian manifold with no spacetime interpretation, mark causal and `c`, `G` conventions not applicable and use `$cx-tensor-calculus-differential-geometry` as the primary workflow. Record the invariant and classification.
4. **Select the model:** for special relativity use Lorentz transformations, invariant intervals, four-velocity, and four-momentum; for collisions/decays conserve four-momentum and use invariant masses before selecting a frame. For general relativity state the metric and symmetries, derive connection/geodesic/curvature as needed, and declare stress-energy and field-equation conventions. Use weak-field, slow-motion, or post-Newtonian methods only after justifying dimensionless limits and required order. Record model and rationale.
5. **Classify the claim:** label each material result exact, controlled approximation (small parameter and error order), numerical (with convergence evidence), or heuristic estimate. Check that derivation and evidence support the label; assign claim IDs, status, uncertainty, and a falsifier.
6. **Run invariant checks:** verify dimensions, signs, contractions, tensor transformation, four-vector norms, metric compatibility, geodesic normalization, and conserved quantities from Killing symmetries where applicable. Recover Newtonian or special-relativistic limits and distinguish coordinate singularities from curvature singularities with invariants or regular coordinates. Record expected and observed checks.
7. **Stress-test and deliver:** compare symbolic results numerically at nonsingular points, vary conventions, coordinates, initial/boundary conditions, model parameters, and approximation order where consequential; flag changes that exceed the error order or alter causal/result classification. Record domains excluded by coordinates or assumptions, preserve failed/inconclusive results, record paths and hashes with `$science-provenance`, and use `$science-review` before presenting material conclusions.

## Outputs

Return `relativistic-evidence-v1` with: system, events, observers, and normalized inputs; boundary/initial conditions and assumptions; metric, units, signature, index and curvature conventions; invariant causal classification; claim identifiers and status (`supported`, `contradicted`, `inconclusive`, or `unavailable`); claim class and falsifier; equations or computational settings and approximation order; locally measured and coordinate results distinguished, with units and uncertainty; source/dependency records; checks and outcomes; sensitivity results; applicability limits; rejected alternatives and reasons; smallest falsifiable next action; artifact paths and hashes; provenance and independent review receipts. Preserve null, failed, and unavailable results distinctly.

## Boundaries

Stop when essential inputs, boundary conditions, or regime cannot be determined safely, or when an approximation is used outside its declared domain. Do not equate mathematical consistency, solver convergence, or process success with empirical validation. Keep unresolved discrepancies and numerical/model uncertainty explicit; do not silently repair inputs or promote an inconclusive result.

## Source basis

Original synthesis informed by Crowell's openly licensed *General Relativity* and *Modern Physics*; source
details are in `../../docs/TEXTBOOK_SOURCES.md`.
