# SimpleFold structure evidence

## Claim semantics

Classify each claim before comparing structures. `input-integrity` covers whether the submitted FASTA, construct, chain definition, and residues match the run record; support it with hashes and parser checks. `execution-integrity` covers whether the pinned code, weights, backend, and configuration produced the retained coordinates; it says nothing about accuracy. `model-confidence` describes the model's own confidence output (including pLDDT where emitted); report its scale and aggregation but never relabel it as a calibrated probability. `structural-agreement` compares a prediction with a known structure under a declared alignment, residue mapping, and metric. `ensemble-stability` describes repeat/sample diversity under fixed model settings. `generalization` requires a genuinely held-out target or benchmark with known data cutoffs and no selection on the evaluation structure.

Use claim statuses consistently: `supported` means prespecified checks favor the claim; `contradicted` means a valid comparison fails it; `inconclusive` means ambiguity, uncertainty, or low power prevents a decision; `unavailable` means required structure, metadata, weights, or permission is absent. A confidence score alone does not establish structural agreement or generalization.

## Source dependencies and independence

Record input sequence and construct hash, model repository commit, checkpoint checksum, model size, inference code, backend/library versions, parameter count if reported by the source, sampling settings, device, precision, and seeds. Record the model's training-data cutoff and the known structure's release or deposition date when available. If cutoff or sequence/structure lineage is unknown, flag possible leakage and do not call the comparison held out.

Check target and close-homolog overlap against the model's documented training cutoff and benchmark split policy where records permit. A benchmark, database record, and later structure can share source experiments or propagated sequence/structure records; count those as dependent evidence. Compare alternatives only after recording whether they share training data, architectures, templates, preprocessing, or evaluation labels. Absence of overlap evidence is not proof of independence.

## Uncertainty and reporting

Separate sequence/construct uncertainty, model confidence, sample-to-sample variation, alignment/mapping uncertainty, reference-structure uncertainty, and model-domain uncertainty. Report ensemble size, random seeds, diversity statistic, aggregation and interval method, residues included/excluded, and any unresolved mapping. Report confidence summaries with their residue range and weighting. Do not infer a population distribution from a handful of model samples unless the sampling interpretation is justified. Keep all failed and null runs in the evidence record.

## Controls and checks

- Positive structural control: run an input with a known experimentally determined structure available for retrospective comparison, using a declared alignment and metric. Treat this as a software/method sanity check; it supports accuracy only for that target and protocol.
- Negative/input control: use malformed FASTA or an unsupported length in a nonproduction validation path; require a clear rejection and verify the real sequence is never silently altered or truncated.
- Verify that all predicted coordinates are finite, residue/chain mapping is coherent, structure files parse, sequence identity matches the intended construct, and checksums match the retained outputs.
- Check seed reproducibility at fixed settings and report whether outputs are identical or variable. Variation is not automatically error; unexplained nondeterminism is a provenance finding.
- For ensemble reports, include a simple baseline such as sequence-only/known structural control when appropriate and a justified independent prediction method for decision-critical claims.

## Sensitivity and fragility

Vary random seeds and number of samples to check whether ensemble summaries stabilize; vary model size, diffusion steps, tau, or backend only as controlled one-factor comparisons with other settings fixed. Report changes in confidence summaries, aligned structural metrics, residue-level disagreement, or downstream decision. A conclusion is fragile when a plausible setting change alters the fold/topology conclusion, ranking, or decision beyond the prespecified tolerance, or when variation is unresolved by the sample count. Label post hoc setting searches exploratory and preserve every tried configuration.

## Applicability domain and failure modes

Applicability is bounded by the exact released checkpoint, documented sequence-length range, supported backend/hardware, training distribution, and construct types. A successful prediction for a monomer does not validate complexes, ligands, membrane context, alternate states, disordered regions, or experimental conditions absent from the model contract. The released model license is independent of code license and must be checked for the intended use.

| Failure mode | Detection and response |
| --- | --- |
| Training-cutoff leakage or homolog overlap | Compare target/homolog and structure dates with documented cutoff and split rules; downgrade held-out claims when unresolved. |
| Confidence mistaken for correctness probability | Inspect wording and calibration evidence; report model confidence only and require external benchmark evidence for accuracy. |
| Best-sample cherry-picking | Compare all retained samples and prespecified selection rule; report diversity and retain failed/null outputs. |
| Invalid or silently changed sequence | Hash input and compare parsed output mapping; stop on truncation, residue loss, or unexpected chain changes. |
| Backend, weights, or license mismatch | Verify commit, weight checksum, runtime metadata, and separate model terms; stop or report unavailable if unresolved. |
| Resource failure called model failure | Preserve logs and classify input/configuration/resource/infrastructure causes before retry or scientific interpretation. |

