# RFdiffusion evidence and claim rules

Use this reference to interpret the output of RFdiffusion and its downstream
sequence/refolding funnel. Record every material claim with status `supported`,
`contradicted`, `inconclusive`, or `unavailable`. Keep the generated structure,
sequence design, experimental binding, expression, and function evidence lanes
separate.

## Claim classes

- **Generation:** a backbone was emitted under a recorded conditioning contract.
  Require a valid structure, mapping, trajectory, config, and candidate ID. It
  does not establish that the structure is foldable.
- **Conditioning/motif satisfaction:** the output meets declared geometric
  constraints after applying an explicit residue map and alignment. Report
  motif-local and global measures separately; a geometric match does not prove
  the intended chemistry or catalytic activity.
- **Self-consistency/designability:** sequence design followed by refolding with
  an independent predictor yields a structure sufficiently similar to the
  design under prespecified global/local scRMSD and confidence criteria. Report
  pLDDT and pAE with their definitions; these are model confidence/error
  predictions, not experimental evidence.
- **Sequence compatibility:** ProteinMPNN or another inverse-folding method
  proposes a sequence for the backbone. Sequence recovery is a diagnostic only;
  it is neither a functional score nor proof that the designed sequence adopts
  the intended state.
- **Experimental binding/expression/folding/function:** assign only from a named
  assay, declared construct and conditions, controls, replicate unit, uncertainty,
  and criterion. These are distinct claim classes; binding does not imply
  expression, folding, specificity, or biological function.

Do not label a backbone “successful” without naming the class and criterion.
Every stage should preserve `supported`, `contradicted`, `inconclusive`, or
`unavailable`; absence of an assay is `unavailable`, not a failure or success.

## Source dependencies and independence

Pin RFdiffusion commit, checkpoint hash, model configuration, preprocessing,
contig/residue mapping, target/motif coordinates, and software environment.
Record any potentials, symmetry settings, noise schedule, and restraints. Keep
code and checkpoint/weight terms distinct; the selected revision's actual files
and licenses control use. Do not assume a license from the model name or a paper.

For the full pipeline, separately record ProteinMPNN/LigandMPNN weights and code,
refolding predictor code/weights, databases/templates, and structure cleanup.
RFdiffusion and RoseTTAFold-derived validation have related training and modeling
assumptions; AlphaFold-based refolding is a different model family but can still
share public structures, homologs, and benchmarks. State this dependency map and
do not call predictors independent merely because the executable differs.

For novelty, search generated backbones and sequences against dated, versioned
structure and sequence collections. Report search method, alignment, coverage,
identity or structural similarity criterion, and missing-data limits. Novelty
relative to a finite database is bounded evidence, not proof that no similar
natural or designed protein exists or that the generator generalizes beyond
training data.

## Uncertainty and selection

Retain every trajectory and candidate, including invalid outputs, failed
conditioning, sequence-design failure, and refolding failure. At each funnel
stage report input, retained, excluded, and unevaluable counts with reasons.
Use all generated candidates as the primary denominator; survivor-only summaries
hide both failure rates and selection bias.

Report distributions for motif RMSD, scRMSD, pLDDT/pAE, geometry, and sequence
recovery rather than only a top candidate or thresholded pass rate. Separate
between-seed/candidate variability from prediction-model uncertainty and any
experimental replicate uncertainty. Candidates selected on the same scRMSD or
confidence filter cannot then use those values as independent confirmation.
For many generated samples, disclose the number inspected and the selection rule;
the best score tends to improve with a larger search budget even without better
per-candidate quality.

Use `inconclusive` for conflicting or unstable predictions, `unavailable` when
required outputs are missing, and `contradicted` only when valid evidence fails
the declared criterion. Keep untested binding, expression, and function as
`unavailable` regardless of computational confidence.

## Controls and sanity checks

