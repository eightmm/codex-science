---
name: proof-and-counterexample
description: "Prove, disprove, or repair mathematical statements by normalizing quantifiers and hypotheses, selecting a proof strategy, constructing counterexamples, and auditing every logical dependency. Use for theorem proving, proof critique, missing-assumption diagnosis, and universal or existential claims."
license: MIT
---

# Proof and Counterexample

## Normalize the claim

1. Rewrite the statement with explicit universe, quantifier order, hypotheses, and conclusion.
2. Expand ambiguous terms into definitions and mark edge cases such as empty sets, zero,
   endpoints, degeneracy, and non-finite objects.
3. Write the exact negation. Preserve quantifier order: negating `for every` produces
   `there exists`, and negating an implication keeps the hypothesis and negates the conclusion.
4. Check whether the statement is false before investing in a proof.

## Choose a route

- Direct: start from hypotheses and build the conclusion.
- Contrapositive: use when the negated conclusion exposes usable structure.
- Contradiction: use when assuming the negation creates a short impossible condition;
  avoid it when a direct or contrapositive proof is clearer.
- Induction: state the induction domain, base cases, hypothesis, and exact step.
- Construction: exhibit an object and verify every required property.
- Extremal/invariant: select a minimal or maximal object or a preserved quantity.
- Equivalence: prove every direction separately; a cycle is acceptable only if all
  implications are explicit.

## Search for a counterexample

1. Attack omitted hypotheses: zero, empty, disconnected, noncompact, noncomplete,
   noncommutative, singular, repeated-root, and boundary cases.
2. Search the smallest finite dimension or cardinality first.
3. Translate the negated claim into constraints and construct an object satisfying them.
4. Verify that the example satisfies every original hypothesis and fails exactly the conclusion.
5. If the original statement is nearly true, give the smallest repair and explain why it suffices.

## Audit

- Label definitions, earlier results, and external theorems.
- Verify all theorem hypotheses at the point of use.
- Reject circular steps, converse errors, hidden existence assumptions, unjustified limit
  interchange, and division by a possibly zero quantity.
- Distinguish `not proven` from `false`.
- Treat symbolic or finite computation as proof only when it exhausts the stated finite domain
  or is accompanied by a valid general argument.

## Deliver

State `proved`, `disproved`, or `conditional`. For a proof, give a dependency-complete argument.
For a refutation, give the counterexample and verification. For a repaired theorem, identify the
added hypothesis and whether it is sufficient, necessary, or both.

## Source basis

The proof discipline is independently synthesized from Lebl's *Basic Analysis I* and
Hefferon's *Linear Algebra*; provenance and licenses are in `../../docs/TEXTBOOK_SOURCES.md`.
