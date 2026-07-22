---
name: formal-theorem-proving
description: "Formalize mathematical statements and produce auditable kernel-check receipts in an existing Lean 4 workspace. Use for theorem-statement audits, proof repair, definition design, tactic or term proofs, dependency minimization, axiom inspection, and correspondence checks between formal and informal claims."
license: MIT
---

# Formal Theorem Proving

## Decision contract

Write the intended informal claim, formal domain and types, quantifiers, hypotheses, equality notion, constructive or classical assumptions, and required trust boundary. Pin the existing Lean, Lake, Mathlib, and import revisions. State whether the task is statement design, proof construction, proof repair, or final kernel verification.

Do not change the theorem merely to obtain a compiling proof without creating a new mathematical claim and correspondence review.

## Reference usage

Read [the Lean proof runtime](references/lean-proof-runtime.md) before `formal-proof-preview`, `formal-proof-execution`, or assigning `proved-formal`. It defines safe workspace paths, exact CLI fields, timeouts, source hashes, admitted constructs, axioms, unsafe declarations, and receipt meaning.

Record the reference and theorem hashes with `$science-provenance`. Use `$science-review` to compare the checked theorem with the informal claim.

## Workflow

1. Audit the statement before proof search. Check for vacuity, weakened hypotheses, wrong quantifier order, unintended coercions, finite/infinite mismatch, and a stronger or weaker equality notion.
2. Search existing definitions and lemmas before introducing synonyms.
3. Create the smallest compiling theorem with explicit imports and helper lemmas that expose the mathematical invariants.
4. Prefer stable term or structured tactic proofs. Isolate automation and record its dependencies.
5. Preview with `scripts/check_formal_proof.py --preview` before executing an unfamiliar workspace command.
6. Execute the bounded checker in the existing approved workspace. Preserve stdout/stderr hashes, tool version, exit code, theorem hash, axioms, admitted constructs, and source-mutation check.
7. Verify informal/formal correspondence explicitly; create `proved-formal` only after a passed `formal-kernel` receipt and a separate correspondence review.

## Outputs

- exact formal theorem source and imports;
- `mathematical-claim` for the intended statement;
- optional `proof-obligation-graph` for helper lemmas;
- `formal-proof-check` with nested `proof-receipt`;
- checker command, version, output hashes, and theorem-file SHA-256;
- axiom, admitted-construct, and unsafe-declaration report;
- line-by-line informal/formal correspondence explanation;
- manifest and independent review receipt.

## Boundaries

- Do not accept `sorry`, `admit`, placeholder proof terms, unsafe declarations, or unreviewed axioms as completed proof.
- A compiling theorem may be vacuous or weaker than the prose claim.
- The runtime never installs Lean, downloads Mathlib, creates a project, or modifies the toolchain without explicit user approval.
- A preview does not execute the kernel and cannot support `proved-formal`.
- A kernel receipt covers exact hashed source and environment; any statement, source, import, toolchain, or trust change invalidates it.
- Stop and report `failed` or `unavailable` instead of introducing an axiom or weakening the target to force completion.

## Source basis

Original synthesis informed by the official *Theorem Proving in Lean 4* documentation; source details are in `../../docs/TEXTBOOK_SOURCES.md`.
