---
name: rnacentral-search
description: "Resolve non-coding RNA identifiers, sequences, types, and cross-references through RNAcentral. Use for RNA annotation, accession normalization, ncRNA, or sequence-context research."
license: MIT
---

# RNAcentral Search

1. Call `science_search_rnacentral` with an RNA name, type, description, or accession.
2. Verify active status, sequence, molecule type, organism, database cross-references, and release.
3. Preserve strand, alphabet, sequence version, length, and source accession before downstream analysis.
4. Record query, URS identifier, release/access time, and selected cross-references.

Do not merge sequences or annotations solely by description. Predicted function is not experimental validation.

Store sequence and cross-reference provenance with `$science-provenance`; run `$science-review` for functional claims.

Source basis: [RNAcentral API](https://rnacentral.org/api).
