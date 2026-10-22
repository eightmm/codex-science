# Geometry and topology evidence guide

## Claim classes and semantics

Assign one class per claim. A **definition-level** claim follows directly from declared definitions. A **theorem** claim requires stated hypotheses and a proof valid in the named category. A **computed invariant** reports an algorithmic result for specified finite input, conventions, and coefficient field; it is not itself proof of an unstated classification theorem. A **reconstruction** is a representation recovered from data or a discretization and remains dependent on that representation. A **simulated field** is a model output, not an observation. An **experimentally supported** claim requires an observation tied to a measurement protocol and uncertainty. Use `supported`, `contradicted`, `inconclusive`, or `unavailable` for the evidence status; do not use status as a substitute for claim class.

Keep equivalence strengths distinct: a homotopy equivalence preserves homotopy type, a homeomorphism preserves topological structure, and a diffeomorphism requires the stated smooth structure and regularity. None follows merely from equal Betti numbers or Euler characteristic. Separate topological invariants from metric quantities, coordinate artifacts, and embedding-dependent measurements.

## Source dependencies and independence

Record the source object, acquisition or cohort, preprocessing, segmentation, mesh or triangulation, software and version, coefficient field, and parameter choices. Multiple meshes derived from one scan, multiple triangulations of one surface, propagated labels, or repeated algorithm runs are dependent representations, not independent observations. Pin dataset releases and software versions; preserve the mapping from source records to derived complexes. State whether a result depends on a shared segmentation, coordinate system, or boundary convention.

## Conventions and computations

Declare orientation and boundary conventions before signs or integration. For Euler characteristic and homology, state the complex or space and coefficient field (for example, a named finite field); torsion and Betti numbers can depend on coefficients. Document treatment of relative boundary components, open versus closed sets, compact support, and base points when those choices affect the result.

For persistent homology, name the filtration function, sublevel/superlevel convention, units and scale, parameter range, coefficient field, and treatment of essential classes. Describe how data are converted to a filtered complex. A barcode is conditional on these choices and the input representation; it is not a unique property of raw data absent a declared construction.

Assess triangulation quality using element degeneracy/aspect or geometric approximation criteria appropriate to the task, boundary conformity, and convergence under refinement. For exact finite combinatorics, check chain-map and boundary-squared identities where relevant. A different triangulation is a useful control only when it represents the same declared object and boundary conditions.

## Uncertainty and sensitivity

Separate theorem hypotheses (which are true or false, not statistical uncertainty) from uncertainty in measured geometry, segmentation, coordinates, model selection, and numerical computation. Carry input uncertainty through the chosen estimator or report a bounded perturbation analysis; state which uncertainty sources are omitted. Do not attach precision unsupported by discretization or measurement resolution.

Vary mesh density and quality, segmentation or point perturbations, coordinate and orientation conventions, coefficient field, filtration choice and scale, and persistence threshold when relevant. Predeclare meaningful perturbation ranges where possible. Treat a qualitative claim as fragile if its class/status changes, a claimed feature appears or vanishes under plausible perturbations, or the numerical result shifts beyond the stated tolerance. Report all tested variants, including failures.

## Controls and failure detection

- Use known simple spaces (point, interval, circle, sphere, disk, torus) as positive controls for expected connectivity, boundary, Euler characteristic, and homology behavior.
- Use a deliberately broken orientation, omitted boundary face, duplicated cell, or invalid incidence relation as a negative/software control; verify that the relevant check detects it.
- Compare an analytic or exact combinatorial case with the implementation. Confirm chain identities and recompute with an alternate valid triangulation or chart.
- Detect category errors by testing whether a claimed invariant is actually preserved by the declared map or equivalence. Equal homology alone must not be reported as homeomorphism.
- Detect instability by refining triangulations and perturbing inputs; detect filtration artifacts by varying the filtration family and scale.

Common failures and detection: missing hypotheses are exposed by an edge-case or counterexample check; sign errors by orientation reversal and overlap checks; boundary mistakes by relative/absolute calculations on a disk; coefficient ambiguity by rerunning homology over stated fields; poor triangulation by degeneracy metrics and refinement; false topological certainty by comparing plausible reconstructions and perturbations; and false independence by tracing derived meshes to their original scan or cohort.

## Applicability domain

