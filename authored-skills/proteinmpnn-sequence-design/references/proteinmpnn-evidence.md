# ProteinMPNN evidence and claim rules

Use this reference to evaluate sequence design on a fixed backbone. Record
material claims as `supported`, `contradicted`, `inconclusive`, or `unavailable`.
Keep sequence-model evidence distinct from predicted structure, binding,
expression, solubility, and experimental function.

## Claim classes

- **Sequence generation:** valid amino-acid sequences were emitted under a pinned
  backbone, mask, constraints, and model configuration. Require sequence IDs,
  mapping, and raw outputs. It does not imply compatibility or function.
- **Native/parent recovery:** identity at designable positions matches an
  explicitly named native or parent sequence under a declared mask. Report
  numerator, denominator, excluded positions, and sequence identity measure.
  Recovery measures similarity to that reference, not folding or function.
- **Model compatibility:** a sequence receives a ProteinMPNN likelihood or
  score under a pinned checkpoint and settings. It is model-conditional evidence,
  not a calibrated probability of folding, stability, expression, or activity.
- **Self-consistency:** independent refolding predicts a structure near the fixed
  backbone using prespecified global and local scRMSD and confidence criteria.
  Report pLDDT/pAE definitions, model identity, and disagreements. The result is
  model consistency, not experimental structure.
- **Experimental property:** assign binding, expression, solubility, folding, or
  function only from a named assay with construct, conditions, controls, replicate
  unit, uncertainty, and declared criterion. Evidence for one property does not
  establish the others.

Never combine recovery, likelihood, and refolding confidence into an unlabeled
“success” score. If candidates are selected by one metric, that same metric is not
independent confirmation. Use status `unavailable` when required evidence was not
collected; do not reinterpret absence as failure.

## Source dependencies and independence

Record the ProteinMPNN/LigandMPNN/SolubleMPNN implementation, commit, checkpoint
hash, model variant, training/noise variant when documented, input preprocessing,
residue mask, constraints, temperature, seed, batch size, and environment. Record
checkpoint and service terms separately from source-code license. Do not infer
the terms for a derived model or redistributed weights from the original
repository license; inspect the selected assets' own terms before use.

Pin backbone source, structure preparation, atom/residue maps, ligand/cofactor
state, and any templates. A recovery test against a native sequence is dependent
on that reference and its homologs; it is not an independent experimental check.
Refolding with a different predictor adds a distinct model but can share training
structures, homologs, and benchmarks. Record those overlaps where known. Multiple
ProteinMPNN temperatures or seeds are sensitivity runs under the same model, not
independent methods.

For novelty, compare sequences and structures to a dated, versioned set of
training-related and public sequences/structures. State search database release,
identity/coverage or structural criteria, aligner, and exclusions. Distinguish
novelty relative to the exact input sequence, to known proteins, and to an
identified training-data source. Unknown training membership or incomplete
collections limit every novelty conclusion.

## Uncertainty, denominators, and selection

Preserve every attempted sequence, including duplicates, invalid sequences,
unscorable candidates, failed refolds, and filtered-out designs. Report counts at
generation, deduplication, validity, model-score, refold, and final-selection
stages. Use generated candidates as the primary denominator and disclose every
conditional denominator. A pass rate among top-ranked survivors is not a campaign
success rate.

Report recovery with the exact designable-position mask, numerator, denominator,
and treatment of ambiguous/noncanonical residues. Report per-position scores and
candidate-level score distributions; do not report only a best sequence. Keep
between-seed and between-backbone variation separate from model uncertainty and
experimental replicate uncertainty. When thousands of sequences are sampled,
selection of an extreme score is expected; disclose total samples inspected and
the rank/filter rule to avoid winner's-curse interpretation.

Use `supported` only for the stated criterion and evidence lane, `contradicted`
for valid evidence that fails it, `inconclusive` for conflicting/unstable results,
and `unavailable` for absent or uninterpretable evidence. Sequence recovery is
never sufficient to assign experimental binding, expression, or function.

