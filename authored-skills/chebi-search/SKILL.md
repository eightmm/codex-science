---
name: chebi-search
description: "Resolve chemical entities, ontology identifiers, formulae, and structures through ChEBI. Use before chemistry, metabolite, reaction, or pharmacology workflows when names or identifiers are ambiguous."
license: MIT
---

# ChEBI Search

1. Call `science_search_chebi` with a name, synonym, or ChEBI identifier.
2. Confirm charge, formula, structure, stereochemistry, ontology role, and parent/child relationship before joining sources.
3. Keep salts, mixtures, isotopologues, protonation states, and stereoisomers distinct.
4. Record identifier, endpoint, release/access time, and selected structure with `$science-provenance`.

Name similarity is not chemical identity. Cross-check PubChem/ChEMBL when a downstream assay or compound record matters.

Source basis: [ChEBI web services](https://www.ebi.ac.uk/chebi/webServicesForward.do).
