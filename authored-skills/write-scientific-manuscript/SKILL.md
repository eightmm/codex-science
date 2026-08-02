---
name: write-scientific-manuscript
description: "Create or revise a traceable scientific manuscript and submission package from reviewed artifacts, a claim register, verified citations, or an existing draft. Use for research articles, methods papers, literature syntheses, journal revisions, cover letters, and point-by-point reviewer rebuttals; do not use to invent results, citations, authorship, ethics, funding, or other missing declarations."
license: MIT
---

# Write Scientific Manuscript

Turn a reviewed scientific record into publication prose without allowing the narrative to outrun the evidence.

## Decision contract

Before drafting, record:

- manuscript mode: `new`, `revision`, or `rebuttal`;
- target document type, audience, venue, section and total word limits, output formats, and evidence cutoff;
- source manifest path and hash, review status, material claim IDs, and permitted inference level;
- applicable reporting guideline and whether venue instructions were supplied or verified from an official source;
- author-approved terminology, title direction, and language;
- status of authorship, contributions, ethics, funding, conflicts, and data/code availability;
- deliverables, review modes, and what would keep the package in `draft`.

Require an exact prior-manuscript hash for revision. Require that hash plus the received reviewer comments for reviewer rebuttal. Treat preferences such as prose cadence as reversible defaults; stop for a missing source record or an interpretation-changing choice.

## Reference usage

Inspect `references/index.json` and load only the route needed.

- Read [the manuscript package contract](references/manuscript-package.md) before creating or validating package files.
- Read [claim and citation traceability](references/claim-citation-traceability.md) before attributing a material claim, numerical value, table, figure, or citation.
- Read [reporting and submission](references/reporting-and-submission.md) before applying a reporting checklist, venue constraint, declaration, or submission-ready status.
- Read [revision and rebuttal](references/revision-and-rebuttal.md) before revising a submitted manuscript or drafting a point-by-point response.

Record any materially controlling reference in the run's `reference-use-ledger`. These references constrain procedure; they are not scientific evidence.

## Workflow

1. **Inspect the record.** Validate the complete source artifact bundle, not only the manifest hash. For `review-ready`, require a passed independent `record`/`source`/`method` receipt linked to its review packet, with stated limitations, unchanged manifest semantics, and coverage of every evidence artifact and source claim. Inventory supporting and contradicting evidence, null results, limitations, figures, tables, queries, executions, and unavailable material. Never reconstruct absent values from memory.
2. **Freeze the contract.** Write `manuscript-contract.json`. Keep every unresolved declaration explicit. A package with unknown required declarations remains `draft`.
3. **Build the narrative spine.** Order material claims and the figures or tables that support them. Mark each proposed statement as reported result, interpretation, contextual source claim, limitation, or future work.
4. **Create the claim-citation map.** Assign manuscript claim IDs before prose expansion. Link each material claim to an existing source claim ID, hashed artifacts, persistent citation IDs, inference level, and one unique manuscript locator. Keep the map's exact claim text inside that locator block. Use `citation-needed` rather than inventing a reference; it keeps the package in `draft`.
5. **Draft evidence-near sections first.** Draft Methods and Results from recorded inputs, executions, analysis outputs, units, denominators, and uncertainty. For a reported JSON value, point to the exact scalar with an RFC 6901 pointer; make derived or converted values point to a recorded derivation artifact. Preserve failed, negative, null, and inconclusive outcomes.
6. **Draft interpretation.** Write Discussion, Introduction, Abstract, and Title only after the evidence-near text is stable. Separate observation from explanation, compare against verified sources, and keep conclusions within the weakest essential evidence link.
7. **Prepare displays and supplements.** Reuse or regenerate figures and tables only from traceable artifacts. Do not require a graphical abstract or AI-generated figure unless the venue or user requests it and the separate tool action is approved.
8. **Apply reporting and venue constraints.** Complete `reporting-checklist.json` with the same guideline recorded in the contract; use `unresolved` for missing items. Do not infer ethics, funding, authorship, conflicts, or availability statements.
9. **Prepare requested formats.** Always write `manuscript.md`; add `manuscript.tex`, `references.bib`, `cover-letter.md`, `reviewer-response.md`, or supplement indexes when declared in the contract.
10. **Package and validate.** Write `submission-package.json` with hashes for every included file. Run `uv run python scripts/validate_manuscript_package.py <package> --require-clean`. Resolve findings or keep the package in `draft`.
11. **Preserve provenance.** Register the contract, manuscript, claim-citation map, checklist, source record, and submission package with `$science-provenance`.
12. **Review independently.** Use `$science-review` in all three mandatory modes: `record`, `source`, and `method`. Set `submission-ready` only when a passed independent receipt states its limitations and covers those modes, every file listed in `submission-package.json` except the receipt itself, every material claim ID, and the current file hashes, with every material finding resolved. The root `submission-package.json` is deliberately self-excluded from its file list.

For retries, correct the evidence link or downgrade the claim. Never weaken validation, delete a negative result, or change the source identity merely to obtain a clean package.

## Outputs

Require:

- `manuscript-contract.json`
- `manuscript.md`
- `claim-citation-map.json`
- `reporting-checklist.json`
- `submission-package.json`

Produce when requested or applicable:

- `manuscript.tex`
- `references.bib`
- `cover-letter.md`
- `reviewer-response.md`
- prior-manuscript and reviewer-comment snapshots
- supplementary-material index
- passed independent review receipt

The claim-citation map records material claim ID, source claim ID, status, inference level, manuscript locator, artifact path and SHA-256, persistent citation IDs, and every reported value with its exact evidence locator. The submission package records file hashes, package status, and review status.

## Boundaries

- Do not fabricate or guess a citation, persistent identifier, quotation, numerical value, unit, denominator, uncertainty, method, result, author, contribution, ethics approval, funding source, conflict statement, or availability statement.
- Do not cite a paper merely because its title is relevant. Verify that the source supports the attributed statement and identify shared studies or dependencies.
- Do not promote association to causality, exploration to confirmation, model output to experimental evidence, process completion to scientific validity, or reviewer approval to truth.
- Do not hide contradictory, null, failed, excluded, or inconclusive evidence to improve the story.
- Do not call prose revision independent review or call record inspection reproduction.
- Keep unresolved claims as `citation-needed`, `unresolved`, `inconclusive`, or withdrawn. Keep unresolved declarations visible and the package in `draft`.
- Do not silently invoke inactive imported writing skills, external credentials, executable templates, network retrieval, or image generation.
- Stop when the source manifest or submitted-manuscript identity cannot be verified, reviewer comments are incomplete, a venue requirement changes scientific interpretation, or private data would leave the approved boundary.
