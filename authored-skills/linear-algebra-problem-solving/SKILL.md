---
name: linear-algebra-problem-solving
description: "Solve exact and numerical linear algebra problems with explicit field, dimensions, bases, rank structure, conditioning, and residual checks. Use for linear systems, vector spaces, linear maps, eigenproblems, least squares, SVD, quadratic forms, and matrix factorizations."
license: MIT
---

# Linear Algebra Problem Solving

## Decision contract
State the field, spaces, dimensions, bases, representation, and exact or floating-point goal. Distinguish structural conclusions from numerical estimates and identify conditioning that limits interpretation.

## Workflow
1. **Specify structure.**
   1. State the scalar field, vector spaces, dimensions, basis conventions, matrix orientation,
      inner product, and exact versus floating-point representation.
   2. Check every product and map for dimension compatibility before manipulating symbols.
   3. Distinguish a linear map from a matrix representation; record basis changes explicitly.

2. **Select the problem class.**
   - Linear system: determine rank, consistency, nullity, and solution-set dimension before solving.
   - Subspace/basis: prove closure, then independence and spanning; do not infer either from vector count alone.
   - Linear map: compute kernel and image and check rank-nullity.
   - Least squares: use orthogonal factorization; avoid normal equations when conditioning matters.
   - Eigenproblem: distinguish algebraic/geometric multiplicity, diagonalizability, normality,
     and generalized eigenvectors.
   - Singular values: use SVD for rank, pseudoinverse, low-rank approximation, and ill-conditioned problems.
   - Quadratic form: state symmetry/Hermitian assumptions and use inertia or definiteness criteria.

3. **Compute.**
   1. Preserve exact arithmetic for symbolic or small rational problems.
   2. Use row reduction for structure, but use QR, SVD, or stable factorizations for numerical work.
   3. Never form an explicit inverse merely to solve a system.
   4. Scale variables when magnitudes differ substantially and report the scaling.
   5. For sparse or structured matrices, preserve sparsity, symmetry, bandedness, or positive definiteness.

4. **Verify.**
   - System residual: `r = b - Ax`; report a scale-aware relative residual.
   - Backward error: ask whether the result exactly solves a nearby problem.
   - Factorization: reconstruct the original matrix and check orthogonality/unitarity where applicable.
   - Eigenpair: check `Av - lambda*v`, normalization, multiplicity, and invariant subspaces.
   - Least squares: check residual orthogonality to the column space.
   - Basis/map: verify reconstruction under the declared coordinates.
   - Conditioning: estimate sensitivity separately from algorithmic stability.

   A small residual does not imply a small forward error for an ill-conditioned problem.

5. **Deliver.**
   Report structural conclusions first, then the chosen algorithm, result, residual/error measures,
   conditioning, and any non-uniqueness. Use `$cx-numerical-analysis-error-control` for sensitive
   floating-point conclusions.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
A small residual does not guarantee small forward error for an ill-conditioned problem; do not treat a numerical rank threshold as exact structure. Use `$cx-numerical-analysis-error-control` for sensitive floating-point conclusions.

## Source basis

This workflow is an original synthesis informed by Hefferon's openly licensed *Linear Algebra*;
source provenance is recorded in `../../docs/TEXTBOOK_SOURCES.md`.
