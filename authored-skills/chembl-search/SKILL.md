---
name: chembl-search
description: "Query the ChEMBL database for bioactive molecules, drug targets, bioactivity measurements (IC50/Ki/EC50), approved drugs, and mechanisms. Use when the user asks about compounds, targets, potency values, or drug mechanisms. Public REST API, no credential needed."
license: Apache-2.0
---

# ChEMBL Database Query (Codex-native)

Codex-native adaptation of Google DeepMind's `chembl-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public ChEMBL REST API directly through Codex's own tools.

## Decision contract

Specify the compound/target and question (identity, activity, mechanism, or
indication), species, assay/evidence cutoff, and requested endpoints. Preserve
ChEMBL molecule/target/activity identifiers and distinguish a target record
from its UniProt component. For activity comparisons, define compatible assay,
target, organism, type, units, and confidence criteria before interpreting.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the ChEMBL terms
   (https://chembl.gitbook.io/chembl-interface-documentation/about) and record
   the notice in provenance. Public read-only HTTP: be polite about rate limits.
   Write responses to a file and parse them; run helper code via `uv run`, never
   bare `python3`. Ask before installs or large downloads.
2. Search molecules with optional `science_search_chembl` (`query`, `limit`
   1–10, default 5; returns ChEMBL ID, title, canonical SMILES, URL). Direct API
   base: `https://www.ebi.ac.uk/chembl/api/data/` (append `?format=json`).
   Endpoints: `molecule` — compounds by ChEMBL ID, name, or structure;
   `target` — drug targets (link to a UniProt accession via `target_components`);
   `activity` — bioactivity measurements for a molecule/target pair;
   `mechanism` / `drug_indication` — mechanism of action and indications.
3. Resolve identifiers first (compound name to ChEMBL ID; gene/protein to target
   via `$cx-uniprot-search` then `target` search). Record exact URL-encoded
   query, filters, access time, response-reported release/update, pagination
   links and pages, and result count. Write large JSON to a file and parse with
   `jq` or a short `uv run` script. Responses are often wrapped in endpoint
   lists such as `molecules` or `activities`; validate shape and completeness.
4. Bound page traversal and retries. Record returned and excluded records with
   reasons; preserve null values and unmapped inputs. Detect malformed or
   truncated responses. A failed endpoint is unavailable, not evidence of no
   activity. Keep raw record IDs and assay provenance for every measurement.
5. Report `standard_type` (IC50, Ki, EC50, …), `standard_value`, and
   `standard_units` together. A value without type/unit is uninterpretable.
   Prefer `pchembl_value` for cross-assay comparison, but it remains
   assay-dependent. Do not average or compare across different assays, targets,
   or organisms as if equivalent; check `assay_type`/confidence and target.
   Separate strong evidence from single low-confidence assays.
6. Record queries, endpoints, cited IDs and response artifacts with
   `$science-provenance`; check material bioactivity/mechanism claims with
   `$science-review` before presentation.

## Outputs

Return normalized compound and target IDs; an evidence table with ChEMBL IDs,
assay IDs, target/species, standard type/value/units, pChEMBL if returned,
assay type/confidence, URL, and inclusion/exclusion reason; claim IDs marked
supported/contradicted/inconclusive/unavailable; query/release/access time;
uncertainty, assay heterogeneity and limitations; and smallest falsifiable
follow-up. Save artifacts and hashes with `$science-provenance`.

## Boundaries

- Cite only ChEMBL IDs and values actually returned; never invent IDs, potencies,
  or units.
- Bioactivity data are heterogeneous and assay-dependent; state confidence and
  never present them as clinical or dosing guidance.
- Approved-drug/indication data describe the record, not medical advice.
- Stop when identity, species, assay, or unit ambiguity changes interpretation.
  Preserve failed/truncated retrieval as unavailable. Respect ChEMBL terms and
  redistribution limits. `$science-review` is mandatory for material potency,
  mechanism, or indication conclusions.