Finite simplicial or cubical algorithms establish results about the encoded finite complex, subject to implementation checks. Their transfer to a continuous space requires a justified approximation or convergence argument. Smooth claims require adequate regularity and compatible smooth structures. Persistent homology stability results do not make an arbitrary filtration scientifically meaningful or repair noisy, biased, or non-independent data. A numerical invariant cannot establish geometric or biological truth without validated input, measurement, and model assumptions.

## Claim assignment examples

- A chain complex calculation that yields Betti numbers is a computed invariant. State the matrix/rank method, coefficient field, boundary treatment, and finite complex. The output supports the values for that encoded complex only.
- A proof that two maps compose up to homotopy supports a homotopy-equivalence claim if the domains, codomains, continuity, and homotopies are explicit. It does not support homeomorphism or diffeomorphism.
- A coordinate formula for curvature is local until chart compatibility and regularity establish a global geometric quantity. Record transition maps and orientation convention.
- A point-cloud reconstruction or mesh-derived surface is a reconstruction. State the sampling, reconstruction algorithm, and approximation assumptions before transferring a topological property to an underlying object.
- A field generated by a geometric simulation remains simulated even if it satisfies a conservation identity. Experimental support requires measurement provenance and independent uncertainty checks.

## Practical decision record

For each computed quantity, retain:

1. The exact input representation and its source lineage.
2. The declared mathematical category and map/equivalence being tested.
3. Orientation, boundary, base-point, coefficient, and filtration conventions that affect the result.
4. Software/version or hand derivation and a deterministic checksum when available.
5. Positive-control outcomes and negative-control detection.
6. Perturbation ranges, alternative decompositions, and any changed claim status.
7. The reason the evidence is sufficient for this claim and the nearest stronger claim it does not establish.

For point-set arguments, distinguish compactness from sequential compactness only under the assumptions that identify them, such as metrizability. For manifold arguments, check whether a boundary is allowed and whether a map is smooth enough for the requested derivative or orientation statement. For curves and surfaces, separate parametrization-dependent speed from length and distinguish intrinsic metric quantities from extrinsic curvature or area. These distinctions determine which evidence belongs to a claim.

When a computation disagrees across valid triangulations, first compare whether they encode the same space, boundary, and coefficient choices. If they do, retain both results and mark the invariant computation inconclusive until implementation or representation differences are resolved. Do not average discrete topological outputs or choose the decomposition that supports the preferred conclusion.

## Geometry-specific checks

For metric geometry, state the metric and units and distinguish distance, length, area, and curvature from topological invariants. For embedded curves and surfaces, identify the ambient space and embedding; compare intrinsic and extrinsic quantities only under a map that preserves the relevant structure. A reparameterization can change coordinate speed while leaving curve length unchanged when its regularity assumptions hold.

For point-set claims, use the open-set definitions of continuity, compactness, and connectedness and name the separation axiom required by the argument. Treat degree as invariant only for the stated class of maps and oriented spaces; specify its definition and hypotheses before using it to infer existence or multiplicity.

For manifolds, state dimension and regularity, and verify that charts cover the claimed domain. Check transition functions and their differentiability before interpreting derivatives globally. If an orientation is used, record the chosen orientation and test sign changes on overlaps. Boundary points require compatible half-space charts and explicit boundary conditions.

For covering-space claims, specify connectedness, local path-connectedness, semilocally simply connected assumptions when required, base point, and deck group action. For induced homology or fundamental-group maps, name the map and verify functorial direction; matching group presentations alone is not a proof of equivalence.

For Euler characteristic, state whether the complex is finite and whether the convention uses cells, simplices, or a relative pair; do not apply a finite alternating-sum formula to an infinite decomposition without a separate convergence argument.

An edge-case checklist should include: empty and singleton spaces; disconnected unions; open and closed intervals; a disk with and without its boundary; a noncompact example; and a singular or degenerate complex. Choose only cases relevant to the claim, but record why omitted cases do not change the stated scope.

## Sources

- Allen Hatcher, *Algebraic Topology*, Cambridge University Press, 2002: homotopy, homology, and algebraic topology conventions.
- Herbert Edelsbrunner and John Harer, *Computational Topology: An Introduction*, American Mathematical Society, 2010: finite computational topology and persistence.
