---
name: clinical-trials-search
description: Search ClinicalTrials.gov (API v2) for trials by condition, intervention, status, phase, location, or sponsor; fetch a trial by NCT ID; check eligibility; and count trials. Use for trial discovery, pipeline/portfolio analysis, or patient-matching context. Public API, no credential needed.
license: Apache-2.0
---

# ClinicalTrials.gov Search (Codex-native)

Codex-native adaptation of Google DeepMind's `clinical-trials-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public ClinicalTrials.gov REST API v2 directly.

## Gates (ask before proceeding)

- **Terms notice**: on first use, tell the user to review the ClinicalTrials.gov
  terms (https://clinicaltrials.gov/) and record the notice in provenance.
- **Network / install**: read-only public HTTP; be polite about rate limits. If
  you write helper code, run it via `uv run`, never bare `python3`.

## Workflow

1. **Endpoint**: `https://clinicaltrials.gov/api/v2/studies` with query params —
   `query.cond` (condition), `query.intr` (intervention), `query.term`,
   `query.spons` (sponsor), `filter.overallStatus` (e.g. `RECRUITING`),
   `query.locn`, and phase filters.
2. **Count first**: request the total (`countTotal=true`) before pulling records,
   to gauge volume.
3. **Restrict fields**: always pass `fields=` (e.g.
   `NCTId,BriefTitle,OverallStatus,Phase,Conditions,InterventionName`) — full
   study JSON is very large. Write responses to a file and parse them.
4. **Paginate** large sets with `pageSize` + `nextPageToken`.
5. **Fetch one trial**: `https://clinicaltrials.gov/api/v2/studies/<NCTId>` for
   full protocol, eligibility, outcomes, and locations.
6. **Report** trials with NCT ID, title, status, phase, condition, intervention,
   and sponsor; link each. Trust the server-side filters unless asked to verify
   detailed eligibility.
7. **Provenance & review**: record queries and cited NCT IDs with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Cite only NCT IDs actually returned; never invent NCT IDs, statuses, or
  eligibility criteria.
- Trial records are registry data, **not medical advice**; do not infer efficacy,
  safety, or eligibility decisions for an individual from them.
- Registration status and results reporting vary; state what the record does and
  does not contain.
