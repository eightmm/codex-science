# Synthetic offline example

All sequences and scores are author-created synthetic CC0 fixture data. No model
or assay was run. From the repository root:

```sh
python3 scripts/analyze_protein_variants.py examples/protein-variant-evaluation/input.json
PYTHONPATH=src python3 -m unittest discover -s tests -p test_protein_variant_workflow.py
```

The first command reproduces expected-analysis.json: five variants, four paired
scores, tie-aware model Spearman 1 and negative edit-count baseline correlation
about 0.94868. Lower supplied toy model scores and higher toy assay scores agree.
The failed fifth score remains in the output. Numbered residue 11 maps to index
zero with offset 10. The WT is an explicit empty edit list. This demonstrates
analysis semantics only; candidate status stays unreviewed.

Negative cases live in the focused tests and bounded benchmark tasks: WT/offset,
indels, no-op and overlapping edits, duplicate IDs/sequences, exact/homology split
leakage, invalid direction/units/numeric values, constants, missingness and failed
essential controls. Register inputs, analysis, command/log, environment and
independent review as ordinary hashed run artifacts for a real dossier; this
fixture has no review receipt or real model execution record.
