# Claim and citation traceability

## Claim records

Give every material manuscript statement a stable ID and record:

- source claim ID;
- exact prose statement and inference level;
- `supported`, `contradicted`, `inconclusive`, `unresolved`, or `withdrawn`;
- a manuscript locator represented by an HTML comment such as
  `<!-- claim:M-001 -->`;
- hashed evidence references and exact JSON pointer, table cell, figure panel,
  page, line, or record locator;
- citation IDs and verbatim reported-value strings.

A supported material claim needs artifact evidence, a verified citation, or
both. A source claim may remain inconclusive; prose must not silently promote it.

## Citation records

Record one citation ID, persistent identifier, title, source type, verification
source, verified status, and the exact manuscript claim IDs it supports.

Resolve the original source. A relevant title, search result, review article, or
portal duplicate does not establish support for the attributed statement.
Preserve peer-review status, version, study identity, and shared cohort or data
dependencies. Use `citation-needed` when verification is incomplete.

When BibTeX is requested, use the citation ID as the entry key so the validator
can check the map against `references.bib`.

## Reported values

For every material number, interval, unit, denominator, sample count, threshold,
or uncertainty statement, record:

```json
{
  "text": "2.5 response units",
  "artifact_path": "source/result.json",
  "artifact_sha256": "...",
  "locator": "/estimate"
}
```

Keep `text` present verbatim in `manuscript.md`. A hash proves byte identity,
not that the locator or interpretation is scientifically correct; review both.

## Failure handling

- Missing evidence: mark the claim `unresolved` or remove it.
- Citation mismatch: correct the attribution; do not substitute a nearby paper.
- Changed artifact: recompute hashes and re-review every affected claim.
- Contradictory evidence: expose it and narrow confidence or inference.
- Unregistered semantic claim: add it to the map before review.
- Numerical discrepancy: correct from the authoritative artifact and inspect
  every reuse in text, tables, figures, abstract, and supplement.
