# Reporting and submission

## Reporting checklist

Select a guideline from the actual study design, not the desired venue:
CONSORT for randomized trials, STROBE for observational studies, PRISMA for
systematic reviews, STARD for diagnostic accuracy, TRIPOD for prediction
models, ARRIVE for animal research, or another named authoritative guideline.

Record each item as `met`, `not-applicable`, or `unresolved`, with a manuscript
locator and evidence reference when applicable. Do not turn an absent procedure
into a writing omission; the manuscript must disclose that it was not done.

## Declarations

Track authors, contributions, ethics, funding, conflicts, and data/code
availability separately. Allowed statuses are:

- `user-supplied`: preserve the supplied value and its provenance;
- `not-applicable`: retain the explicit decision;
- `unknown`: keep the package in `draft`.

Never infer these statements from affiliation, repository metadata, prior
papers, acknowledgements, or model output.

## Venue constraints

Record the source, access date, and version or page identity for venue
instructions. Separate formatting constraints from scientific choices. A word
limit may shorten prose but must not remove a material limitation, negative
result, denominator, uncertainty statement, or required reporting item.

Do not claim current venue compliance from an old template. Network retrieval,
credentials, paid templates, or executable venue tooling require their normal
approval and audit boundaries.

## Submission readiness

Use `review-ready` only when deterministic package validation is clean and no
required declaration or checklist item is unresolved. Use `submission-ready`
only when:

- every file hash matches;
- every material claim is traced;
- requested output formats are present;
- declarations and reporting items are resolved;
- independent record/source/method review passed for the exact package;
- critical and major findings are resolved or affected claims are withdrawn.

A journal portal upload, editorial check, or reviewer pass does not establish
scientific truth or acceptance.