- **Positive generation control:** reproduce an official motif-scaffolding,
  topology, or binder example with its pinned config. Confirm conditioning and
  output parsing, not broad biological validity.
- **Known-structure control:** scaffold a known motif or target structure and
  measure whether the same alignment/mapping code recovers the expected geometry.
- **Negative controls:** use scrambled or random sequences for comparable
  backbones, plus unconditioned generation or an irrelevant motif/target where
  scientifically meaningful. Process controls through the same sequence and
  refolding pipeline; they are not guaranteed nonbinders.
- **Downstream positive control:** include a known foldable sequence/backbone or
  known binder in the refolding/complex-prediction route where available. It tests
  that route's calibration, not the new design.
- **Experimental controls:** if testing is authorized separately, include known
  positive and nonbinding controls, target-only/background controls, and
  appropriate replicate units; report construct, assay range, failed measurements,
  and uncertainty.

Check coordinate units, chain IDs, contig lengths, residue numbering, motif
alignment, sequence alphabet/length, clashes, missing atoms, and preserved input
hashes. Stop on mapping ambiguity rather than silently repairing it.

## Sensitivity analysis

Vary independent seeds and candidate counts, hotspot or motif definition,
conditioning/contig alternatives, noise scale, diffusion steps or potentials,
and downstream thresholds. Keep each comparison's target, checkpoint, compute
budget, and filter denominator visible. Vary one factor at a time first; combine
only defensible alternatives.

Treat a result as fragile if modest changes alter motif satisfaction, fold class,
topology, sequence/refolding agreement, candidate ranking, retained count, or
claim status. Report overlap among candidate sets, stage denominators, and which
decision changes. Do not tune conditioning or thresholds against the same outputs
then describe the resulting pass rate as confirmatory.

## Applicability and failure detection

RFdiffusion produces structures under learned structural priors and supplied
conditioning. Applicability is limited by target conformational state, missing
partners, membrane/glycan context, ligand or metal chemistry, unusual residues,
disordered regions, uncertain maps, and unsupported topology or length. Structural
plausibility does not establish thermodynamic stability, accessibility,
expression, binding, specificity, toxicity, or function.

| Failure mode | Detection and record |
| --- | --- |
| Contig/index or residue-map error | Validate each mapped residue against source coordinates and motif alignment before generation. |
| Motif geometry passes but chemistry is wrong | Inspect side-chain orientation, catalytic/ligand geometry, and missing context; keep function unproven. |
| Invalid/malformed trajectories disappear | Reconcile emitted candidate IDs with logs and count invalid outputs as failures. |
| Refolding uses design model or shared assumptions | Trace model/checkpoint lineage and label shared evidence dependencies. |
| Good scRMSD only among selected survivors | Restore generation and intermediate counts; report conditional and full denominators. |
| High pLDDT or low pAE mistaken for success | Preserve metric definitions and classify as prediction confidence, never assay evidence. |
| Novelty claimed from one database | Repeat across declared sequence/structure sources and state collection date and coverage. |
| Stable result depends on one seed/filter cutoff | Run prespecified perturbations and mark conclusion fragile if candidate set or claim changes. |

## Sources and scope

- Watson et al., “De novo design of protein structure and function with
  RFdiffusion,” *Nature* (2023): describes the generative method and reports
  selected experimental demonstrations. Those demonstrations do not establish
  success for an untested generated structure.
- Dauparas et al., “Robust deep learning–based protein sequence design using
  ProteinMPNN,” *Science* (2022): supports backbone-conditioned sequence design
  and its tested evaluations; sequence recovery remains a diagnostic.
- Jumper et al., “Highly accurate protein structure prediction with AlphaFold,”
  *Nature* (2021): describes predicted structures and confidence metrics; these
  outputs are not measurements of folding or activity.
- The RFdiffusion paper's stated in-silico validation criteria are examples of
  computational filters. Thresholds for a new campaign must be justified and
  prespecified for its objective, rather than copied as universal acceptance
  criteria.
