# Single-cell pseudobulk stages and pack-local records

All checked-in inputs and outputs are synthetic software fixtures. This reference constrains procedure and is not biological evidence. There is no new global schema, engine, claim key or receipt key.

## Invocation and identities

Run `python3 scripts/validate_single_cell_pseudobulk_pack.py examples/workflow-single-cell-pseudobulk/pack.json` from the repository. The public Python entry point is `codex_science.single_cell_pseudobulk_pack.validate_single_cell_pseudobulk_pack(path)`. Both compute and validate; neither writes a file. The CLI prints `single-cell-pseudobulk-result-v1` JSON on success (exit 0), and a labelled error on stderr with exit 2 on refusal. It has one positional `pack` argument and no `--output` option. `welch_test(first, second, minimum=2)` is the small numerical reference; effects are second condition minus first. BH and the two-sided Student-t calculation reuse the existing bulk-expression helpers.

Every artifact identity is `{path, sha256}` with a lowercase SHA-256 of the actual bytes. Paths must be canonical POSIX bundle-relative names: no absolute or drive paths, backslashes, `..`, redundant separators, `.` components or symlinked components. The entry pack may be selected by an ordinary local path, but symlinks in that path are refused too. Missing files are an unavailable-input refusal, never a negative observation.

The reader checks lstat identity, opens with O_NONBLOCK and O_NOFOLLOW, checks descriptor type and size, and reads at most 64 MiB plus one byte. It refuses nonregular, swapped, growing and oversized files. Each artifact is parsed from one cached byte snapshot; final separate reads recheck hashes and file identities, including the entry pack. Concurrent replacement is refused even if the replacement has identical content. There is no lock or cross-file transaction: the final recheck detects changes observed during the run, not edits made after validation returns. Two concurrent calls write nothing; killing either leaves no output, partial file or receipt.

The aggregate raw-byte budget is `MAX_TOTAL_BYTES = 256 * 1024 * 1024`
(256 MiB), checked against each new artifact's descriptor size before reading.
The aggregate JSON-value allowance is `MAX_TOTAL_NODES = 4000000`: before parsing,
count the root, every comma and the first value of every nonempty container with
a non-consuming lookahead. This conservative upper bound also counts matching
bytes inside strings. Equality passes; exhausted budgets refuse further unique
artifacts. Snapshots are keyed by `(st_dev, st_ino)`, so hardlink aliases share
one initial read, hash and parse and consume each budget once. Path identities
remain separate for hash checks and reporting. Final checks re-read each unique
inode once and check every referenced path; they do not consume the budgets again.
Byte or JSON-value exhaustion is `input-limit`. The absolute bundle directory is
walked component by component with `O_DIRECTORY|O_NOFOLLOW`, checking each opened
directory against its pre-open lstat device/inode. Its final descriptor remains
pinned for every artifact read. Artifact ancestors have the same identity checks;
the root is checked again before and after the final artifact checks. Descriptors
close on success, refusal or interruption.

UTF-8 JSON requires an object root. Nested duplicate keys, NaN/Infinity, numbers with absolute magnitude above 1e100, and container depth above 64 (root depth zero) are refused. Recursion and malformed values become labelled ValueErrors. Integer fields require JSON integers and reject bools, all floats (including integral values such as 3.0) and strings. A hash is not a signature or evidence of historical preregistration.

## Pack-local schemas

All records require the named `schema` and `fixture: true`. These shapes are local to this pack and registered only as ordinary artifacts; separate existing claim-register entries carry adjudication. Pack, input-map, identity, specification, QC, label and claim objects refuse unknown fields, including unsupported independence or preregistration assertions. An external origin still requires the source checks below.

