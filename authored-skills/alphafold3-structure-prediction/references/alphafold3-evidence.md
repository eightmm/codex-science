# AlphaFold3 Evidence and Interpretation

## Claim classes

Assign claim IDs and classes before inspecting candidate ranks:

- **Sequence/chemistry-conditioned prediction:** AF3 generated coordinates for a
  precisely specified set of protein, nucleic acid, ligand, modification, and covalent-
  link inputs. Support requires schema-valid input, correct entity/atom mapping,
  successful output validation, and pinned settings. It establishes a computational
  prediction only.

- **Local structure confidence:** pLDDT (reported per atom and per residue; atom-level matters for ligands) is a model confidence estimate for local
  geometry. It does not certify experimental accuracy, ligand chemistry, domain
  arrangement, or functional state.

- **Relative placement and interface confidence:** PAE represents estimated positional
  error between token/residue pairs; pTM summarizes global fold/topology confidence;
  ipTM summarizes interface confidence where emitted. These are confidence estimates
  conditional on the model and inputs, not probabilities of binding or affinity.

- **Candidate ranking:** preserve the exact `ranking_score` field and software version.
  It ranks candidate samples under a pipeline-specific rule; it is not an independent
  test, calibrated probability, or universal scale across releases. Do not infer the
  exact formula unless the pinned release documents it.

- **Experimental agreement or benchmark claim:** requires an identified experimental
  comparator with matching entity/construct and chemical state, a prespecified alignment
  and metric, an overlap audit, and target- level uncertainty. Label predicted and
  experimental coordinates distinctly.

- **Binding, mechanism, efficacy, or safety:** confidence and predicted poses alone
  cannot establish these claims. Require appropriate independent experimental evidence;
  no clinical use is permitted under this workflow.

Keep statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`. A
completed AF3 run supports only a model-output claim unless a separate evidence design
supports more.

## Source dependence and overlap

Pin the official code release or container digest, parameter provenance/version,
database snapshots, inference pipeline and flags, template cutoff, MSA mode/source,
seeds, recycles where configurable, and hardware/precision. Record all entities, atom
identifiers, CCD or SMILES representation, bond annotations, protonation/tautomer or
stereochemical assumptions where relevant, and any custom component dictionary. Preserve
disallowed weight material outside logs and provenance.

Report MSA depth, coverage, pairing and template hits when these inputs are used or
exposed by the release. These characterize input evidence, not model accuracy. Identify
shared or propagated records among MSA sources, template structures, PDB entries,
evaluation targets, and comparison methods. Search exact sequence, homologous domains,
related complexes, ligand identity, and similar constructs when benchmark leakage
matters; record search scope and unresolved matches.

Use a PDB release date as a holdout only if the exact AF3 parameter version has a
verified training cutoff. Do not assume the public paper's date is the cutoff for every
weight release. A post-cutoff structure can still overlap through homologs, related
domains, templates, or prior versions. If cutoff or parameter provenance cannot be
verified, state unknown and do not claim held-out performance. Keep Google source-code,
weight, and output terms distinct; never store restricted assets or credentials in the
evidence bundle.

## Confidence and uncertainty

Retain confidence files and report metric, entity/chain/token mask, aggregation, and
missing fields. Interpret pLDDT as local confidence, PAE as relative-position
uncertainty, pTM as global topology confidence, ipTM as interface confidence, and
ranking score as a within-pipeline sample rank. None is an experimental error interval,
calibrated posterior probability, chemical validation, binding free energy, or proof of
a biological interaction. A strong global score can coexist with weak ligand placement
or a poor local region.

For ligand and covalent predictions, separately inspect atom mapping, stereochemistry,
bond lengths/angles, clashes, protonation assumptions, and whether the required
chemistry was represented. Confidence values do not replace these checks. Carry
uncertainty from sample variation, input/chemical ambiguity, MSA/template and PDB
overlap, and comparator quality separately. Preserve all candidates relevant to
diversity; do not let the ranking score hide alternate poses or failed samples.

## Controls and sensitivity

Use a positive control by running a known experimental complex with the matching
constructs and chemistry through the same pinned pipeline, then compare using a
prespecified chain/atom mapping and structural metric. It tests parsing and the workflow
as well as model behavior; it does not validate the query. Add a negative or sanity
control suitable for the claim, such as an incorrect partner, a nonbinding control
complex where justified, a chemically invalid bond/atom mapping that must be rejected,
or a predicted pose whose key contacts are selectively perturbed. State what the control
can and cannot diagnose.

For benchmark claims, prefer targets with experimental release after the documented
training cutoff and audit homology, templates, repeated complexes, and propagated MSA
records. Freeze target set, exclusions, alignment, metric, and acceptance threshold
before running. Report counts, exclusions, missing outputs, and per-target outcomes. Do
not present a post-cutoff date as sufficient proof of independence.

Vary MSA source/depth, template use/cutoff, recycle count where supported, and random
seed; preserve all settings and candidate structures. Compare local geometry, domain
placement, interface, ligand pose, confidence, and claim status using fixed mappings. A
claim is fragile when plausible settings reverse status, change the key
chemical/structural interpretation, or cross a prespecified structural acceptance
boundary. Samples share model weights and often input evidence, so they measure
sensitivity rather than independent replication.

## Applicability and failure detection

AF3 can model supported combinations of biomolecular entities, but applicability depends
on release, input representation, parameter access, and trained coverage. A valid JSON
file does not prove that a custom ligand, rare modification, unusual covalent bond,
conformational ensemble, membrane context, or biological assembly is represented
correctly. State unsupported chemistry, missing partners, absent cellular context, and
uncertain state explicitly.

Detect common failures with explicit checks: JSON dialect/required-field errors (schema
validation); entity/chain confusion (ID and sequence map); ligand atom or bond mismatch
(CCD/SMILES correspondence and geometry); wrong stereochemistry or covalent attachment
(chemical validation); incomplete MSA or template evidence (input audit); accidental
training/template overlap (version-pinned overlap search); ranking instability (retain
all seeds and scores); implausible interface or ligand pose (contacts, clashes,
geometry, and negative control); unavailable confidence field (record missing rather
than substituting); restricted asset leakage (artifact allowlist review); and silent
partial execution (exit status, expected files, parser, and logs). A run that exits
successfully but fails structure or chemistry validation is not a successful scientific
result.

## Sources

- Abramson et al., “Accurate structure prediction of biomolecular interactions with
  AlphaFold 3,” *Nature* (2024): model scope, benchmark design, and reported confidence
  measures.

- wwPDB, PDB archive documentation (version/release used by the run): experimental
  structure and release provenance.

- AlphaFold3 version-specific official input and output documentation: exact JSON
  dialect and emitted confidence-field definitions; pin the documentation revision with
  the run.

The paper and documentation describe methods and fields; neither validates an individual
prediction. Apply the terms supplied with the actual source, parameter, and output
assets.
