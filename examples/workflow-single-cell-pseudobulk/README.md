# Synthetic single-cell pseudobulk fixtures

Every input, negative case and expected result here is a redistributable synthetic software fixture, not a real cohort or biological finding. The generator used Python `random.Random(20261103)` for bounded per-cell integer jitter. There are eight independent fixture donors, four per condition, balanced over two batches, with three T cells and one rare-labelled cell per donor. Four additional cells exercise supplied doublet, low-count, high-mitochondrial and zero-count exclusions. Each regular cell has 1000 counts.

`EFFECT` has a planted donor-level condition contrast; `BATCH` has a planted batch effect balanced across conditions; `NULL` is a negative control, and `ZERO` fails the prespecified gene-detection threshold. `MARK` supports synthetic cell-type provenance and is excluded from condition testing. `MT` supplies the mitochondrial count control. The label evidence and observation records are synthetic assertions for validator testing, never scientific support for a real cell type or mechanism.

Run from the repository:

```sh
python3 scripts/validate_single_cell_pseudobulk_pack.py examples/workflow-single-cell-pseudobulk/pack.json
PYTHONPATH=src:tests python3 -m unittest test_workflow_single_cell_pseudobulk_pack
```

The read-only CLI writes JSON to stdout, has no `--output` option and never modifies these fixtures. `pack.json` binds design, counts, collection, label evidence, study outputs and claims by path and hash. `expected.json` records the complete expected result, including excluded cells, eight underfilled rare-cell pairs, the excluded ZERO gene, input identities and unavailable review. Only EFFECT passes BH alpha 0.05 (q approximately 0.000154265); BATCH and NULL remain nonsignificant. The reference reuses the repository's stdlib Welch/BH helpers and creates no runtime records or checkpoint.

`negative-cases.json` indexes all 24 frozen cases and their required refusal codes. The focused test module drives every case through the public entry point. Cases cover cell pseudoreplication, repeated donors and invalid donor adjustment, batch confounding, insufficient donors, absent marker evidence, circular labels, post-result QC/aggregation changes, silently included underfilled units, missing/selective correction, namespace/annotation mismatches, causal/trajectory/fate/clinical/physical claims, review/computed support, unavailable-as-negative evidence and falsely external evidence aliasing a study output. All referenced negative inputs remain labelled fixtures.

Additional runtime tests refuse binding, affinity, inhibition, activation and mechanism wording for positive claims, including "Compound A binds target B with high affinity". The wording filter is case-insensitive and uses whole-word families; statistical association remains the only admitted inference. If a counts record declares `seed`, it must be a JSON integer, never a boolean or float. Omitted, zero and negative integer seeds remain accepted within the existing JSON magnitude bound.

These records use seven pack-local schemas listed in the skill's `references/stages.md`. They are ordinary artifacts, with separate coordinator-owned claim-register entries. One coordinator checkpoint uses the five ordered stage IDs. `$science-review` owns rigor, independence and any receipt. Approval is never truth, numerical agreement never physical validity, and absent records never negative evidence. No edgeR, DESeq2, network, remote or GPU execution is part of these fixtures.

Two concurrent validator calls only read snapshots and print their own outputs. Killing a call leaves these files unchanged and creates no partial result; callers choose how to preserve stdout. Input edits during validation produce a labelled refusal at the final identity/hash recheck. The coordinator preserves failed controls, null results and unsuccessful attempts outside this immutable example.
