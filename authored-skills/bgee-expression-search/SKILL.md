---
name: bgee-expression-search
description: "Find ontology-aware healthy wild-type gene expression context with Bgee. Use for cross-species, anatomical, developmental-stage, or baseline-expression questions."
license: MIT
---

# Bgee Expression Search

1. Normalize the gene first, then call `science_search_bgee` with the canonical symbol.
2. Confirm species and gene ID before retrieving anatomical or developmental expression evidence.
3. Preserve evidence type, anatomical ontology term, developmental stage, species, release, and access time.
4. Reconcile healthy baseline evidence with GTEx/HPA or disease datasets using `$cx-expression-cell-context`.

Do not treat absence from one Bgee result as evidence of no expression. Do not merge orthologs or developmental stages without an explicit mapping.

Record selected evidence and release with `$science-provenance`; use `$science-review` for cross-species claims.

Source basis: [Bgee API](https://www.bgee.org/support/tutorial-api).
