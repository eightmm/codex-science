---
name: proof-and-counterexample
description: "Prove, disprove, test, or repair mathematical statements by normalizing quantifiers and assumptions, building proof obligations, searching bounded domains safely, verifying counterexamples, and assigning evidence statuses that distinguish computation from proof."
license: MIT
---

# Proof and Counterexample

## Decision contract

Write the exact domain, quantifier order, hypotheses, conclusion, equality notion, edge cases, and intended evidence status before proof search. Write the exact negation. Decide whether the target is a general theorem, an exact finite proposition, or only a bounded test.

Check whether the statement is false before investing in a proof. Do not weaken a failed statement silently; create a repaired claim with its added hypothesis.

## Reference usage

Read [proof and counterexample evidence](references/proof-counterexample-runtime.md) before `counterexample-search`, `proof-obligation-authoring`, or assigning `proved-*` or `disproved`. The reference contains exact domain declarations, expression limits, result statuses, and receipt rules.

Record material reference hashes. Preserve search and proof artifacts with `$science-provenance`, then use `$science-review` for any claim that leaves the local exercise context.

## Workflow

1. Normalize the statement and negation with explicit types and quantifiers.
2. Attack omitted hypotheses, zero and empty cases, boundaries, singularities, small finite objects, and low dimensions.
3. When a bounded executable domain helps, run `scripts/search_counterexample.py`. A returned assignment must satisfy every hypothesis and violate the conclusion.
4. If no counterexample is found, keep the status `tested` unless an exact finite domain was completely exhausted.
5. For a proof, choose direct, contrapositive, contradiction, induction, construction, invariant, extremal, or equivalence routes and decompose every material dependency into a proof-obligation graph.
6. Produce an `informal-deductive`, `finite-exhaustion`, or `formal-kernel` proof receipt appropriate to the evidence.
7. Cross-check statement hashes, assumptions, and unresolved obligations before changing the claim status.

## Outputs

- `mathematical-claim` with statement hash, domain, assumptions, quantifiers, status, and permitted inference;
- `counterexample-search` receipt for bounded evaluation;
- `proof-obligation-graph` for deductive dependencies;
- `proof-receipt` identifying deductive, finite, formal, or computational evidence;
- repaired theorem and necessity/sufficiency discussion when the original statement fails;
- manifest and review receipt for material work.

## Boundaries

- `not proved` is not `false`; `no counterexample found` is not `proved`.
- Random or floating-point samples cannot prove a universal statement.
- Exact finite exhaustion proves only the exact finite domain stated in the receipt.
- A symbolic computation is proof only when its transformations, domains, and theorem dependencies are justified.
- A passed obligation cannot depend on an open or failed obligation.
- A counterexample must satisfy every original hypothesis, not a weakened approximation.
- Stop and report `conditional`, `tested`, or `unavailable` rather than inventing a missing lemma or hiding a failed case.

## Source basis

The proof discipline is independently synthesized from Lebl's *Basic Analysis I* and Hefferon's *Linear Algebra*; provenance and licenses are in `../../docs/TEXTBOOK_SOURCES.md`.
