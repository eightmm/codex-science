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

Record the question, condition and intervention concepts, geography and time
scope, intended use, recruitment/status cutoff, and whether the task is
aggregate discovery or individual context. Use NCT IDs as canonical registry
identifiers. Assign claim status as supported, contradicted, inconclusive, or
unavailable only under the criteria in the clinical reference. A search result
cannot determine personal eligibility or establish intervention benefit.

## Reference usage

Read [references/clinical-trial-evidence.md](references/clinical-trial-evidence.md) before
query design, eligibility-context work, count interpretation, or any claim about
trial status, results, completeness, or evidence independence. It defines
registry claim semantics, dependency checks, controls, sensitivity checks, and
the limits of registry records.

## Workflow

1. **Gates (ask before proceeding).** On first use, ask the user to review
   ClinicalTrials.gov terms (`https://clinicaltrials.gov/`) and wait for the
   user's notice that they reviewed them; record that notice in provenance
   before making a request. Use read-only HTTP, be polite about rate limits,
   and use `uv run` for helper code, never bare `python3`.
2. Define the question and intended use. If it concerns an individual, limit
   the task to locating records for qualified study staff; record the explicit
   population, geography/time scope, cutoff, and out-of-scope decisions.
3. Select condition, intervention, sponsor, location, status, and phase terms.
   Use `science_search_clinical_trials(query, limit)` for bounded discovery
   (`query` up to 500 characters; `limit` 1–10, default 5); use API v2 directly
   at `https://clinicaltrials.gov/api/v2/studies` for structured filters,
   pagination, or full records. Available filters include `query.cond`,
   `query.intr`, `query.term`, `query.spons`, `filter.overallStatus` (for
   example `RECRUITING`), `query.locn`, and phase filters. Record the exact
   serialized query and why each filter fits the question.
4. Count first with `countTotal=true`. Request only needed `fields=` (for example
   `NCTId,BriefTitle,OverallStatus,Phase,Conditions,InterventionName`); full
   study JSON is very large, so write responses to a file and parse them. Fetch
   a record at `https://clinicaltrials.gov/api/v2/studies/<NCTId>` only when
   details are needed. Record endpoint, fields, access time, and returned total.
5. Paginate with `pageSize` and `nextPageToken`. Continue until no token or a
   declared cap; validate NCT IDs, response structure, page continuity, and
   truncation. Retry transient failures at most twice with backoff. Retain failed
   pages and mark the retrieval incomplete or unavailable; preserve missing
   fields as unknown. Record tokens/pages, counts, and source update metadata.
6. Apply explicit inclusion and exclusion criteria to retrieved records. Keep
   included and excluded NCT IDs with reasons; report title, status, phase,
   condition, intervention, sponsor, and link. Separate registration status
   from results reporting and use the reference criteria for claim status. Trust
   server-side filters unless detailed eligibility verification is requested;
   record that limitation, and when a claim depends on completeness run the
   filtered-versus-unfiltered control in step 7.
7. Run domain controls and sensitivity checks from the reference. If plausible
   term, filter, cutoff, or paging changes alter the result set materially,
   mark affected claims inconclusive and record the comparison; do not treat an
   empty or filtered result as proof no trial exists.
8. Save query, records, exclusions, completeness, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.
   Return the schema below, including uncertainty, dependencies, limitations,
   next falsifiable action, and artifact paths/hashes.

## Outputs

Return one `clinical-trial-evidence-v1` record with required fields: `question`,
`intended_use`, `normalized_query`, `cutoff`, `filter_rationale`,
`retrieval_ledger`, `count_and_page_status`, `included_trials`,
`excluded_trials`, `claim_register`, `missing_fields`, `source_dependencies`,
`uncertainty`, `limitations`, `next_falsifiable_action`, `artifact_paths`, and
`artifact_hashes`. Each trial row includes NCT ID, title, status, phase,
condition, intervention, sponsor, URL, and relevant claim IDs. Each claim has a
stable ID and status: supported, contradicted, inconclusive, or unavailable.

## Boundaries

- Cite only NCT IDs actually returned; never invent NCT IDs, statuses, or
  eligibility criteria.
- Trial records are registry data, **not medical advice**; do not infer
  efficacy, safety, or eligibility decisions for an individual from them.
- Registration status and results fields are separate observations; state what
  the record contains and omits.
- Empty, incomplete, or filtered results do not establish that no trial exists.
  Stop patient-matching conclusions at record inspection and direct individual
  eligibility questions to qualified study staff.

Preserve the notice, query, filters, fields, pages, records, exclusions, and
hashes with `$science-provenance`; obtain `$science-review` for material claims.
