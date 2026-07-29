# Manuscript package contract

## Required files

Every package contains:

```text
manuscript-contract.json
manuscript.md
claim-citation-map.json
reporting-checklist.json
submission-package.json
```

Use schema version `1` and one stable `manuscript_id` across all JSON files.
Keep every path relative to the package root and record a lowercase SHA-256.
Include source manifests and every artifact referenced by a reported value
inside the portable package.

`manuscript-contract.json` records:

- `mode`: `new`, `revision`, or `rebuttal`;
- document type, venue, evidence cutoff, reporting guideline, and output formats;
- the source-manifest path and SHA-256;
- exact prior-manuscript and reviewer-comment identities when applicable;
- declarations with `user-supplied`, `not-applicable`, or `unknown` status.

`submission-package.json` lists every package file except itself. Excluding
itself avoids a circular digest.

## Package status

- `draft`: unresolved claims, checklist items, declarations, or review findings
  may remain.
- `review-ready`: deterministic validation is clean and required declarations
  are resolved, but independent review is pending.
- `submission-ready`: validation is clean and a passed, hash-matched independent
  review receipt is included.

Do not use a clean validator result as a substitute for independent review.

## Validation

Run:

```bash
python scripts/validate_manuscript_package.py artifacts/<run>/manuscript --require-clean
```

Save JSON output with `--output <path>` when it must enter the artifact bundle.
The validator checks declared structure, paths, hashes, cross-file IDs,
claim/citation links, reported-value evidence, BibTeX keys, declaration status,
checklist status, and revision or rebuttal identity.

## Failure handling

| Failure | Required response |
| --- | --- |
| source or file hash mismatch | stop; recover the exact bytes or rebuild the package |
| unsupported material claim | link valid evidence or downgrade, mark unresolved, or withdraw |
| unknown declaration | keep `draft`; request a user-supplied or not-applicable decision |
| unresolved checklist item | keep `draft` and expose the missing reporting element |
| changed manuscript after review | invalidate the review receipt and review the new hashes |
| package path escapes root | reject it; copy approved evidence into the portable package |
