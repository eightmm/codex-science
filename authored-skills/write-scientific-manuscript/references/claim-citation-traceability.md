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
The exact mapped claim text must appear after one unique claim marker and before
the next claim marker. `citation-needed` and `unresolved` claims remain `draft`.
Every citation ID attributed to a claim must also appear as an `@citation-id`
anchor inside that same claim-marker segment, and each citation record must list
the claim ID in its string-valued `supports_claim_ids` array.

Evidence paths must name files in the reviewed source inventory: either a listed
file artifact or a file contained in a listed `directory-tree` artifact. File
references carry the individual file's SHA-256; a tree's recorded digest covers
its members. Add new or changed evidence to the source manifest and regenerate
its review packet and receipt before marking the package ready for review.

## Citation records

Record one citation ID, persistent identifier, title, source type, verification
source, verified status, and the exact manuscript claim IDs it supports.

`verification_source` must be a package-relative path to an existing file in
that source inventory, or to the recorded source manifest itself. Any file type
is accepted; the validator does not require the persistent identifier to appear
inside the file. A service name or remote URL alone is not a recorded source.
File identity and inventory coverage do not establish correct attribution or
support; review those independently.

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
For JSON artifacts, use an RFC 6901 pointer that resolves to one scalar. The
validator checks that scalar against the reported text, accepting equivalent
numeric formatting such as `2.5` and `2.50`. Point percentages, unit conversions,
rounding, and derived values to a derivation artifact that records the displayed
value. Reported-value and derivation paths must follow the same reviewed source
inventory rule as claim evidence, including membership under a listed directory
tree. Non-JSON locators remain hash-checked but require independent semantic
review. A material claim whose JSON evidence pointer resolves to an integer or
float requires a nonempty `reported_values` list; non-numeric claims do not.
Complete semantic coverage still requires independent review.

## Failure handling

- Missing evidence: mark the claim `unresolved` or remove it.
- Citation mismatch: correct the attribution; do not substitute a nearby paper.
- Changed artifact: recompute hashes and re-review every affected claim.
- Contradictory evidence: expose it and narrow confidence or inference.
- Unregistered semantic claim: add it to the map before review.
- Numerical discrepancy: correct from the authoritative artifact and inspect
  every reuse in text, tables, figures, abstract, and supplement.
