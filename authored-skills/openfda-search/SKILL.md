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
jurisdiction and cutoff. Select the dataset and endpoint that match the question;
openFDA reports submitted or regulatory records and does not replace clinical
judgment. Do not treat a product-name match as a confirmed identity without
checking returned identifiers and context.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Use read-only public access and follow current rate-limit guidance. Write
   large responses to a file and parse them; helper code must use `uv run`,
   never bare `python3`. Ask before installs or large downloads.
2. The direct endpoint base is `https://api.fda.gov` (for example
   `/drug/event.json`, `/drug/label.json`, `/device/510k.json`). Choose the
   endpoint, then serialize `search=` using its field:term syntax; use `count=`
   for aggregations. Repository discovery tool `science_search_openfda(query,
   limit)` exists only for drug labels and is fixture-tested experimental; it
   does not replace the broader direct API. Do not infer other dataset coverage
   from that tool.
3. Start with a bounded query and `limit`; restrict returned fields when the
   endpoint supports it. Record exact URL/parameters, access time, returned
   count, source-reported update metadata, and paging/completeness status.
   Validate record IDs and endpoint-specific fields; preserve absent/null values
   as missing. Detect malformed or truncated JSON. Retry transient errors at
   most twice with backoff; never turn API failure or an empty response into a
   negative safety finding.
4. Apply explicit inclusion/exclusion rules and retain every returned record
   and exclusion with its reason. Resolve product identity using returned
   identifiers; cite only records actually retrieved. Preserve event reports,
   label statements, recalls, and clearance records as distinct evidence types.
5. Save query, endpoint, records, exclusions, and hashes with
   `$science-provenance`; use `$science-review` before material conclusions.

## Outputs

Return normalized product/query and cutoff, exact endpoint and parameters,
reported update time, completeness status, included/excluded records with
reasons, and a table of source identifiers, record type, date, relevant fields,
URL, and claim IDs. Mark claims supported, contradicted, inconclusive, or
unavailable; include missingness, uncertainty, dependencies, limitations, next
falsifiable action, and artifact paths/hashes.

## Boundaries

- Adverse-event reports are voluntary and not causally confirmed; report counts,
  not causation. Not medical advice.
- Cite only records actually returned.
- A count is not an incidence rate without a valid denominator. A label is not
  proof of comparative effectiveness, and a 510(k) clearance is not an approval
  or clinical outcome. Do not merge these categories.
- Stop on ambiguous product identity, incomplete pages, or endpoint mismatch;
  state source gaps rather than treating them as evidence of no risk.
