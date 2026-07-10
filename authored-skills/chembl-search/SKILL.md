---
name: chembl-search
description: "Query the ChEMBL database for bioactive molecules, drug targets, bioactivity measurements (IC50/Ki/EC50), approved drugs, and mechanisms. Use when the user asks about compounds, targets, potency values, or drug mechanisms. Public REST API, no credential needed."
license: Apache-2.0
---

# ChEMBL Database Query (Codex-native)

Codex-native adaptation of Google DeepMind's `chembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public ChEMBL REST API directly through Codex's own tools.

## Gates (ask before proceeding)

- **Terms notice**: on first use in a workspace, tell the user to review the
  ChEMBL terms
  (https://chembl.gitbook.io/chembl-interface-documentation/about) and record the
  notice in provenance.
- **Network / install**: read-only public HTTP. Be polite about rate limits.
  Write responses to a file and parse them; if you write helper code, run it via
  `uv run`, never bare `python3`.

## Workflow

Search molecules first with `science_search_chembl`; use the direct API below
for target, activity, mechanism, and indication records.

1. **Choose the endpoint** on `https://www.ebi.ac.uk/chembl/api/data/` (append
   `?format=json`):
   - `molecule` — compounds by ChEMBL ID, name, or structure.
   - `target` — drug targets (link to a UniProt accession via
     `target_components`).
   - `activity` — bioactivity measurements for a molecule/target pair.
   - `mechanism` / `drug_indication` — mechanism of action and indications.
2. **Resolve identifiers first** (e.g. compound name → ChEMBL ID, gene/protein →
   target via `$cx-uniprot-search` then `target` search) before pulling
   activities.
3. **Run the query**, writing JSON to a file rather than dumping large payloads
   to stdout; parse with `jq` or a short script. Results are usually wrapped in a
   list keyed by the endpoint (e.g. `molecules`, `activities`).
4. **Interpret bioactivity correctly** (this is where errors happen):
   - Report `standard_type` (IC50, Ki, EC50, …), `standard_value`, and
     `standard_units` together — a value is meaningless without its type/unit.
   - Prefer `pchembl_value` for cross-assay comparison; still note it is
     assay-dependent.
   - Do not average or compare across different assays, targets, or organisms as
     if equivalent; check `assay_type`/confidence and target.
5. **Report** compounds/targets with ChEMBL IDs, the requested measurements with
   units, and links; separate strong evidence from single low-confidence assays.
6. **Provenance & review**: record queries, endpoints, and cited ChEMBL IDs with
   `$science-provenance`; check claims with `$science-review`.

## Boundaries

- Cite only ChEMBL IDs and values actually returned; never invent IDs, potencies,
  or units.
- Bioactivity data are heterogeneous and assay-dependent; state confidence and
  never present them as clinical or dosing guidance.
- Approved-drug/indication data describe the record, not medical advice.
