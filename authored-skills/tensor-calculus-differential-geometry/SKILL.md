---
name: tensor-calculus-differential-geometry
description: "Compute and verify tensor-calculus and differential-geometry results. Use for coordinate transformations, metrics, differential forms, covariant derivatives, connections, geodesics, curvature, Lie derivatives, and coordinate-independent geometric identities."
license: MIT
---

# Tensor Calculus and Differential Geometry

## Declare conventions

State the manifold, dimension, coordinates and domains, basis or frame, tensor type, metric and signature,
orientation, index range, summation rule, connection, curvature sign, and units. Distinguish a tensor from its
components and a coordinate basis from an orthonormal frame.

## Compute geometrically

1. Identify the coordinate-free object and transformation law before expanding indices.
2. Derive inverse metric, volume form, connection coefficients, and covariant derivatives consistently.
3. Use exterior derivatives and forms when they expose antisymmetry, orientation, or integral structure.
4. Build curvature from the declared convention and contract only after checking index positions.
5. Separate connection coefficients, which are coordinate dependent, from torsion and curvature tensors.

## Verify

- Check free-index types, dummy-index pairing, symmetry, antisymmetry, and dimensions at every line.
- Transform components to another chart or frame and confirm invariant contractions agree.
- Verify metric compatibility, torsion assumptions, Bianchi identities, and geodesic normalization as applicable.
- Recover flat-space or Euclidean results and confirm curvature invariants vanish when expected.
- Cross-check symbolic output at regular sample points; do not infer tensor equality from one coordinate component.

## Deliver

Report conventions, geometric objects, component derivation, transformation or invariant checks, singular chart
regions, and the final coordinate-independent interpretation.

## Source basis

Original synthesis informed by Sochi's openly licensed tensor-calculus text and Crowell's relativity text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
