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

Specify original compound/query, goal (identity, properties, similarity,
substructure, or bioactivity), stereochemical intent, evidence cutoff, and
claim IDs. Separate deposited Substance records (SIDs), standardized Compound
records (CIDs), and BioAssay records (AIDs). A deposited record or assay result
does not by itself validate a chemical property, activity, or mechanism. State
the minimum support, controls, uncertainty, and scope for each claim before
retrieval. Treat salts and stereoisomers as distinct unless an explicit
structure-based rule justifies equivalence.

## Reference usage

- Read [references/pubchem-records-and-assays.md](references/pubchem-records-and-assays.md)
  before interpreting SIDs, CIDs, AIDs, depositor provenance, or assay outcomes.
- Read [references/chemical-identity-and-sensitivity.md](references/chemical-identity-and-sensitivity.md)
  before structure matching, normalization, property aggregation, or changing
  search/activity thresholds.

## Workflow

1. **Gates (ask before proceeding).** On first use in a workspace, tell the
   user to review the source's terms of use and record the notice in provenance.
   Public read-only access: be polite about rate limits. Write large responses
   to a file and parse them; run helper code via `uv run`, never bare `python3`.
   Ask before installs or large downloads. Record gate completion.
2. Assign claim IDs and preserve the original name/CID/SMILES and stereochemical
   intent. Optionally use `science_search_pubchem` (`query`, `limit` 1–10,
   default 5; returns CID, title, formula, molecular weight, SMILES, and URL).
   Direct PUG-REST base: `https://pubchem.ncbi.nlm.nih.gov/rest/pug`.
   Resolve names/SMILES to candidate CIDs before property comparison; record
   candidate selection and exact serialized query.
3. Retrieve requested records with `/compound/name/<name>/cids/JSON`,
   `/compound/cid/<cid>/property/<props>/JSON`, or appropriate substance and
   assay endpoints. For similarity/substructure, use `/compound/fastsimilarity_2d`
   or `/fastsubstructure`, state input structure, mode, filters, and declared
   result/page bound. Record endpoint, access time, update/release if reported,
   properties, thresholds, pages, and result count.
4. Verify HTTP status, JSON shape, identifiers, property presence, and
   completion. Read [references/pubchem-records-and-assays.md](references/pubchem-records-and-assays.md)
   to preserve depositor attribution and source relationships; keep each SID,
   CID, AID, and depositor distinct. Preserve multiple CIDs, null properties,
   and exclusions with reasons.
5. Run a known reference-compound check and a decoy name-collision check.
   Confirm structure identity using available InChI/InChIKey, connectivity,
   charge, salt, tautomer, and stereochemistry evidence before joining records.
   Record whether each result is deposited, standardized, computed, measured,
   or an interpretation.
6. Vary structure standardization, similarity/activity threshold, unit
   conversion, and any aggregation choice. Record record-set and status changes.
   Retry transient failures only within a bound; malformed/truncated or failed
   responses are unavailable, not negative evidence. Do not replace a failed
   PUG-REST query with an unstructured web-search guess.
7. Return the required `pubchem-chemical-evidence-v1` fields; preserve query,
   response/page state, and artifact hashes with `$science-provenance`. Use
   `$science-review` before material chemical identity, activity, or mechanism
   conclusions, and record the smallest next identity/assay check.

## Outputs

Return one `pubchem-chemical-evidence-v1` record with: claim identifier
(`claim_id`); claim class/status (`claim_class`, `status`); original and
normalized query/structure intent (`query_identity`); CID/SID/AID and depositor
IDs (`record_ids`); source release/update, exact endpoint/query, access time,
page state, and result count (`source_receipt`); property/activity values with
reported units and measurement or computation status (`observations`);
included/excluded records and reasons (`record_decisions`); shared depositor,
assay, source, or propagated-record dependencies (`dependencies`); reference
and decoy outcomes (`controls`); normalization, threshold, unit, and
aggregation variants (`sensitivity`); uncertainty, applicability domain,
limitations, next check, artifact paths and hashes (`uncertainty`,
`applicability`, `limitations`, `next_action`, `artifacts`). Use status values
supported, contradicted, inconclusive, unavailable, or withdrawn.

## Boundaries

- A name can map to multiple CIDs, and each SID is depositor-provided while
  CIDs are derived standardized records. Do not conflate Substance, Compound,
  and BioAssay records or hide depositor provenance.
- Report CID and canonical/isomeric SMILES only as returned. Never invent
  structures or properties. A computed or deposited property is not by itself
  experimental activity, efficacy, safety, or clinical guidance.
- Preserve missing properties as null, failed queries as unavailable, and
  query-specific no-results as limited negative evidence rather than proof of
  global absence. Stop if stereochemical or salt-state ambiguity changes the
  result; respect terms and redistribution limits.
- `$science-review` is mandatory for material chemical identity, bioactivity,
  or mechanism claims.
