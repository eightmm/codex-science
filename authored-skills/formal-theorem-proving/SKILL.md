---
name: formal-theorem-proving
description: "Formalize mathematical statements and produce kernel-checked proofs. Use for Lean 4 theorem proving, proof repair, definition design, tactic or term proofs, dependency minimization, theorem-statement audits, and correspondence checks between formal and informal claims."
license: MIT
---

# Formal Theorem Proving

## Audit the statement first

Translate the intended claim into explicit types, quantifiers, hypotheses, universes, structures, and equality
notions. Check that the formal statement is neither vacuous nor weaker than the prose. Identify constructive,
classical, decidability, and choice assumptions. Pin Lean, Mathlib, and imported library revisions.

## Build the proof

1. Search existing definitions and lemmas before introducing synonyms.
2. Create the smallest compiling theorem with explicit imports and a minimal reproducible file.
3. Decompose the claim into typed helper lemmas that expose the mathematical invariants.
4. Prefer stable term or structured tactic proofs; isolate automation and record its dependencies.
5. Keep coercions, simplification sets, namespaces, and implicit arguments controlled.

Do not add packages, change the toolchain, or fetch large libraries without user approval. Do not accept
`sorry`, `admit`, undeclared axioms, or generated proof artifacts as completed evidence.

## Verify

- Compile from a clean project using the pinned toolchain and exact imports.
- Run axiom inspection and disclose classical or project-specific axioms.
- Search for `sorry`, `admit`, unsafe declarations, and unintended local assumptions.
- Perturb hypotheses and test small countermodels to detect a trivial or mis-stated theorem.
- Compare the checked statement line by line with the original mathematical claim.

## Deliver

Provide the formal statement, imports and versions, proof, kernel-check command and result, axiom report, and
an informal correspondence explanation. Label any remaining gap as unproved.

## Source basis

Original synthesis informed by the official *Theorem Proving in Lean 4* documentation; source details are in
`../../docs/TEXTBOOK_SOURCES.md`.
