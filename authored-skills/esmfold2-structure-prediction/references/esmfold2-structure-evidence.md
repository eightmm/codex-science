# ESMFold2 Structure Evidence

## Claim semantics

Assign a claim ID and class before inspecting predicted structures.

- **Prediction/structure:** the output is a plausible model under the pinned
  model and input conditions. Report coordinates, coverage, confidence, and
  controls; a prediction is not an experimental structure.
- **Comparative/modeling:** one configuration or model is preferred under a
  prespecified structural metric and matched input. Shared training data or code
  makes apparent agreement dependent evidence.
- **Interface/complex:** an interface is structurally plausible under the
  selected assembly, stoichiometry, and input. Confidence and geometry do not
  establish binding, affinity, or biological interaction.
- **Functional/mechanistic:** a structural feature supports a hypothesis only
  when independently tested. A predicted pose or contact pattern does not prove
  activity, mechanism, or causal effect.
- **Operational:** the pinned execution produced a complete artifact. This is a
  process claim, not scientific validation.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable`. Record required
support, falsifier, evidence, uncertainty, dependencies, and applicability. Do not
promote family-level benchmarks to target-specific evidence.

## Confidence semantics and output checks

Record only metrics actually emitted by the pinned release. pLDDT is a predicted
local residue-level confidence score; it does not measure experimental error for
the target and is not a calibrated probability. PAE estimates predicted relative
position error between residues or entities when provided; inspect inter-domain
or inter-chain blocks for relative-placement uncertainty. pTM and ipTM are model
confidence summaries at broader structure/interface scales when emitted; neither
is an affinity or binding probability. Keep each metric separate and preserve
residue/atom mapping and missing-value semantics.

Validate mmCIF parsing, chain/entity IDs, residue coverage, sequence correspondence,
ligand and cofactor atom maps, and that confidence arrays match the intended
residues. Do not infer a missing metric or map a score from a different sample.
For sampled outputs, compare sample-level structures and report the number and
selection rule for retained samples.

## Input mode, model dependencies, and leakage

Record exact Biohub `esm` code commit, Transformers version, ESMFold2 and ESMC
weight revisions/checksums, input builder, inference settings, remote service/model
identifier, and license/weights terms. A moving branch or unpinned service response
cannot be reproduced as an immutable model identity.

Record whether prediction used a single sequence or MSA, the MSA source/date,
search database release and filters, templates or external structural inputs if
used, and all entity/cofactor choices. Single-sequence mode removes MSA evidence;
it is a distinct input condition and should not be conflated with MSA-supported
results. MSA source cohorts and structure databases can share records with
benchmark or target structures.

Record the model's stated training cutoff and any known target/template overlap.
Compare target sequence/complex and available homologs or structures against
cutoff-relevant sources when feasible. Unknown training membership, close homologs,
or post-cutoff target structures are limitations. A nominally post-cutoff test is
not independent if homologous or template information crossed the boundary.

## Uncertainty and controls

Report variation across seeds, diffusion samples, input mode, and plausible
entity/cofactor choices. State whether uncertainty reflects sampling, model
confidence, or external structural variation; these are not interchangeable.
Retain failed samples and avoid selecting a preferred sample solely because it
supports the claim.

Use a known-structure control matched to the input modality and task where
possible. Freeze the reference structure and alignment procedure before scoring.
Report sequence/assembly match, coverage, and metric. A known-structure control
checks pipeline behavior; it does not validate a novel target or the model's
claimed generalization. For an interface claim, inspect geometry and clashes, and
use an orthogonal predictor or independent experimental evidence where the claim
is decision-critical. Record shared inputs and model-family dependencies.

## Sensitivity and fragility

Vary seeds and diffusion sample count; compare single-sequence and MSA modes when
both are scientifically applicable. Vary MSA source or cutoff only as a declared
sensitivity, and inspect supported stoichiometry, ligand state, metal ions, and
cofactor representations. Fix the pocket/contact cutoff and atom map before
downstream comparison.

Treat the claim as fragile if fold, domain orientation, interface placement,
ligand pose, residue contacts, or interpretation changes materially across
samples or plausible input states. Record the variants and define materiality
before analysis when possible. If choices were made after inspection, label that
analysis exploratory and preserve the selection rationale.

## Applicability domain and failure detection

Applicability depends on represented entity types, sequence length, complex size,
modifications, ligands, cofactors, available MSA/template evidence, and the exact
released implementation. Check the pinned release's accepted input/output
contract; do not assume all modalities named in general model descriptions are
supported in a local interface. Unsupported chemistry or entity representation
requires stopping or using an explicitly approved alternative that satisfies its
own license and input contract.

- **Entity or residue mismatch:** compare expected and returned chain/residue
  maps; stop downstream analysis on incomplete or ambiguous mapping.
- **Unreported metric:** inspect output schema and arrays; report it unavailable
  rather than inferring a score from another model or sample.
- **Confident but wrong placement risk:** compare PAE, sample variation, geometry,
  clashes, and orthogonal evidence; narrow the claim if they disagree.
- **MSA dependence:** compare input mode and MSA provenance; disclose when a
  result depends on an MSA that is unavailable or overlapping.
- **Cutoff leakage:** record target/template provenance and training cutoff;
  downgrade if overlap cannot be resolved.
- **Unsupported ligand or metal state:** validate CCD, atom map, oxidation/state
  assumptions, and cofactor presence; do not silently change chemistry.
- **Remote transfer or license breach:** check location, authorization, and terms
  before execution; stop if the approved route or rights are unclear.

## Sources

Use the exact Biohub ESMFold2 source repository and model card at the pinned
revision for supported modalities, weights, license, and interface behavior; those
materials do not validate a target-specific result. Lin et al. (2023),
*Evolutionary-scale prediction of atomic-level protein structure with a language
model*, describes ESMFold and its sequence-based inference; do not transfer its
claims automatically to ESMFold2. Jumper et al. (2021), *Highly accurate protein
structure prediction with AlphaFold*, describes pLDDT and PAE semantics in the
AlphaFold system. Use those definitions to explain confidence scores, not to
equate them with empirical accuracy for this model or input. CASP assessment
frameworks measure structure-prediction performance on defined targets and
metrics; a benchmark result is not experimental validation of a new prediction.
