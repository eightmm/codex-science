---
name: tensor-calculus-differential-geometry
description: "Compute and verify tensor-calculus and differential-geometry results. Use for coordinate transformations, metrics, differential forms, covariant derivatives, connections, geodesics, curvature, Lie derivatives, and coordinate-independent geometric identities."
license: MIT
---

# Tensor Calculus and Differential Geometry

## Decision contract
State manifold, coordinates or frame, tensor types, metric, orientation, index conventions, and curvature conventions. Distinguish coordinate components from geometric objects and state the regularity/domain of each chart.

## Workflow
1. **Declare conventions.**
   State the manifold, dimension, coordinates and domains, basis or frame, tensor type, metric and signature,
   orientation, index range, summation rule, connection, curvature sign, and units. Distinguish a tensor from its
   components and a coordinate basis from an orthonormal frame.

2. **Compute geometrically.**
   1. Identify the coordinate-free object and transformation law before expanding indices.
   2. Derive inverse metric, volume form, connection coefficients, and covariant derivatives consistently.
   3. Use exterior derivatives and forms when they expose antisymmetry, orientation, or integral structure.
   4. Build curvature from the declared convention and contract only after checking index positions.
   5. Separate connection coefficients, which are coordinate dependent, from torsion and curvature tensors.

3. **Verify.**
   - Check free-index types, dummy-index pairing, symmetry, antisymmetry, and dimensions at every line.
   - Transform components to another chart or frame and confirm invariant contractions agree.
   - Verify metric compatibility, torsion assumptions, Bianchi identities, and geodesic normalization as applicable.
   - Recover flat-space or Euclidean results and confirm curvature invariants vanish when expected.
   - Cross-check symbolic output at regular sample points; do not infer tensor equality from one coordinate component.

4. **Deliver.**
   Report conventions, geometric objects, component derivation, transformation or invariant checks, singular chart
   regions, and the final coordinate-independent interpretation.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
Do not identify a tensor from one coordinate component or confuse connection coefficients with tensors. Stop coordinate-dependent conclusions at chart singularities or when index/curvature conventions are unresolved.

## Source basis

Original synthesis informed by Sochi's openly licensed tensor-calculus text and Crowell's relativity text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