| Schema | Required content |
| --- | --- |
| `single-cell-pseudobulk-pack-v1` | `stages` in the exact five-stage order; `inputs` identities named `design`, `counts`, `gene_sets`, `labels`; `frozen_spec`, `analysis_spec`, canonical `frozen_sha256`, `frozen_design_sha256` equal to the design file hash, `freeze_before_results: true`, boolean `exploratory`, ordered `included_units` objects with `unit_id` and `cell_type`, `study_outputs` identities, and `claims`. |
| `single-cell-pseudobulk-design-v1` | Shared identity fields below; `biological_units` with unique `id`, independent unique `donor_id`, `condition`, `batch`, `chemistry`; `adjustment: []` for the reference. |
| `single-cell-pseudobulk-counts-v1` | Shared identities, unique ordered `genes`, `mitochondrial_genes` subset, `cells` with unique `id`, design `unit_id`, evidenced `cell_type`, aligned nonnegative integer `counts` and supplied boolean `doublet`; optional `seed` must be an integer when declared (the fixture records 20261103). Zero and negative integer seeds remain allowed within the existing JSON magnitude bound; omission remains allowed. |
| `single-cell-pseudobulk-gene-sets-v1` | Shared identities and nonempty `sets`, each with `id` and unique `genes` drawn from the count namespace. These are identity controls, not an enrichment computation. |
| `single-cell-pseudobulk-labels-v1` | Shared identities, unique `cell_types` and exactly one `labels` entry per cell type: `cell_type`, `method` (`marker` or `reference`), `origin` (`external` or `study`), `source` identity and `genes`. Marker genes must be nonempty and recorded in the source. Reference labels also name matching nonempty `reference_id`. |
| `single-cell-pseudobulk-evidence-v1` | Nonempty `kind` and `result`; marker/reference evidence additionally records evidenced `cell_types` and matching `genes` or `reference_id`. Positive association support requires `kind: statistical-evidence` and `result: donor-level-association`; a review or computed record cannot substitute. |
| `single-cell-pseudobulk-result-v1` | `stages`, `evidence_level: statistical-only`, `review: unavailable`, `exploratory`, `specification_sha256`, final `input_identities`, `cell_qc`, `excluded_cells`, `excluded_units`, `excluded_genes`, `pseudobulk`, `differential`, `limitations`. |

Shared identities are `organism`, `genome_version`, `annotation_version`, `identifier_namespace`, equal and nonempty across design, counts, gene sets and labels. The reference does not silently remap IDs. Every gene-set member and mitochondrial identifier must occur in counts.

Both specifications require `replicate_unit` (`donor` or `biological_sample`), `aggregation` (`sum-raw-counts` or `mean-raw-counts`), `model: welch-log2-cpm`, integer `minimum_donors >= 2`, `alpha` in [0,1], a two-condition ordered `contrast`, unique nonempty `test_genes` and `cell_types`, `correction: BH`, `correction_scope: all-tested-gene-cell-type-pairs`, and `qc`. QC has positive integer `min_genes`, `min_counts`, `min_cells`, `gene_min_units` and `max_mito_fraction` in [0,1]. Empty or zero count tables are not condition evidence. Defaults belong to the checked-in declared fixture, not a universal scientific recommendation.

Claims require unique `id`, `kind` (`descriptive` or `associational`), `text`, `status` and `support` identities. Allowed statuses are planned, supported, replicated, suggestive, conflicting, unsupported, withdrawn, unavailable. Missing support forces unavailable; it cannot support a negative statement. Positive statuses require an actual passing result for the named `gene_id`/`cell_type`, statistical evidence, and no overreach. A single fixture never establishes independent replication, so replicated is refused. Exploratory positive claims remain suggestive. These local checks do not replace the coordinator's existing claim register or independent review.

## 01-design: freeze and admit

Inputs: entry `pack.json` plus identities of `design.json`, `counts.json`, `gene-sets.json`, `labels.json` and each source record. Reuse `$cx-public-omics-dataset-discovery` and `$cx-expression-cell-context` context records when conducting a real study; this fixture route performs no retrieval. Output: immutable admitted `single-cell-pseudobulk-pack-v1` and hashed design/specification identities.

Controls fixed before outcomes: biological independence, conditions, batches, chemistry, labels, genome/annotation/namespace, QC, aggregation, test family and BH alpha. Independent donors nested in unpaired conditions are the replicate units, not an automatically invalid design. Multiple samples from one donor and donor fixed effects nested in condition are refused here; paired or repeated-measures models need a separate method. A batch/chemistry factor whose every level occurs in only one condition is perfectly confounded and refused. Nonempty covariate adjustment is unsupported. The reference does not adjust partial confounding; a balanced planted batch effect is the fixture control, and real imbalance needs method review.

Evidence labelled external must differ by both path and hash from every study input and declared study output; an alias copy is still dependent. Asserted marker/reference provenance is checked against the hashed source kind, result and cell-type evidence. Label-feature overlap with tested genes requires exploration even when the source says external. Source declarations cannot establish actual historical independence.

Failure: labelled refusal for missing input, bad identity, absent evidence, donor/batch/chemistry confounding, or invalid freeze. Preserve the failed admission and unavailable records in the coordinator's evidence store. Gate only when essential missing information or an interpretation-changing choice prevents this admitted route.

## 02-qc: retain failures

