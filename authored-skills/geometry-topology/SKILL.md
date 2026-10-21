---
name: geometry-topology
description: "Formulate and verify geometry and topology arguments. Use for metric and topological spaces, continuity, compactness, connectedness, manifolds, curves and surfaces, homotopy, covering spaces, Euler characteristic, and geometric invariants."
license: MIT
---

# Geometry and Topology

## Decision contract
State the category, objects, maps, hypotheses, and whether the target is local or global and intrinsic or embedding-dependent. Use only invariants valid under the declared equivalence and regularity.

## Workflow
1. **Identify the category.**
   State the objects, maps, equivalence relation, topology or metric, dimension, regularity, orientation, boundary,
   and base points. Distinguish local from global claims and intrinsic from embedding-dependent quantities.
   Before calculating, name the invariant or obstruction that could decide the problem.

2. **Reason.**
   - For point-set topology, use open-set definitions and verify separation, compactness, connectedness, and continuity hypotheses.
   - For manifolds, declare charts and transition regularity; ensure coordinate calculations define global objects.
   - For curves and surfaces, distinguish parametrization artifacts from length, curvature, area, and topology.
   - For homotopy or covering arguments, track base points, path lifting, induced maps, and group actions.
   - Use Euler characteristic, degree, fundamental group, or homology only in the category where it is invariant.

3. **Verify.**
   - Check definitions against canonical examples and edge cases: empty sets, boundaries, noncompact spaces, and singular points.
   - Test whether a proposed map is well-defined, continuous, injective, surjective, or a homeomorphism as claimed.
   - Verify coordinate overlap and orientation signs; recompute invariants using a different decomposition or chart.
   - Search for counterexamples when a hypothesis is dropped and distinguish necessary from sufficient conditions.
   - For computation, confirm triangulation independence or convergence and retain exact combinatorial checks.

4. **Deliver.**
   Report the category, hypotheses, invariant or construction, proof, counterexample search, coordinate checks, and
   whether the conclusion is local, global, smooth, metric, or purely topological.

## Outputs
Return normalized inputs and assumptions; a machine-readable evidence or execution table; claim IDs marked supported, contradicted, inconclusive, or unavailable; uncertainty and limitations; and the smallest falsifiable next action. Record commands or derivations and artifact paths and hashes with `$science-provenance`; preserve failures and nulls. Run `$science-review` before material or consequential scientific conclusions.

## Boundaries
Do not infer a global property from one chart or confuse embedding geometry with intrinsic geometry or topology. Stop when a required hypothesis, base point, orientation, or equivalence relation is unspecified.

## Source basis

Original synthesis informed by Hitchman's openly licensed geometry and topology text and Lebl's analysis text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
