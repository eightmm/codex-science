# Model execution evidence

## Claim semantics and model selection

Separate operational claims from scientific claims. `completed` means the process reached its declared terminal state; it does not establish correctness, validity, or usefulness. Scientific statuses are `supported`, `contradicted`, `inconclusive`, and `unavailable`.

Before execution, name the claim class: descriptive measurement, predictive performance, comparative model advantage, mechanistic inference, or generated-candidate property. Assign a stable claim ID and state the population/system, prediction unit, inference-time inputs, required support, falsifier, metric, success threshold, and applicability domain. Match model evidence to the claim: benchmark performance does not establish mechanism; a predicted structure does not establish experimental structure; a docking score does not establish affinity.

Select a model only after comparing input modality, intended output, training/evaluation overlap risk, license, data terms, code and weight availability, compute envelope, and validated domain. Record alternatives and why excluded. Pin model code, weights, databases, preprocessing and runtime revisions. Do not choose a model after seeing outcomes and report the comparison as preregistered.

## Source dependencies and independence

Track dependencies among training data, homologous entities, templates, pretrained models, feature pipelines, code libraries, checkpoints, and test sets. Two models or evaluation sources are not independent when they share material data, templates, labels, preprocessing, or code. Record split keys and immutable entity IDs where relevant; identify leakage paths and whether the comparison is genuinely held out.

For each run preserve input hashes or approved external identifiers, code revision, lockfile/container digest, weight/database checksum, configuration, command, hardware, runtime, seed, and output hashes. Record source and data versions instead of relying on mutable names such as `latest`.

## Uncertainty and execution states

Keep uncertainty sources separate: measurement and labels, sampling/split variation, model stochasticity, calibration, domain shift, preprocessing, numerical behavior, and missing inputs. Use intervals, repeated seeds, subgroup diagnostics, or qualitative limitations appropriate to the design. Model confidence is not calibrated probability without validation on the target domain.

Record preflight, smoke, full run, and validation as separate states. Preserve exceptions, failed attempts, timeouts, partial outputs, null outputs, and cancellation. A successful exit code only answers whether the declared process completed according to its runner.

## Controls and sanity checks

- Validate input schema, units, coordinate/feature mappings, sequence or chemical alphabets, missingness, and identity before inference.
- Run a known small smoke input and check output shape, finite values, valid identifiers, and expected invariants before a full run.
- Use the declared baseline (simple, prior method, or no-effect predictor) and a negative control or label/input permutation when scientifically appropriate; explain when such a control is invalid.
- Include a positive reference/control when available, such as a validated example or known reference case; do not substitute a success message for a positive control.
- Check for train/test overlap, duplicate entities, homologs/templates, donor leakage, and preprocessing fitted outside the permitted training split.
- For docking, redock a suitable reference where available and inspect pose validity; absent a valid positive control, label candidate ranking exploratory.

Record which control addresses which claim and the result. Failed controls constrain or invalidate only claims that depend on them, but must be reported.

Before execution, map each claim to one primary metric and its direction, aggregation unit, split, baseline, and acceptance threshold. Choose the metric to reflect the scientific task rather than convenience; report secondary metrics as supporting diagnostics. If no defensible threshold exists, state that limitation and do not invent a pass/fail result after inspection.

For comparison, preserve a frozen evaluation set or protocol and use the same inputs and resource budget where feasible. Report paired or repeated outcomes with their uncertainty. An orthogonal model is useful only when it tests a distinct failure mode; different names do not guarantee different assumptions or training data.

## Approval and run record

The one-time gate covers a bounded package/repository and pin, downloads, hosts, data movement, resources, and output path. Record the approved envelope before execution and compare actual use against it. An approval does not cover a different model, dataset, host, or resource scale.

The run record should make failed as well as successful attempts reconstructable: timestamp, command, exit state, configuration, input identity, environment/model versions, output path, and reason for retry or stop. Keep generated diagnostics tied to the run and label downstream interpretations separately from raw model output.

For each claim, state whether the evidence is direct or proxy-based, whether the benchmark matches the intended use, and what observation would falsify the conclusion. A metric that improves while a negative control or essential invariant fails does not meet the declared scientific acceptance criterion.

## Sensitivity analysis

Vary settings that can change the result: random seeds, model/checkpoint, preprocessing, thresholds, input conformers or microstates, split policy, sequence/structure template use, solver tolerances, and resource/backend determinism as relevant. Keep the preregistered primary setting distinct from exploratory variants.

Call a conclusion fragile when a reasonable predeclared variation changes the claim status, reverses a comparison, crosses the acceptance threshold, changes top-ranked candidates materially, or violates a key invariant. Report the range of outcomes and do not select the favorable variant after inspection.

Use explicit stopping rules: stop on a failed essential schema check, smoke invariant, license or hardware requirement, approval boundary, or unsafe data transfer; retry only bounded alternatives already in scope. Record when a result remains inconclusive because the run did not reach scientific acceptance.

## Applicability domain and failure modes

State the system/population, modalities, chemical/sequence/structure space, assay, hardware, and inference-time information on which the result depends. Applicability does not extend automatically to new populations, targets, compounds, modalities, or experimental conditions.

| Failure mode | Detection and response |
| --- | --- |
| Process success presented as scientific validity | Compare output with the declared baseline, control, metric, and acceptance threshold; report process and science states separately. |
| Leakage or hidden data overlap | Audit entity IDs, split keys, templates, pretraining sources, and preprocessing fit; qualify or invalidate affected claims. |
| Model chosen after outcomes | Compare dated plan and run configuration; label post hoc selection exploratory. |
| Confidence interpreted as probability | Check target-domain calibration; otherwise report as model score/confidence only. |
| Smoke passes but full input differs | Validate representative data and output invariants at both scales; preserve full-run failure. |
| Unstable rankings or metrics | Repeat predeclared seeds/settings and report sensitivity; downgrade if status or threshold changes. |
| Inappropriate control | Check whether control tests the actual claim and shares key biases; state why it cannot establish validity. |
| Environment drift prevents reproduction | Compare lock, image, model, hardware, and runtime identities; report exact mismatch and reproduction limit. |

Record the decision consequence for each result: which claim status changed, which threshold was met or missed, and whether the next action is validation, method repair, or a new experiment. Do not let a downstream visualization or secondary analysis upgrade a claim whose primary acceptance test failed.

For a null or failed result, distinguish evidence against the hypothesis from insufficient power, implementation failure, invalid input, or unavailable output. Only the first can count as a scientific contradiction, and only when the measurement and design could have detected the predicted effect.

When a run is interrupted, preserve the last valid checkpoint and the exact restart point. Confirm that resumed computation does not duplicate samples or alter the preregistered evaluation set; otherwise identify it as a new run.

Name the expected output artifact and its schema before execution. Validate the artifact after the runner exits; a zero exit code with missing, malformed, or empty output fails the operational contract.

## Sources

- Wilson et al., **Good enough practices in scientific computing** (2017), PLOS Computational Biology: practical organization, automation, and reproducibility practices; not a model-validation standard.
- Sandve et al., **Ten Simple Rules for Reproducible Computational Research** (2013), PLOS Computational Biology: reproducibility practices; not proof that a model generalizes.
