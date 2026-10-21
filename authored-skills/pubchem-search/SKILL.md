---
name: pubchem-search
description: "Query PubChem by name, CID, or SMILES; retrieve properties; run similarity/substructure searches; and get bioactivity. Use for cheminformatics on a specific chemical, drug, or molecule. Public PUG-REST API, no credential needed."
license: Apache-2.0
---

# Pubchem Search (Codex-native)

Codex-native adaptation of Google DeepMind's `pubchem-database` skill
([science-skills](https://github.com/google-deepmind/science-skills), Apache-2.0).
Uses the public API directly through Codex's own tools.

## Decision contract

Specify the compound/query and goal (identity, properties, similarity,
substructure, or bioactivity), preserve the original name/CID/SMILES and
stereochemical intent, and set an evidence cutoff. Resolve names to candidate
CIDs before comparing properties. Treat each CID as a distinct source record;
salts and stereoisomers can have separate identifiers.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; run helper code via `uv run`, never bare `python3`.
   Ask before installs or large downloads.
2. Optionally resolve names with `science_search_pubchem` (`query`, `limit`
   1–10, default 5; it returns CID, title, formula, molecular weight, SMILES,
   and URL). Direct PUG-REST base is
   `https://pubchem.ncbi.nlm.nih.gov/rest/pug`. Resolve name/SMILES to CIDs
   (`/compound/name/<name>/cids/JSON`), then fetch properties
   (`/compound/cid/<cid>/property/<props>/JSON`). Preserve exact serialized
   query, selected properties, endpoint, access time, response-reported update,
   result count, and page/continuation state.
3. For similarity/substructure use `/compound/fastsimilarity_2d` or
   `/fastsubstructure` endpoints. State the input structure, search mode, and
   filters before inspecting results; preserve returned thresholds and match
   identifiers. Bound result count and pagination.
4. Validate HTTP status, JSON shape, CIDs, property presence, and completion.
   Preserve multiple returned CIDs and exclusions with reasons. Keep missing
   properties null. Detect malformed or truncated responses; use bounded retries
   for transient failures. Do not replace a failed PUG-REST query with an
   unstructured web-search guess. Treat no results as query-specific absence,
   not proof that no compound or activity exists.
5. Report CID and canonical/isomeric SMILES as returned, plus requested
   properties and source URL. Record exact query, endpoint, response/page state,
   and artifact hashes with `$science-provenance`; use `$science-review` before
   material chemical identity, activity, or mechanism conclusions.

## Outputs

Return normalized query and structure intent; candidate table with CID, title,
formula, molecular weight, canonical/isomeric SMILES, requested properties,
source URL, and inclusion/exclusion reason; claim IDs marked
supported/contradicted/inconclusive/unavailable; endpoint/access-time details;
identity and measurement uncertainty, limitations, and smallest next identity
or assay check. Preserve response artifacts and hashes via `$science-provenance`.

## Boundaries

- Report the CID and canonical/isomeric SMILES; a name can map to multiple CIDs
  (salts, stereoisomers).
- Cite only CIDs actually returned; never invent structures or properties.
- A computed or deposited property is not by itself experimental activity,
  efficacy, safety, or clinical guidance. Stop if stereochemical or salt-state
  ambiguity changes the result. Preserve missingness and source failures.
- Respect source terms and redistribution limits. `$science-review` is mandatory
  for material chemical identity, bioactivity, or mechanism claims.
