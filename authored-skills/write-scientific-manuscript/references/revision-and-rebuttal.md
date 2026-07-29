# Revision and reviewer rebuttal

## Identity boundary

Before editing, copy the exact submitted manuscript and record its package path
and SHA-256 in `prior_manuscript`. For rebuttal, also preserve the complete
editor and reviewer comments with a path and SHA-256.

Do not rely on an editable cloud view, remembered wording, or comments pasted
without reviewer labels and numbering. Stop if comment order or manuscript
version is ambiguous.

## Point-by-point response

For each comment, record:

- stable comment ID and verbatim comment;
- response status: accepted, partially accepted, disputed, clarification
  requested, or blocked;
- concise response with evidence;
- exact old and new manuscript locators;
- change summary and affected claim IDs;
- new analysis, source, artifact, or limitation introduced;
- remaining disagreement or unavailable evidence.

Be respectful and direct. Do not claim an analysis was performed unless its
execution and output are in the artifact record. A rhetorical answer cannot
resolve a methodological or evidence defect.

## Change ledger

Preserve a machine-readable ledger connecting each reviewer comment to changed
files, claim IDs, artifact hashes, and manuscript locations. Revalidate the
whole package after changes. Any material byte change invalidates a review
receipt for the previous package.

For revisions without reviewer comments, record the rationale, request source,
and affected claims in the same ledger.

## Failure handling

| Failure | Required response |
| --- | --- |
| prior manuscript hash unavailable | stop; recover the exact submitted version |
| reviewer comment incomplete or ambiguous | request the complete authoritative comments |
| requested analysis not performed | state the limitation or execute it through an approved scientific workflow |
| reviewer request conflicts with evidence | explain the conflict and preserve the supported claim boundary |
| response changes a material result | update artifacts, trace map, abstract, displays, and independent review |
| requested disclosure is unknown | keep it unresolved; do not invent a declaration |
