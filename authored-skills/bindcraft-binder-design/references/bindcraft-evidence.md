# BindCraft evidence and claim rules

Use this reference to interpret a BindCraft design campaign. The campaign
manifest records the actual run; this document defines what conclusions the
record can support. Keep status values `supported`, `contradicted`,
`inconclusive`, and `unavailable` for every material claim.

## Claim classes

- **Generation:** a trajectory or sequence was emitted. Assign only when the
  output is present, parseable, and linked to a recorded run; this says nothing
  about folding or binding.
- **Design-model compatibility:** the designed sequence/complex passes declared
  in-silico geometry, confidence, or energy criteria. Require metric definitions,
  model/checkpoint identity, thresholds fixed before ranking, and the candidate's
  complete filter history. It is not experimental binding.
- **Self-consistency:** an independent refolding or complex-prediction run
  resembles the design under a prespecified alignment and scRMSD definition.
  Record global and interface/local comparisons separately. Agreement is model
  agreement, not a measured structure.
- **Experimental binding:** assign only from a named binding assay with target
  identity, construct, conditions, controls, replicate unit, uncertainty, and
  assay-specific decision rule. Predicted ipTM, ipAE, contacts, or interface
  energy cannot assign this class.
- **Expression/folding:** assign only from an experiment that measures the
  declared property; soluble yield does not imply a correctly folded monomer.
- **Function/specificity:** require a functional or competition assay and
  relevant positive, negative, and off-target controls. Binding alone does not
  establish function or specificity.

Keep computational, experimental binding, expression/folding, and functional
claims as distinct rows. A measured result for one candidate does not validate
all survivors or a future campaign.

## Source dependencies and independence

Record BindCraft release or commit, complete config, target structure and
coordinate hash, AlphaFold2 code/weights identity, ProteinMPNN version/weights,
PyRosetta version and terms, templates/databases where used, and runtime
environment. Pin checksums where available; do not infer a version from a
directory name. Review each component's license, weight terms, and service terms
before use or redistribution. The BindCraft code license does not grant rights to
separately licensed weights or PyRosetta.

Design-time AlphaFold2 optimization and AlphaFold2-based filtering share model
assumptions. Treat them as one evidence lane, not independent validation. A second
prediction using a different seed or recycles setting is a sensitivity check, not
an independent method. Record shared weights, code, training sources, templates,
target structure, and scoring features before calling any rescore orthogonal.
Even a different predictor may share public training structures or homologs.

For novelty, compare both target and binder sequences/structures with a dated,
versioned collection. Report database release, search method, identity/coverage,
and exclusions. A low hit count is not proof of novelty; incomplete databases,
recent deposits, and related training examples limit that inference.

## Uncertainty and selection

Record all attempts, including interrupted runs and rejected candidates. At every
stage report the input count, retained count, missing/unevaluable count, and
reason-specific exclusions. Use generated trajectories as the primary denominator
for yield; also report later-stage denominators. Never report only a pass rate
among candidates selected by the same metrics used to define a pass.

Preserve the continuous score distributions, not only binary filters or a top-k
list. Report uncertainty across seeds and candidates separately from assay
replicate uncertainty. Small samples, correlated trajectories, unmeasured
construct failures, and unknown assay sensitivity must remain explicit. A
candidate selected from many attempts has winner's-curse risk; selection on
ipTM/ipAE and then reporting those same metrics is not independent confirmation.

Use claim statuses as follows: `supported` means the stated evidence meets its
prespecified criterion; `contradicted` means valid evidence fails it; `inconclusive`
means evidence is conflicting or too imprecise; `unavailable` means required
evidence was not collected or cannot be interpreted. Missing evidence is not a
negative result.

## Controls

- **Positive design control:** a known binder/target pair or validated reference
  complex passed through the same structure preparation and scoring route. Report
  whether the pipeline recovers the expected interface; known binders may not
  reproduce a design-specific geometry.
- **Negative design controls:** scrambled sequences or randomly chosen designs
  matched for length/composition, plus an unconditioned or unrelated-surface
  baseline where the tool setup makes that comparison meaningful. Run through the
  same predictor and filters; do not assume they are biologically nonbinding.
- **Target controls:** evaluate plausible off-target homologs or neighboring
  domains and preserve matched target preparation. Computational selectivity is a
  hypothesis until measured.
- **Experimental controls, if assays are run:** include assay-positive and
  nonbinding/irrelevant controls, target-only/background controls, and replicate
  units. Record construct, concentration range, detection limit, and failed wells.

Sanity checks include residue-number mapping, chain identity, interface atom
counts, clash/geometry calculation, sequence alphabet, and input/output checksums.
Invalid inputs make the result unavailable; they are not repaired silently.

## Sensitivity analysis

Prespecify a small, interpretable grid around the planned design: independent
seeds; hotspot sets or numbering choices justified by the target; allowed noise
and optimization settings; and filter thresholds varied one at a time before
combined alternatives. Keep candidate budget comparable or show its change.

Call a result fragile when small defensible changes alter the top candidates,
pass/fail decisions, epitope, rank ordering, or qualitative claim status. Report
candidate overlap, rank correlation where meaningful, funnel counts, and the
threshold at which decisions change. Do not choose a preferred setting after
seeing which one gives the desired binder and call it confirmatory.

## Applicability and failure detection

BindCraft's conclusions are limited by target structure quality and state,
unmodeled glycans, ligands, membrane orientation, oligomerization, flexibility,
epitope accessibility, construct truncation, protonation, and omitted cofactors.
The pipeline does not establish developability, immunogenicity, safety, in-cell
access, or assay performance. Predictions outside the trained structural/model
domain or on unusual chemistry require separate evidence.

| Failure mode | Detection and record |
| --- | --- |
| Wrong chain, residue numbering, or target state | Compare source coordinates, maps, assembly, and hotspot residues before launch. |
| Missing interface context or inaccessible epitope | Inspect omitted chains, glycans, membrane plane, ligands, and known partners; downgrade specificity/access claims. |
| Weight, dependency, or terms mismatch | Hash files, record provenance and license; stop before use if rights are unresolved. |
| Design and validation share AF2 assumptions | Trace model lineage; label it same-lane computational support. |
| Threshold tuned after viewing candidates | Compare frozen config and execution logs; mark the analysis exploratory and rerun with a declared rule if approved. |
| Survivor-only denominator or lost trajectories | Reconcile run IDs and stage counts; claim unavailable until the full funnel is restored. |
| Apparent novelty from incomplete search | Record database/date/coverage and report only bounded similarity evidence. |
| High confidence without experimental effect | Keep prediction and assay claims separate; report assay result and uncertainty independently. |

## Sources and scope

- Pacesa et al., “One-shot design of functional protein binders with BindCraft,”
  *Nature* (2025): describes the BindCraft pipeline and experimental evaluation
  in its tested targets. Its reported outcomes are not a success-rate prior for
  a new target or campaign.
- Dauparas et al., “Robust deep learning–based protein sequence design using
  ProteinMPNN,” *Science* (2022): supports ProteinMPNN as a backbone-conditioned
  sequence design method, not as a binding or function assay.
- Jumper et al., “Highly accurate protein structure prediction with AlphaFold,”
  *Nature* (2021): introduces prediction confidence outputs; confidence is not
  an experimental measurement of affinity or function.
- Watson et al., “De novo design of protein structure and function with
  RFdiffusion,” *Nature* (2023): reports specific experimental demonstrations
  and computational filters; it does not validate every generated backbone.
