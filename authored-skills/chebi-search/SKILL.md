---
name: chebi-search
description: "Resolve chemical entities, ontology identifiers, formulae, and structures through ChEBI. Use before chemistry, metabolite, reaction, or pharmacology workflows when names or identifiers are ambiguous."
license: MIT
---

# ChEBI Search

## Decision contract

Define the original chemical name/identifier, intended entity (parent, salt,
mixture, isotopologue, protonation state, stereoisomer, or class), context,
downstream question, and evidence cutoff. Preserve ChEBI identifiers including
source-formatted `CHEBI:<id>`, assign claim IDs, and separate a curated ontology
record/role from a measured property or experimentally validated mechanism. A
name match or ontology relation alone does not establish chemical equivalence,
activity, or mechanism. State which ontology relation or identity evidence is
needed and what ambiguity would stop a join.

## Reference usage

- Read [references/chebi-identity-and-ontology.md](references/chebi-identity-and-ontology.md)
  before interpreting entity classes, roles, hierarchy, parent/child relations,
  or mapping names to structures.
- Read [references/chemical-identity-and-sensitivity.md](references/chemical-identity-and-sensitivity.md)
  before normalizing structures, joining another chemistry source, or assessing
  threshold/aggregation sensitivity.

## Workflow

1. Normalize the query while retaining the original text. Call
   `science_search_chebi` with a name, synonym, or ChEBI identifier (`query`,
   `limit` 1–10, default 5); it returns identifier, title, formula, SMILES,
   and URL. Public ChEBI web services are also available at
   https://www.ebi.ac.uk/chebi/backend/api/docs/. The repository connector is an
   additional discovery option, not a condition for public-source access.
   Record claim IDs, input, and identity-selection rule.
2. For direct connector search, use
   `https://www.ebi.ac.uk/chebi/backend/api/public/es_search/` with URL-encoded
   `term` and `size`. Bound page traversal. Record endpoint, exact parameters,
   access time, release/update if reported, result count, and continuation state.
3. Verify HTTP status, response structure, identifier format, and returned
   values. Read [references/chebi-identity-and-ontology.md](references/chebi-identity-and-ontology.md)
   to distinguish chemical class, parent/child structure, and `has role`
   assertions. Confirm charge, formula, structure, stereochemistry, and
   ontology role before joining candidates; record inclusions/exclusions.
4. Preserve absent formula, structure, and ontology values as null. Keep salts,
   mixtures, isotopologues, protonation states, and stereoisomers distinct.
   Detect malformed/truncated responses; retry transient failures a bounded
   number of times. A failed structured query is unavailable, not a negative
   result or reason to substitute a web-search guess.
5. Run a known reference-compound check and a decoy name-collision check. Check
   that the selected entry's entity type, formula/structure, charge/stereo
   details, and ontology role agree with the intended use; record each control.
6. Vary name/synonym choice, structure normalization, parent-versus-child
   inclusion, and any downstream activity threshold, unit conversion, or
   aggregation. Record changed candidates and claim status. Cross-check
   PubChem/ChEMBL only when a downstream assay or compound record matters, and
   keep source IDs and dependencies separate.
7. Return the required `chebi-entity-evidence-v1` fields and save exact query,
   selected identity, and response artifact hashes with `$science-provenance`.
   Use `$science-review` before material identity, mechanism, or pharmacology
   conclusions; record uncertainty and the smallest next discriminating check.

## Outputs

Return one `chebi-entity-evidence-v1` record with: claim identifier and
class/status (`claim_id`, `claim_class`, `status`); original and normalized
query (`query_identity`); ChEBI ID, entry name, formula, structure, charge,
stereochemistry, entity type and ontology relations (`entity`); source release,
exact endpoint/parameters, access time, page state, and result count
(`source_receipt`); included/excluded candidates with reasons
(`record_decisions`); cross-source IDs and shared source/record dependencies
(`dependencies`); reference and decoy outcomes (`controls`); name/structure,
hierarchy, threshold, unit, and aggregation variants (`sensitivity`);
uncertainty, applicability domain, limitations, next discriminating action,
artifact paths and hashes (`uncertainty`, `applicability`, `limitations`,
`next_action`, `artifacts`). Use status values supported, contradicted,
inconclusive, unavailable, or withdrawn.

## Boundaries

- Name similarity is not chemical identity. Do not silently merge salts,
  mixtures, isotopologues, protonation states, stereoisomers, or distinct
  ontology classes. Record the source-formatted `CHEBI:<id>` when supplied.
- Curated ontology roles classify known entity relationships or behavior; they
  are not direct assay measurements or proof of mechanism in a particular
  species, tissue, dose, or experimental context.
- Missing values and failed queries are not negative evidence. Stop if
  structure/state ambiguity changes a downstream interpretation. Respect source
  terms and redistribution limits; `$science-review` is mandatory for material
  chemistry or pharmacology claims.

Source basis: [ChEBI public API documentation](https://www.ebi.ac.uk/chebi/backend/api/docs/).
