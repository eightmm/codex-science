---
name: science-review
description: Independently review a scientific run by checking claims against the approved plan, saved artifacts, citations, environment, and execution record. Use after scientific analysis or writing, before presenting conclusions, and when users ask to verify calculations, citations, reproducibility, methods, figures, or evidence fidelity.
---

# Science Review

Review the record; do not assume the producing agent's conclusion is correct.

## Inputs

Require the approved plan, artifact manifest, execution log, outputs, and cited sources. If any are missing, report the missing evidence instead of filling gaps from memory.

## Review

1. Run `<plugin-root>/scripts/validate_artifact.py <manifest> --review-output <run-dir>/review.json` for deterministic structural checks.
2. Check that each reported computation has a successful execution record and that reported values match saved outputs.
3. Resolve each citation or persistent identifier. Check that the cited source supports the exact attributed claim and distinguish peer-reviewed work from preprints.
4. Check that figures and tables are traceable to code and inputs, with units, axes, legends, and sample counts consistent with the record.
5. Check whether the method can support the conclusion. Inspect baseline choice, controls, leakage, multiple testing, uncertainty, assumptions, and generalization boundaries as applicable.
6. Check every approved plan step. Mark incomplete or blocked steps explicitly.
7. Emit findings with severity, claim, evidence, and required correction. Do not silently edit the producer's record.
8. Re-review after corrections and preserve both the original finding and its resolution.

Use [references/review-checklist.md](references/review-checklist.md) for the compact finding taxonomy.

## Independence

Use a separate subagent when available. Provide raw run artifacts and the approved plan without the intended answer or suspected bug. If no separate agent is available, state that the review was a second pass rather than an independent review.

## Boundary

The deterministic checker does not re-run analyses and cannot judge domain validity by itself. Reviewer success reduces obvious inconsistencies but does not establish scientific truth, clinical validity, or regulatory compliance.
