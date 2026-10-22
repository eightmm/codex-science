# GNINA evidence, controls, and limits

## Claim semantics

Keep the following claims distinct and assign the narrowest class supported:

- **Execution:** a pinned GNINA release and model processed the declared structures and emitted parseable output. Require exit status, logs, and identity checks; this is not a scientific result.
- **Pose recovery:** a pose meets the predeclared symmetry-aware RMSD or other structural criterion against an independent experimental reference, with atom mapping and denominator stated. This supports recovery in the tested setup only.
- **CNN pose score/confidence:** a model-specific output used to order poses or estimate pose plausibility according to that model's training objective. It is not a universally calibrated probability that a pose is correct, and it is not evidence of physical binding.
- **CNN affinity output:** a model-derived estimate on its training/evaluation scale. Report the exact field, model/checkpoint, units/transform if documented, and model version. It is not measured affinity and should not be compared across arbitrary model versions or targets as if calibrated.
- **Empirical scoring energy:** a scoring-function output for the declared configuration; it is not an experimental free energy or Kd/IC50.
- **Comparative ranking:** performance on a frozen, leakage-controlled set with prespecified metrics, baselines, and uncertainty. Retrospective benchmark performance does not establish prospective enrichment.
- **Experimental binding/affinity:** requires an assay and conditions independent of GNINA. Docking outputs cannot assign this claim.
- **Inconclusive or unavailable:** failed controls, missing provenance, uncertain mapping, or missing reference prevent support; retain the attempted cases and reason.

Never choose among CNNscore, CNNaffinity, empirical energy, or a post hoc combination after seeing which gives the preferred outcome. Treat an exploratory reranking rule as exploratory and freeze it before an independent evaluation.

## Source dependencies and independence

Record target structure source/accession, chain/assembly, receptor preparation, protonation, retained waters/metals/cofactors, ligand source and microstates, atom mapping, GNINA release, CNN checkpoint/model identity, scoring mode, and binary/container digest. Pin CUDA and relevant runtime identity where inference may depend on it. A changed GNINA release, CNN model, empirical scoring function, or `cnn_scoring` mode defines a different analysis; do not pool its scores without a matched bridge study.

Freeze train/test or benchmark split identities before evaluating. Group related targets and chemical series by an explicit homology/scaffold policy when claiming generalization; inspect exact structure, ligand, template, and propagated benchmark record overlap. Record whether the experimental reference ligand informed autoboxing or preparation. Such use may be legitimate in a redocking task but invalidates a blind-prediction claim. Receptor/ligand structures, preparation code, weights, and source databases shared between training and test reduce independence and must be disclosed.

## Uncertainty

Separate uncertainty due to receptor state, protonation/tautomer enumeration, ligand stereochemistry, water/cofactor treatment, box, search seeds, generated pose diversity, scoring model, and reference alignment. For each case retain all attempted seeds and poses, not only the top-ranked item. Report per-target metrics and distributions before aggregate summaries; show denominators, missing cases, and exclusions.

CNN score variation is not itself a calibrated uncertainty interval. Do not convert an uncalibrated confidence output to a probability or treat high confidence as experimental validation. For an affinity estimate, report the model's documented scale and evaluation domain; if calibration for the target/domain is unknown, say so. Keep model uncertainty distinct from experimental assay uncertainty.

## Controls and sanity checks

- **Positive pose control:** redock a known co-crystal ligand with a prespecified symmetry-aware RMSD threshold and verified atom map. Use reference-informed autoboxing only for a protocol explicitly labeled redocking.
- **Ranking controls:** test known actives against chemically/property-matched decoys, with decoy generation and labels documented; include a simple baseline and report per-target as well as pooled performance. Decoys are not proven inactive compounds.
- **Negative/sanity controls:** include malformed or deliberately mismatched input detection, unrelated ligand/target pairs where appropriate, and checks for impossible atom mapping, severe clashes, invalid geometry, and score-field mixing.
- **Model comparison control:** if comparing CNN models or score modes, use the same frozen cases, preparation, split, and metric; do not tune on the held-out comparison set.

A failed positive control blocks a validation claim for the setup. A score ordering of decoys does not alone establish enrichment on prospective compounds.

## Score-channel reporting

Before evaluation, identify which output field is the primary ordering rule and what the remaining fields are used for. Store the raw field names and values from the pinned release so later readers can distinguish model output from a renamed or transformed value.

