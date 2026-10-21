---
name: chebi-search
description: "Resolve chemical entities, ontology identifiers, formulae, and structures through ChEBI. Use before chemistry, metabolite, reaction, or pharmacology workflows when names or identifiers are ambiguous."
license: MIT
---

# ChEBI Search

## Decision contract

Define the chemical name/identifier and the intended entity: parent compound,
salt, mixture, isotopologue, protonation state, or stereoisomer. Preserve
ChEBI identifiers (including the source-formatted `CHEBI:<id>` where supplied),
organism/context if relevant, downstream question, and evidence cutoff. A name
match is a candidate identity, not a confirmed chemical equivalence.

## Workflow

1. Normalize the query while retaining the original text. Call
   `science_search_chebi` with a name, synonym, or ChEBI identifier (`query`,
   `limit` 1–10, default 5); it returns identifier, title, formula, SMILES, and
   URL. Public ChEBI web services are also available at
   https://www.ebi.ac.uk/chebi/backend/api/docs/. The repository connector
   is an additional discovery option, not a condition for public-source access.
2. For direct connector search, the implementation queries
   `https://www.ebi.ac.uk/chebi/backend/api/public/es_search/` with URL-encoded
   `term` and `size`. Record endpoint, exact parameters, access time, any
   release/update reported, result count, and page/continuation state. Follow
   additional pages only under a declared bound.
3. Validate HTTP status, response structure, identifier format, and returned
   values. Resolve candidates by confirming charge, formula, structure,
   stereochemistry, ontology role, and parent/child relationship before joining
   sources. Keep salts, mixtures, isotopologues, protonation states, and
   stereoisomers distinct. Record returned and excluded candidates with reasons.
4. Preserve missing formula/structure/ontology values as null. Detect malformed
   or truncated responses; retry transient failures a bounded number of times.
   Do not replace a failed structured query with a web-search guess. Cross-check
   PubChem/ChEMBL when a downstream assay or compound record matters, keeping
   source IDs and source dependencies separate.
5. Save exact query, endpoint, selected identity and response artifact hashes
   with `$science-provenance`. Use `$science-review` before material identity,
   mechanism, or pharmacology conclusions.

## Outputs

Return normalized name and identifier; candidate table with ChEBI ID, name,
formula, structure string, charge/stereo details when returned, ontology role,
parents/children, source URL, and inclusion/exclusion reason; claim IDs marked
supported/contradicted/inconclusive/unavailable; endpoint/release/access time;
identity uncertainty, limitations, and smallest next discriminating check.
Record artifacts and hashes through `$science-provenance`.

## Boundaries

Name similarity is not chemical identity. Do not silently merge salts, mixtures,
isotopologues, protonation states, or stereoisomers. Missing values and failed
queries are not negative evidence. Stop if structure/state ambiguity changes a
downstream interpretation. Respect source terms and redistribution limits;
`$science-review` is mandatory for material chemistry or pharmacology claims.

Source basis: [ChEBI public API documentation](https://www.ebi.ac.uk/chebi/backend/api/docs/).