## Controls and sanity checks

- **Native recovery:** redesign or rescore a known structure and report recovery
  over exactly the same designable positions, chain mask, and constraints. This
  assesses model behavior on that reference, not new-design function.
- **Known binder/fold control:** where applicable, include a known binder or
  experimentally characterized sequence on a comparable backbone, processed
  through the same scoring/refolding route. Do not treat target binding as a
  required outcome for a sequence-only method without an assay.
- **Negative sequence controls:** compare scrambled and random sequences matched
  for length and composition, plus native/parent or unconditioned sequence
  baselines where valid. Run them with identical masks and downstream checks;
  a random sequence is not guaranteed to be nonfunctional.
- **Context control:** compare ligand-aware and ligand-removed designs when the
  ligand effect is the question, keeping backbone and candidate budget matched.
- **Experimental controls:** if separate assays are performed, include known
  positive, negative/irrelevant, and background controls, declare replicate units,
  and report all failed measurements and detection limits.

Sanity checks cover amino-acid alphabet, sequence length, fixed-position
preservation, chain/residue correspondence, ligand atom identity, duplicate
sequences, and input/output hashes. Invalid mapping or violated fixed residues
invalidate downstream comparisons; do not silently repair them.

## Sensitivity analysis

Vary independent random seeds, temperature, backbone noise/model variant, fixed
and designable masks, tied positions, ligand context, and any sequence biases.
Vary downstream refolding and filter thresholds as a separate analysis. Where
hotspots or target contacts determine the designable mask, test defensible
alternative hotspot/mask definitions and record their provenance. Keep candidate
budget, backbone, and filter denominators matched or report the differences.

Call the result fragile if small defensible changes alter candidate ranks,
recovery, sequence diversity, novelty, refolding agreement, retained counts, or
claim status. Report sequence-set overlap, score distributions, and stage counts.
Do not tune temperature, masks, or filters after viewing the preferred sequence
and present the selected configuration as confirmatory.

## Applicability and failure detection

ProteinMPNN conditions on a supplied structure representation. Results depend on
backbone accuracy, missing side chains/atoms, chain and residue mapping, ligand
representation, oligomeric context, and the selected model variant. Sequence
scores do not encode every biological context, post-translational modification,
expression system, folding pathway, conformational state, or assay condition.
Ligand-aware design is limited to the represented ligand/context and does not
establish binding affinity or catalytic function.

| Failure mode | Detection and record |
| --- | --- |
| Wrong chain or residue mask | Reconcile sequence, structure, and designable positions before scoring; compare fixed residues after generation. |
| Recovery inflated by masked positions | Report exact numerator/denominator and recompute only over the declared designable mask. |
| Ligand context omitted or mismapped | Check ligand atom names, residue IDs, coordinates, and model flags; mark context claim unavailable if missing. |
| Duplicates counted as diversity | Deduplicate by exact sequence and report both raw and unique counts. |
| Temperature/seed outputs called independent replication | Label runs as same-model sensitivity and report seed-level variability. |
| Best-of-many scores presented alone | Reconcile total sampled candidates and full score/failure distribution. |
| High recovery interpreted as function | Keep recovery class separate; require a relevant assay for experimental claims. |
| Novelty claimed without training-data provenance | Report searched collection and date; state training membership uncertainty. |

## Sources and scope

- Dauparas et al., “Robust deep learning–based protein sequence design using
  ProteinMPNN,” *Science* (2022): describes backbone-conditioned sequence design
  and reports structural/experimental evaluations. Those results do not make a
  likelihood or recovery score a universal function predictor.
- Jumper et al., “Highly accurate protein structure prediction with AlphaFold,”
  *Nature* (2021): describes structure prediction and confidence metrics; scores
  such as pLDDT/pAE are predictions, not assay measurements.
- Watson et al., “De novo design of protein structure and function with
  RFdiffusion,” *Nature* (2023): provides examples of structural generation and
  downstream evaluation. It does not establish performance of a ProteinMPNN
  sequence or a new target-specific campaign.
