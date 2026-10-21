---
name: clinical-trials-search
description: "Search ClinicalTrials.gov (API v2) for trials by condition, intervention, status, phase, location, or sponsor; fetch a trial by NCT ID; check eligibility; and count trials. Use for trial discovery, pipeline/portfolio analysis, or patient-matching context. Public API, no credential needed."
license: Apache-2.0
---

# ClinicalTrials.gov Search (Codex-native)

Codex-native adaptation of Google DeepMind's `clinical-trials-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public ClinicalTrials.gov REST API v2 directly.

## Decision contract

Record the question, condition and intervention concepts, geography/time,
intended use, recruitment/status cutoff, and whether this is aggregate discovery
or individual context. Use NCT IDs as canonical registry identifiers. A search
result cannot determine personal eligibility or establish intervention benefit.

## Workflow

1. **Gates (ask before proceeding).** On first use tell the user to review
   ClinicalTrials.gov terms (`https://clinicaltrials.gov/`) and record notice
   in provenance. Read-only HTTP; be polite about rate limits. Helper code must
   use `uv run`, never bare `python3`.
2. Search with `science_search_clinical_trials(query, limit)` (`query` up to
   500 characters; `limit` 1–10, default 5) for bounded discovery. For
   structured filters, pagination, or full records use API v2 directly:
   `https://clinicaltrials.gov/api/v2/studies`, with `query.cond`, `query.intr`,
   `query.term`, `query.spons`, `filter.overallStatus` (for example
   `RECRUITING`), `query.locn`, and phase filters. Count first with
   `countTotal=true`. Restrict `fields=` (for example
   `NCTId,BriefTitle,OverallStatus,Phase,Conditions,InterventionName`); full
   study JSON is very large. Write responses to a file and parse them. Fetch one record at
   `https://clinicaltrials.gov/api/v2/studies/<NCTId>`.
3. Paginate with `pageSize` and `nextPageToken`; record the exact serialized
   query, filters, fields, token/page, access time, total, returned count, and
   source-reported update metadata. Continue until no next token or a declared
   cap. Validate NCT IDs, response structure, page continuity, and truncation.
   Preserve missing fields as unknown. Retry transient failures at most twice
   with backoff; retain failed pages and mark incomplete/unavailable.
4. Apply explicit criteria and retain included and excluded NCT IDs with
   reasons. Report NCT ID, title, status, phase, condition, intervention,
   sponsor, and link. Trust server-side filters unless asked to verify detailed
   eligibility; record that limitation. Registration status and results fields
   are separate observations.
5. Save query, records, exclusions, and hashes with `$science-provenance`; use
   `$science-review` before material conclusions.

## Outputs

Return normalized query and cutoff, filter rationale, count and page status,
included/excluded NCT IDs with reasons, and a trial table with title, status,
phase, condition, intervention, sponsor, URL, and relevant claim IDs. Mark
claims supported, contradicted, inconclusive, or unavailable; include missing
fields, source dependencies, uncertainty, limitations, next falsifiable action,
and artifact paths/hashes.

## Boundaries

- Cite only NCT IDs actually returned; never invent NCT IDs, statuses, or
  eligibility criteria.
- Trial records are registry data, **not medical advice**; do not infer
  efficacy, safety, or eligibility decisions for an individual from them.
- Registration status and results reporting vary; state what the record does and
  does not contain.
- Empty, incomplete, or filtered results do not establish that no trial exists.
  Stop patient-matching conclusions at record inspection and direct individual
  eligibility questions to qualified study staff.
