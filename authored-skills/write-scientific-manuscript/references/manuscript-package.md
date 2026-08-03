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

The source manifest must itself be a valid Codex Science artifact bundle with
no deterministic review findings. A `review-ready` or `submission-ready`
package requires a current passed, independent `record`/`source`/`method` review
receipt linked to a valid `review-packet-v1`. The packet freezes the reviewed
manifest semantics; the receipt states its limitations and covers all non-review
source artifacts and all source claim IDs used by material manuscript claims.

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
  review receipt covers mandatory `record`, `source`, and `method` modes, every
  file listed in `submission-package.json` except that receipt itself, and every
  material manuscript claim, and states at least one review limitation. The root
  package manifest remains self-excluded.

Do not use a clean validator result as a substitute for independent review.

## Compatibility note

Schema version `1` remains readable, but readiness validation is intentionally
stricter. Existing packages can return new findings when their source receipt
has no linked review packet, their source review omits a mandatory mode, their
checklist guideline differs from the contract, or cited claim segments omit the
recorded citation anchor, or an independent receipt states no limitation. Keep
such a package in `draft` or `review-ready`, regenerate the exact review packet
and receipt, refresh hashes, and validate again; do not suppress the finding or
relabel the old receipt.

## Validation

Run:

```bash
"<plugin-root>/scripts/python_runtime.sh" "<plugin-root>/scripts/validate_manuscript_package.py" artifacts/<run>/manuscript --require-clean
```

Save JSON output with `--output <path>` when it must enter the artifact bundle.
The validator checks declared structure, paths, hashes, cross-file IDs,
claim/citation links, reported-value evidence, BibTeX keys, declaration status,
checklist/contract guideline agreement, revision or rebuttal identity,
source-bundle review-packet and receipt coverage, and submission review receipt
freshness and completeness.

## Failure handling

| Failure | Required response |
| --- | --- |
| source or file hash mismatch | stop; recover the exact bytes or rebuild the package |
| unsupported material claim | link valid evidence or downgrade, mark unresolved, or withdraw |
| unknown declaration | keep `draft`; request a user-supplied or not-applicable decision |
| unresolved checklist item | keep `draft` and expose the missing reporting element |
| changed manuscript after review | invalidate the review receipt and review the new hashes |
| package path escapes root | reject it; copy approved evidence into the portable package |