Input identities: frozen pack, design, counts and label evidence from 01. Output: `cell_qc`/`excluded_cells` in `single-cell-pseudobulk-result-v1`; no file is created by the validator. For each cell record total counts, number of genes with positive counts, mitochondrial-count fraction and all failed controls. A zero-count cell has fraction 1 and fails minimum counts/genes. Exclude supplied doublet calls; do not create or rerun a doublet model. Threshold comparisons are inclusive at the stated limits.

Count retained cells per unit and cell type. Record every underfilled combination, including zero cells, with `cells`, `threshold`, `reason: min_cells`; never silently include it. Gene QC uses the number of retained pseudobulk units with nonzero gene count and the frozen `gene_min_units`, before looking at p values. Preserve dropped genes with units and threshold. Failure: an empty retained testing family or insufficient eligible units stops comparison. No automatic gate for ordinary QC exclusions.

## 03-aggregation: freeze the replicate unit

Input identities: the same frozen files and retained cell assignments. Output: `pseudobulk` in `single-cell-pseudobulk-result-v1`, with `unit_id`, `cell_type`, `condition`, `batch`, `chemistry`, retained `cells` and aligned raw-count sums or means. Iterate design units then label cell types; the pack's `included_units` must exactly equal eligible tested pairs in that order. Low-cell groups are never test replicates.

Changing QC or aggregation from the original frozen specification requires `exploratory: true`; keep the original freeze. Hashes verify declared content, not when it was written. Sum and mean routes give equal CPM ratios within a unit; the rule still remains part of the frozen identity. Failure: omitted or silently included pairs, unsupported aggregation, or unlabelled revisions are refusals. A material change in scientific interpretation needs a human gate; a declared admitted offline route needs none.

## 04-comparison: statistical evidence

Input identities: frozen pack/design/counts/labels/collection and admitted sources. Output: all `differential` rows in `single-cell-pseudobulk-result-v1`. Require at least `minimum_donors` in each condition for every tested cell type; recheck batch and chemistry confounding after QC. Compute log2(1 + 1e6 × count / total pseudobulk counts). Use independent biological units, never cell count, for Welch means, sample variances, degrees of freedom and denominators. Refuse empty, non-finite, insufficient or zero-within-condition-variance data. Report second-minus-first `log2_fold_change`, `t`, `df`, `p_value`, `q_value`, `significant`, and both donor counts. This effect is a difference of mean log values, not a count-model coefficient.

BH includes every gene/cell-type pair surviving only the fixed pre-test gene QC; no p-value or effect selection enters the family. Both missing correction and selected-after-testing scopes are refusals. Preserve all null results and excluded genes. Stop on failed numerical controls; never replace them with a significant-looking number. edgeR/DESeq2 pseudobulk are names of gated real-count extension points only; no command, installation or external executable is bundled.

## 05-handoff: bounded claims and independent review

Inputs: unchanged identities and all QC/aggregation/comparison results, failed controls, negative results, uncertainties, source dependencies and separate existing claim-register entries. Output: the ordinary result artifact and coordinator-owned `$science-provenance` registration, then a `$science-review` packet. The coordinator chooses rigor and registers any independent receipt; the pack leaves review unavailable and cannot mark itself reviewed.

An `unavailable` claim is refused when its text says supported, replicated, suggestive, significant or differentially expressed. At most 1000 units and 100 cell types are accepted, checked before any per-group allocation. The conservative, case-insensitive wording filter refuses whole words beginning with `caus`, `mechanis`, `therap`, `clinical`, `efficac`, `effective`, `treat`, `cure`, `prevent`, `driv`, `induc`, `regulat`, `activat`, `repress`, `bind`, `affinit`, `inhibit`, `fate`, `trajector`, `pseudotim`, and the word `truth`, plus `physical validity`, `disease modif...` and `patient benefit...` with spaces or hyphens. These narrow word families include binding, affinity, inhibition, activation and mechanism assertions, such as "Compound A binds target B with high affinity". Word boundaries apply at both ends, and the filter refuses these even in negations and for every claim status, including supported, replicated and suggestive. Review must also assess unlisted paraphrases. Every positive status checks both cited record `kind` and `result`; review/approval/computed/numerical/physical/clinical/truth records are refused, and positive support must be donor-level statistical evidence. Claim labels alone cannot bypass wording or source checks.

Association is never causality, a computed agreement never physical or clinical validity, an absent record never negative evidence, and approval never truth. Retain failed controls and negative results. The next measurement must discriminate a remaining interpretation, not just add another schema. Use one existing checkpoint with the five stage IDs in `plan.json`. No global state, manifest, receipt, registry or MCP contract is changed.
