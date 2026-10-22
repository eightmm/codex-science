---
name: tensor-calculus-differential-geometry
description: "Compute and verify tensor-calculus and differential-geometry results. Use for coordinate transformations, metrics, differential forms, covariant derivatives, connections, geodesics, curvature, Lie derivatives, and coordinate-independent geometric identities."
license: MIT
---

# Tensor Calculus and Differential Geometry

## Decision contract

State the manifold, dimension, chart or frame, coordinate domain, tensor types, metric signature, index placement, orientation, units, and connection and curvature conventions before computing. Separate a component calculation from a coordinate-independent geometric claim, and state regularity assumptions. A chart singularity is not a physical singularity unless invariant or extendibility evidence supports that conclusion.

## Reference usage

Read [tensor-geometry-conventions.md](references/tensor-geometry-conventions.md) before computing covariant derivatives, Christoffel symbols, curvature, geodesics, or singularity claims. It defines convention checks, invariant controls, claim classes, and symbolic validation limits.

Preserve inputs, conventions, derivations or commands, environment, artifacts, hashes, failures, and null results with `$science-provenance`; use `$science-review` before material or consequential scientific conclusions.

## Workflow

1. **Declare geometry and conventions.** Record manifold, dimension, chart/frame and domain, metric signature, index range, summation rule (index convention and summed-index range), raising/lowering rules, orientation, units, connection, and Riemann sign convention; if these are unresolved, stop convention-dependent claims.
2. **Identify the geometric object.** State its tensor type and coordinate-free meaning before expanding components; choose coordinate or orthonormal frame calculations according to the transformation law required; use exterior derivatives and forms when they clarify antisymmetry, orientation, or integral structure.
3. **Compute metric and connection data.** Derive inverse metric, determinant/volume form, and Christoffel symbols; verify metric compatibility and lower-index symmetry when the connection is Levi-Civita and torsion-free.
4. **Differentiate and contract consistently.** Record partial versus covariant derivatives, index positions at each contraction, and the declared Riemann-to-Ricci convention before simplifying components.
5. **Check identities and transformations.** Verify free/dummy indices, dimensions, symmetries, torsion assumptions, Bianchi identities, geodesic normalization, and transformation to a second regular chart or frame as applicable.
6. **Test controls.** Recover the Euclidean or flat-space limit and expected vanishing curvature invariants; independently recompute selected expressions with a second derivation or symbolic route and compare invariant contractions.
7. **Assess singularity claims.** At a coordinate boundary, test whether the chart degenerates; evaluate suitable curvature invariants and investigate extension or geodesic behavior before classifying a physical singularity.
8. **Probe sensitivity and report.** Recompute under an explicitly converted alternate signature or curvature convention where useful, vary regular sample points and symbolic simplifications, and record disagreements, uncertainty, limitations, claim status, and next action.

## Outputs

Return one `tensor-geometry-evidence-v1` record with: geometric problem (`manifold`, `chart_domain`); conventions (`metric_signature`, `index_convention`, `curvature_convention`, `orientation`); claim class (`claim_class`: component computation, tensor identity, curvature or invariant result, singularity classification, or symbolically checked result); claim identifier and status (`claim_id`, `claim_status`: supported, contradicted, inconclusive, or unavailable); tensor type and result (`object_type`, `coordinate_result`, `geometric_interpretation`); derivation and checks (`derivation`, `identity_checks`, `transformation_checks`, `symbolic_checks`); singularity assessment (`singularity_assessment`); uncertainty and limitations (`uncertainty`, `limitations`); provenance and artifact identities (`provenance`, `artifact_paths`, `artifact_hashes`); failures and nulls (`failures`, `null_results`); and next action (`next_action`). Preserve derivations and execution details through `$science-provenance`; use `$science-review` for material claims.

## Boundaries

Christoffel symbols depend on coordinates and are not tensor components. Partial derivatives of tensor components are not generally covariant derivatives. A result for one coordinate component does not establish a tensor identity. Stop coordinate-dependent conclusions at chart singularities; a divergent component alone does not establish physical curvature or geodesic singularity. Retain conflicting conventions and failed symbolic checks rather than silently changing signs.

## Source basis

Original synthesis informed by Sochi's openly licensed tensor-calculus text and Crowell's relativity text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