## Held-out comparison procedure

Before using a known structure as validation, freeze target sequence/construct, model and weight identity, evaluation metric, alignment policy, and acceptance threshold. Record the experimental structure identifier, chain, construct, release/deposition date, quality notes where available, and mapping to the predicted sequence. Search the documented training cutoff and benchmark split records for target and homolog relationships. If records are missing, label leakage status unknown and limit the claim to a retrospective comparison.

Do not tune input selection, model size, sample count, alignment mask, or threshold on the same known structure and then call it independent validation. If it selects settings, report development evidence and reserve a separate target or benchmark for evaluation. Record all candidate runs and the selection rule so the reported structure is not chosen silently after inspection.

For structure agreement, report residue mapping, number/fraction aligned, superposition policy, and exact metric implementation. A global score can hide a wrong domain arrangement or a poorly predicted segment; add domain-wise or residue-wise summaries when those differences matter. Report unresolved termini, missing residues, alternate conformations, and construct mismatches rather than silently trimming the comparison.

Confidence comparisons across model sizes or releases need care: score definitions and calibration can change with checkpoint and implementation. Keep the same aggregation and residue mask, record score distributions rather than only maxima, and do not compare raw confidence values as common probabilities. Ensemble spread reflects sampler and settings; it is not experimental occupancy or conformational free energy without a separate validated model.

## Ensemble and confidence interpretation

Report the sample-generation procedure and whether randomness enters the sampler, preprocessing, or backend. An ensemble can collapse because of sampling settings or model bias; low diversity does not prove the protein has one biological state. High diversity does not establish multiple populated states. Biological conformational populations require experimental or separately validated thermodynamic evidence.

When summarizing pLDDT or another per-residue score, include residue coverage, aggregation rule, and whether low-confidence segments were excluded. Do not remove low-confidence regions before reporting overall statistics without also giving the unfiltered result. For domain or interface claims, report the relevant residue subset and distinguish local geometry from relative domain orientation.

If confidence calibration is claimed, require a target-matched validation set with known structures, a frozen metric, and a calibration analysis comparing score to observed correctness. A single structure or the model's own score distribution is insufficient. Record calibration population and cutoff so the statement does not silently extend to unseen taxa, constructs, or model releases.

## Per-target evaluation record

For a single target, identify the biological construct and whether the reference structure represents the same sequence, oligomeric state, ligands, mutations, and environmental conditions. A mismatch may explain structural differences but must be reported rather than adjusted away after comparison.

Record the coordinate preprocessing used for comparison, including residue renumbering, missing atoms, alternate conformers, protonation if relevant, and treatment of unresolved segments. Preserve original predicted and experimental files alongside any derived aligned structures.

If the scientific question concerns a binding site, catalytic geometry, or interface, prespecify the residue set and geometric features of interest. Whole-chain accuracy can obscure local failure, and a favorable local alignment can obscure incorrect global topology.

When only a predicted structure is available and no external reference exists, limit conclusions to execution integrity, model confidence, or sample diversity. Structural plausibility is not independent evidence of experimental correctness.

For downstream functional interpretation, describe the geometric observation and the known evidence linking it to function. A structure prediction by itself does not establish ligand binding, catalytic activity, pathogenicity, or mechanism.

## Sources

- Jumper et al. (2021), *Highly accurate protein structure prediction with AlphaFold*: supports discussion of AlphaFold's model outputs and confidence design; it does not calibrate SimpleFold confidence or validate its predictions.
- Moult et al. (1995), Critical Assessment of Techniques for Protein Structure Prediction (CASP): describes blind comparative assessment as a framework; a CASP-style comparison still requires an applicable benchmark, correct cutoff, and target-specific metrics.
- Wang et al. (2025), *SimpleFold: Folding Proteins is Simpler than You Think* (arXiv:2509.18480): primary method paper for the described flow-matching model and its reported benchmark setup; it does not establish target-specific accuracy or calibration.
- Apple's SimpleFold release repository and model documentation, exact commit and release date recorded per run: primary source for that code/checkpoint's settings, supported input, and license. These release facts are version-specific and must be checked at execution time.