- **Empirical energy:** report the scoring function, its direction, and the exact configuration. Do not label it measured free energy.
- **CNN pose score:** report as a model-specific pose-ranking signal. If the release defines a particular interpretation, quote the model documentation in the run record and still report its validation domain.
- **CNN affinity:** report the exact output scale only when the pinned release documents it. Do not silently convert, calibrate, or compare it with an assay value.
- **Combined ordering:** if a declared workflow combines outputs, freeze the formula and parameters on development data, preserve each input field, and evaluate the frozen rule on a separate test set.

When score channels disagree, preserve the disagreement as evidence. Do not average channels with different objectives or scales. Report which ordering was prespecified, show the alternatives as secondary analyses, and state whether the conclusion changes under them.

## Benchmark set construction record

Record how active and decoy labels were assigned, the source and date of each label, and whether labels represent measured binding, curated activity, or a proxy. State potency cutoffs and assay heterogeneity if applicable. Do not call untested or unannotated molecules inactive.

For each evaluation set, preserve:

- target identifiers and the rule used to group homologous proteins;
- ligand identifiers, salt/tautomer/stereochemistry policy, and scaffold grouping rule;
- training/test split identity and any structure/template overlap checks;
- active, decoy, ambiguous-label, failed, and excluded counts;
- primary ranking metric, baseline, tie handling, and aggregation method;
- per-target results so a few large targets do not obscure weaker cases.

If the label source or split cannot be reconstructed, limit the statement to a descriptive result on the available records. If target labels, thresholds, or score fields were chosen after inspection, mark the comparison exploratory and do not present it as independent validation.

## Sensitivity analysis

Vary seeds and sampling effort, plausible ligand protonation/tautomer states, receptor conformations, box/autobox choices, and the declared CNN/empirical scoring mode. For flexible side chains, vary only a justified residue set and report it as a separate protocol. For ranking, test the predeclared aggregation rule and per-target results; do not choose a favorable score channel post hoc.

Call the conclusion **fragile** if plausible preparation, sampling, model, or score-mode changes reverse the pose-success decision, substantially reorder candidates under the declared metric, or cross the prespecified acceptance boundary. Show which cases change and retain the primary run as frozen.

## Applicability domain and failure modes

Applicability is limited by training-set composition, target-family and ligand-series overlap, receptor structures and conformational states, scoring-mode validation, and chemistry represented in model development. Treat out-of-distribution targets, unusual metals/cofactors, covalent ligands, macrocycles, highly flexible or charged ligands, incomplete pockets, membrane/allosteric sites, and unvalidated flexible-receptor protocols as outside the demonstrated domain unless separately benchmarked. A score may rank plausible poses while all are physically wrong.

| Failure mode | Detection and response |
|---|---|
| CNN pose score described as probability or binding confidence | Check output semantics against the pinned model documentation; report as model-specific ranking output. |
| CNN affinity conflated with measured affinity | Trace value to output field/model and assay sources; relabel model estimate and require experiment for binding claims. |
| Scores from different versions/modes pooled | Compare model/checkpoint, scoring mode, and release identities; separate analyses or run a matched bridge. |
| Reference ligand leaks into blind test through autoboxing | Trace box and preparation inputs; relabel as redocking or invalidate the blind claim. |
| Positive control or matched decoys fail | Inspect preparation, labels, target grouping, and denominator; downgrade claim and preserve failures. |
| Training/test overlap or propagated benchmark records | Audit sequence/scaffold/source identities; restrict claim to the observed benchmark or rebuild a disjoint split. |
| Atom conversion changes stereochemistry or ordering | Round-trip identity checks and geometry validation; exclude only with recorded reason and report denominator. |
| Sampling instability hidden by top score | Compare seeds, clusters, and score channels; report fragility and avoid best-of-many selection. |

## Source basis

The workflow draws on McNutt et al. (2021), *GNINA 1.0: molecular docking with deep learning*; Francoeur et al. (2020), *Three-Dimensional Convolutional Neural Networks and a Cross-Docked Data Set for Ligand Pose Prediction*; and Warren et al. (2006), *A Critical Assessment of Docking Programs and Scoring Functions*. These works motivate task-specific benchmark interpretation; they do not certify a model's calibration or performance on a new target set.
