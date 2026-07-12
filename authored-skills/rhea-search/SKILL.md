---
name: rhea-search
description: "Search curated biochemical reactions and participants through Rhea. Use for enzyme, pathway, metabolite, reaction-direction, or mechanism context."
license: MIT
---

# Rhea Search

1. Normalize participants with ChEBI, then call `science_search_rhea` using reaction, enzyme, or participant terms.
2. Preserve Rhea ID, direction, participant IDs, stoichiometry, status, and source release.
3. Cross-check enzyme/protein claims with UniProt and pathway claims with Reactome.
4. Record query and selected reaction identifiers with `$science-provenance`.

Do not infer kinetics, cellular flux, thermodynamic favorability, or tissue activity from a curated reaction equation.

Source basis: [Rhea REST access](https://www.rhea-db.org/help/download).
