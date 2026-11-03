# Stage contracts

## Input and handoff

Use one existing checkpoint with the ordered plan steps. Each handoff retains immutable input/output paths and hashes, stage status and exclusions; failures remain recorded. Freeze source topology/trajectory hashes, ordered atom mapping (chain/residue/insertion/atom identity), reader format/version, producer engine, parameter files/water/ensemble and restart/seed lineage. Distinct filenames or seeds alone do not prove independent runs. Matched topology is required by the bounded helper; a scientifically justified cross-topology comparison needs an explicit reviewed mapping outside it.

## Observable and processing

Freeze observable formula/implementation and unit, selection membership, fit/reference atoms, PBC/make-whole/unwrap/center order, frame times and time unit, equilibration discard, stride, window, controls, threshold rationale and intended contrast before inspecting comparisons. Validate box vectors and geometry using the original trajectory reader. Retain original coordinates and transformed derivatives separately. Missing frames, unresolved PBC or identity/unit mismatch stop the helper. Never auto-convert units, patch missing values or silently discard incomplete blocks.

## Exported-series helper

`python3 scripts/analyze_trajectory_comparison.py examples/trajectory-comparison/series.json` reads one JSON and prints JSON only. `trajectory-comparison-v1` is a pack-local artifact label, not a registered global schema. Required contract keys are demonstrated completely in the example. Each replica repeats processing metadata and exact expected times, with unique replica, independent-run and source identities. `model_id` freezes the comparable upstream protocol/model; condition contrasts involving model changes need another reviewed design.

The helper calculates arithmetic per-replica means, disjoint contiguous block means and sample-SD/sqrt(block count) SE, plus doubled-block SE only where the entire window divides into at least four complete coarse blocks. An odd base-block count makes doubled-block SE unavailable; trailing blocks are never omitted. No partial block is discarded. Fewer than four base blocks makes block SE unavailable and the comparison exploratory. Block length must be justified against observable correlation time outside the helper; increasing block-size SE is a warning to investigate, not automatic proof of adequacy. Inspect traces, autocorrelation and additional prespecified windows with the analyzer. Half-window drift is late mean minus early mean; its absolute value is checked against the frozen threshold in observable units. For odd frame counts the late half has one additional frame, explicitly determined by integer division.

Conditions receive equal-weight replica means and SD/sqrt(replica count); the contrast is second minus first, with SE sqrt(SE1²+SE2²), assuming independent unpaired replicas across conditions. Paired runs, shared run ancestry, unequal windows or correlated replicas require a different reviewed estimator. No p-value or confidence interval is fabricated. Less than two independent replicas per condition, any failed essential control, or any excessive half drift makes contrast SE unavailable and status exploratory. Descriptive means remain available with reasons. Matching declarations cannot authenticate actual topology, PBC or statistical independence; review source records.

## Conclusion admission

Qualified descriptive status means the declared offline checks passed. It is not a convergence, equilibration, hypothesis-test or biological claim. Preserve null/negative comparisons. Essential failed controls prevent accepted scientific conclusions. Sampling-sensitive results remain inconclusive even when this helper passes. Include upstream force-field/protonation/ensemble limitations, alternative hypotheses, untested slow timescales and the smallest next measurement. Review records separately from experimental evidence.
