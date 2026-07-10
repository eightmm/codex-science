---
name: openfda-search
description: Query the openFDA API for drugs, devices, foods, and more: adverse events, recalls, labeling, approvals, shortages, 510(k) clearances, and NDC lookups. Use for FDA safety/regulatory data. Public API, no credential needed.
license: Apache-2.0
---

# Openfda Search (Codex-native)

Codex-native adaptation of Google DeepMind's `openfda-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  source's terms of use and record the notice in provenance.
- **Network / install**: read-only public access; be polite about rate limits.
  Write large responses to a file and parse them; if you write helper code, run
  it via `uv run`, never bare `python3`. Ask before installs or large downloads.

## Endpoints

- openFDA API `https://api.fda.gov` (e.g. `/drug/event.json`, `/drug/label.json`, `/device/510k.json`)

## Workflow

1. Pick the endpoint for the domain (drug/device/food/...) and use `search=` with field:term syntax and `count=` for aggregations.
2. Restrict fields and `limit`; write large responses to a file.
- **Provenance & review**: record queries, endpoints, and cited identifiers with
  `$science-provenance`; check claims with `$science-review` before presenting.

## Boundaries

- Adverse-event reports are voluntary and not causally confirmed; report counts, not causation. Not medical advice.
- Cite only records actually returned.
