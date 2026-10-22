---
name: openfda-search
description: "Query the openFDA API for drugs, devices, foods, and more: adverse events, recalls, labeling, approvals, shortages, 510(k) clearances, and NDC lookups. Use for FDA safety/regulatory data. Public API, no credential needed."
license: Apache-2.0
---

# Openfda Search (Codex-native)

Codex-native adaptation of Google DeepMind's `openfda-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Record the product/substance or device, regulatory question, intended use,
jurisdiction, and cutoff. Select the dataset and endpoint that match the
question. Assign claim status as supported, contradicted, inconclusive, or
unavailable only under the openFDA reference criteria. openFDA reports
submitted or regulatory records and does not replace clinical judgment. Do not
treat a product-name match as confirmed identity without checking returned
identifiers and context.

## Reference usage

Read [references/openfda-evidence.md](references/openfda-evidence.md) before selecting an
endpoint, interpreting adverse-event counts, combining product records, or
making safety/regulatory claims. It defines record claim semantics, product and
report dependencies, controls, sensitivity checks, and dataset limits.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, ask the
   user to review the source terms of use and wait for notice that they did so;
   record the notice in provenance before a request. Use read-only public
   access, be polite about rate limits, and follow current rate-limit guidance.
   Write large responses to a file and parse them; use `uv run`, never bare
   `python3`, for helper code. Ask before installs or large downloads.
2. Define the product/substance or device, regulatory question, intended use,
   jurisdiction, and cutoff. Select an endpoint that contains evidence for that
   question; record the endpoint choice and any incompatible question types.
3. Serialize the `search=` expression using the chosen endpoint's field:term
   syntax; use `count=` for aggregations. The endpoint base is
   `https://api.fda.gov` (for example `/drug/event.json`, `/drug/label.json`,
   `/device/510k.json`). `science_search_openfda(query, limit)` covers only drug
   labels and is fixture-tested experimental; it does not replace direct API
   access or imply broader dataset coverage.
4. Begin with a bounded query and `limit`; restrict returned fields when
   supported. Record exact URL and parameters, access time, returned count,
   update metadata, and paging/completeness status. Decide whether identity
   identifiers are sufficient before including a record.
5. Validate record IDs and endpoint-specific fields; preserve absent and null
   separately; detect malformed or truncated JSON. Retry transient failures at
   most twice with backoff. Retain failures and mark incomplete or unavailable;
   never convert API failure or an empty response into a negative safety
   finding.
6. Apply explicit inclusion and exclusion criteria and retain reasons. Resolve
   identity using returned identifiers. Keep adverse-event reports, label
   statements, recalls, approvals, shortages, and clearance records as distinct
   evidence types; classify claims using the reference criteria.
7. Run the domain controls and sensitivity checks in the reference. If plausible
   identity, endpoint, date, or query changes materially alter included
   records, counts, or interpretation, mark affected claims inconclusive and
   record the comparison.
8. Save query, endpoint, records, exclusions, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.
   Return the schema below with missingness, uncertainty, dependencies,
   limitations, next falsifiable action, and artifact paths/hashes.

## Outputs

Return one `openfda-evidence-v1` record with required fields: `question`,
`intended_use`, `normalized_product_query`, `cutoff`, `endpoint`,
`exact_parameters`, `reported_update_time`, `completeness_status`,
`included_records`, `excluded_records`, `claim_register`, `missingness`,
`source_dependencies`, `uncertainty`, `limitations`,
`next_falsifiable_action`, `artifact_paths`, and `artifact_hashes`. Each record
row includes source identifier, record type, date, relevant returned fields,
URL, and relevant claim IDs. Each claim has a stable ID and status: supported,
contradicted, inconclusive, or unavailable.

## Boundaries

- Adverse-event reports are voluntary and not causally confirmed; report counts,
  not causation. Not medical advice.
- Cite only records actually returned.
- A count is not an incidence rate without a valid denominator. A label is not
  proof of comparative effectiveness, and a 510(k) clearance is not an approval
  or clinical outcome. Do not merge these categories.
- Stop on ambiguous product identity, incomplete pages, or endpoint mismatch;
  state source gaps rather than treating them as evidence of no risk.

Preserve exact requests, records, exclusions, and hashes with
`$science-provenance`; obtain `$science-review` for material conclusions.
