---
name: linear-algebra-problem-solving
description: "Solve exact and numerical linear algebra problems with explicit field, dimensions, bases, rank structure, conditioning, and residual checks. Use for linear systems, vector spaces, linear maps, eigenproblems, least squares, SVD, quadratic forms, and matrix factorizations."
license: MIT
---

# Linear Algebra Problem Solving

## Decision contract

State the field, spaces, dimensions, bases, representation, and exact or floating-point goal. Distinguish structural conclusions from numerical estimates and identify conditioning that limits interpretation. Classify results as proven with stated assumptions, numerically verified with conditioning and backward/forward evidence, simulated estimates with Monte Carlo error, or conjectures. Record baseline, inference limit, uncertainty rule, falsifier, and any missing choice that materially changes the method.

## Reference usage

- Read [references/linear-algebra-evidence.md](references/linear-algebra-evidence.md) before assigning claim classes, interpreting rank or eigenstructure numerically, comparing algorithms, or reporting conditioning, sensitivity, or applicability.

## Workflow

1. **Specify structure:** state the scalar field, vector spaces, dimensions, basis conventions, matrix orientation, inner product, and exact versus floating-point representation; check products and maps for dimension compatibility and record normalized inputs and assumptions.
2. **Fix representation:** distinguish a linear map from its matrix representation, record basis changes explicitly, and identify scaling or units; if representation or field ambiguity changes the result, resolve it before computing and record the choice.
3. **Select the problem class:** for systems determine rank, consistency, nullity, and solution-set dimension; for subspaces prove closure, independence, and spanning; for maps compute kernel/image and check rank-nullity; for least squares prefer orthogonal factorization and avoid normal equations when conditioning matters; for eigenproblems distinguish algebraic/geometric multiplicity, diagonalizability, normality, and generalized eigenvectors; use SVD for rank, pseudoinverse, low-rank approximation, and ill-conditioned problems; for quadratic forms state symmetry/Hermitian assumptions and use inertia or definiteness criteria; record the rationale and claim target.
4. **Choose computation:** preserve exact arithmetic for symbolic or small rational problems; use row reduction for structure and QR, SVD, or stable factorizations for numerical work; never form an explicit inverse merely to solve a system; scale variables when magnitudes differ substantially and report scaling; preserve sparsity, symmetry, bandedness, or positive definiteness; record algorithm, precision, revisions, and stopping rules.
5. **Run the smallest discriminating case:** test a small exact case, known solution, or invariant before the full problem; retain input, code, environment, failed runs, and baseline, and explain what defect the case can expose.
6. **Verify:** for systems report `r = b - Ax` and a scale-aware relative residual; assess backward error as the nearby problem solved; reconstruct factorizations and check orthogonality/unitarity; for eigenpairs check `Av - lambda*v`, normalization, multiplicity, and invariant subspaces; for least squares check residual orthogonality to the column space; for bases/maps verify reconstruction under declared coordinates; estimate sensitivity separately from algorithmic stability; record every diagnostic.
7. **Test sensitivity and domain:** vary precision, tolerances, scaling, rank thresholds, perturbations, matrix size/structure, and algorithm when applicable; classify the result as fragile if rank, solution, eigenstructure, reported digits, or claim status changes beyond the declared tolerance; state the tested conditioning and matrix class and record limits.
8. **Classify and hand off:** assign stable claim IDs and proven, numerically verified, simulated-estimate, or conjecture class with supported, contradicted, inconclusive, or unavailable status; record uncertainty, dependencies, limitations, and next falsifier; preserve commands/derivations and artifact paths/hashes with `$science-provenance`, use `$cx-numerical-analysis-error-control` for sensitive floating-point conclusions, and run `$science-review` before material or consequential conclusions.

## Outputs

Return one `linear-algebra-evidence-v1` record containing: normalized inputs and assumptions (`normalized_inputs`); field, spaces, dimensions, bases, and representation (`mathematical_structure`); claim identifiers, classes, statuses, and exact hypotheses (`claims`); algorithm and source/code dependencies (`method_dependencies`); structural results and numerical diagnostics (`results`); residual, backward error, conditioning, and forward-sensitivity evidence (`error_analysis`); controls (`controls`); uncertainty, sensitivity, and applicability domain (`uncertainty_applicability`); failed/null cases and alternatives (`failures_alternatives`); falsifier and smallest next action (`next_action`); commands, environment, artifact paths, and hashes (`provenance`); `$science-provenance` record and `$science-review` findings (`review`). Report structural conclusions first, then the chosen algorithm, result, residual/error measures, conditioning, and any non-uniqueness.

## Boundaries

A small residual does not guarantee small forward error for an ill-conditioned problem; do not treat a numerical rank threshold as exact structure. Distinguish backward stability from conditioning and report assumptions behind rank, multiplicity, and spectral claims. Use `$cx-numerical-analysis-error-control` for sensitive floating-point conclusions. Preserve failures and nulls; run `$science-review` before material or consequential conclusions.

## Source basis

This workflow is an original synthesis informed by Hefferon's openly licensed *Linear Algebra*;
source provenance is recorded in `../../docs/TEXTBOOK_SOURCES.md`.
