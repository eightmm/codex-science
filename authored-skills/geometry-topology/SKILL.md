---
name: geometry-topology
description: "Formulate and verify geometry and topology arguments. Use for metric and topological spaces, continuity, compactness, connectedness, manifolds, curves and surfaces, homotopy, covering spaces, Euler characteristic, and geometric invariants."
license: MIT
---

# Geometry and Topology

## Decision contract

State the category, objects, maps, hypotheses, equivalence relation, topology or metric, dimension, regularity, orientation, boundary, and base points. Say whether the claim is local or global and intrinsic or embedding-dependent. Assign each material claim a stable ID and status; use only invariants valid under the declared equivalence and regularity.

## Reference usage

Read [references/geometry-topology-evidence.md](references/geometry-topology-evidence.md) before computing Euler characteristic, homology, persistent homology, or geometric quantities; before making homotopy, homeomorphism, diffeomorphism, or invariance claims; and when checking conventions, triangulations, or sensitivity. It defines claim classes, coefficient and filtration choices, controls, and downgrade conditions.

Preserve inputs, derivations, code, environment, and failed or null checks with `$science-provenance`; use `$science-review` before material or consequential scientific conclusions.

## Workflow

1. **Classify the problem.** Identify objects, maps, equivalence, topology or metric, dimension, regularity, orientation, boundary, base points, and whether the target is local/global or intrinsic/embedding-dependent; record the assumptions and intended invariant.
2. **Check hypotheses.** Match the claim to its category and verify separation, compactness, connectedness, continuity, chart overlap, and transition regularity as applicable; record each checked hypothesis and any gap.
3. **Separate claim types.** Label a computed invariant or reconstructed object as a computation, a homotopy/homeomorphism/diffeomorphism statement by the exact equivalence proved, and a theorem or empirical claim only when its proof or independent evidence supports it; record claim IDs, status, and support.
4. **Choose the construction.** Select definitions, maps, coordinates, or a decomposition that preserve the declared equivalence; for homotopy or covering arguments track base points, path lifting, induced maps, and group actions; record the construction and conventions.
5. **Compute with declared conventions.** For Euler characteristic or homology state the finite complex or space, boundary treatment, and coefficient field; for persistent homology state the filtration and parameter; record exact inputs, coefficients, filtration, and result.
6. **Probe edge cases.** Check empty sets, boundaries, noncompact spaces, singular points, and counterexamples when hypotheses are removed; record tested cases and unresolved counterexamples.
7. **Check representations.** Verify well-definedness, continuity, injectivity, surjectivity, coordinate overlap, orientation signs, and triangulation quality; recompute with an alternate chart or decomposition when feasible and record discrepancies.
8. **Verify and report.** Check exact combinatorial identities or convergence/triangulation stability for computations, then report the claim, proof or computation, uncertainty, applicability domain, limitations, and smallest falsifiable next action; preserve commands, artifacts, and hashes.

## Outputs

Produce a `geometry-topology-evidence-v1` record containing: claim identifier (`claim_id`); claim class (`claim_class`); claim status (`status`: supported, contradicted, inconclusive, or unavailable); normalized objects, maps, and assumptions (`objects`, `maps`, `assumptions`); declared category and equivalence (`category`, `equivalence`); invariant or construction and conventions (`method`, `conventions`); coefficient field and filtration when applicable (`coefficient_field`, `filtration`); evidence and checks (`evidence`, `checks`); uncertainty and applicability domain (`uncertainty`, `applicability_domain`); limitations and next action (`limitations`, `next_action`); artifact paths and hashes (`artifacts`). Preserve failed and null results.

## Boundaries

Do not infer a global property from one chart, confuse embedding geometry with intrinsic geometry or topology, or promote a computed invariant or reconstructed field to a theorem or experimentally supported result. Stop when a required hypothesis, base point, orientation, coefficient field, filtration, or equivalence relation is unspecified. A finite computation does not establish a result beyond its declared representation and checks.

## Source basis

Original synthesis informed by Hitchman's openly licensed geometry and topology text and Lebl's analysis text;
source details are in `../../docs/TEXTBOOK_SOURCES.md`.
