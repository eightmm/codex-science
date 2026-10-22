# AlphaFold2 Evidence and Interpretation

## Claim classes

Assign a claim ID and one class before looking at ranked outputs:

- **Sequence-conditioned structure prediction:** a model proposes coordinates for the
  supplied sequence, state, and AF2 configuration. Support requires a valid input,
  successfully parsed output, reported configuration, and adequate coverage. This says
  what the model predicted, not that the structure was experimentally observed.

- **Local structural reliability:** use residue-level pLDDT and region coverage. High
  pLDDT supports local model confidence; it does not establish correct domain
  arrangement, ligand state, oligomerization, or experimental accuracy. Low pLDDT can
  indicate disorder, flexibility, missing evolutionary signal, or model uncertainty;
  distinguish these explanations.

- **Relative placement or interface confidence:** use PAE for uncertainty in relative
  residue/domain placement and pTM for global topology; use ipTM for predicted multimer
  interfaces when the pinned implementation emits it. These are model confidence
  estimates, not calibrated probabilities of biological interaction or affinity.

- **Model ranking:** record the exact ranking field and implementation. A ranking score
  orders candidates under that pipeline's criteria; it is not an independent validation
  metric or probability of truth. Do not compare scores across releases or presets
  without evidence of compatible definitions.

- **Experimental agreement or benchmark performance:** requires a separately identified
  experimental reference, a predeclared alignment/metric, a non-leaking split, and
  uncertainty across targets. A prediction compared with an experimental structure is a
  prediction-to-experiment comparison; label the experimental structure and its
  construct, state, and resolution separately.

- **Interaction, mechanism, or biological function:** AF2 coordinates and confidence
  alone cannot support binding, causality, mechanism, or function. Require orthogonal
  experimental evidence fit to the claim; otherwise report prediction-only or
  inconclusive.

Use statuses `supported`, `contradicted`, `inconclusive`, and `unavailable`
consistently. A high score is not a claim status. Record the observation that would
falsify each claim and preserve contradictions.

## Source dependence, MSA, templates, and leakage

Pin the AF2 source/container revision, parameter set/checksum, model preset, genetic
databases and snapshot dates, template database and cutoff, feature pipeline, and
inference flags. Record exact sequence and chain mapping plus MSA source, effective
depth/coverage when available, pairing method for multimer, template hits, and missing
inputs. Depth is evidence about available evolutionary information, not a direct
accuracy measure; many near-duplicate sequences do not equal many independent homologs.

Identify shared cohorts or records across MSAs, template libraries, public structures,
training/evaluation targets, and any comparator. Search exact sequences, close homologs,
domains, complexes, and related constructs in the pinned PDB/database snapshot where
feasible. Record the query, release, matching rule, and unresolved overlap. PDB release
after a training cutoff does not by itself exclude memorization through homologs or
templates.

Never invent an AF2 training cutoff. Use a cutoff only when the exact parameter/training
version has an authoritative documented cutoff; otherwise state `unknown` and do not
describe a target as held out on that basis. For a post-cutoff control, verify
experimental release date against the documented cutoff and check
sequence/domain/template overlap. Record software, parameter, database, and output
licensing terms separately; this skill does not grant asset rights.

## Confidence and uncertainty

Retain per-residue pLDDT and the full PAE matrix or artifact, and report summaries with
the exact region, chain, mask, and aggregation rule. pLDDT concerns local coordinate
confidence; PAE concerns expected positional error between residue pairs under the
model; pTM summarizes global topology confidence; ipTM summarizes interface confidence.
None is an experimental error bar, calibrated posterior probability, or binding free
energy. Ranking confidence may combine metrics; record the implementation's definition
when known and otherwise keep it as an opaque within-run rank.

Report missing confidence fields as missing. Do not average away low-confidence
segments, interfaces, or chain asymmetry. For a material claim, carry uncertainty from
model sample variation, input ambiguity, MSA/template dependence, and experimental
reference quality as separate components or explicit qualitative caveats. A single seed
or top-ranked structure cannot estimate sampling uncertainty.

## Controls and sensitivity

Use a positive control by predicting a known experimental structure from the matching
sequence/construct under a prespecified setup and comparing after a declared chain
mapping and alignment. Treat it as an end-to-end sanity check, not independent evidence
for the query. Include a negative or sanity control appropriate to the task: a known
non-interacting/incorrect pairing for multimer, a sequence/chain permutation that should
disrupt a specific interface hypothesis, or an input perturbation with a predictable
consequence. Do not claim a negative-control failure refutes biology unless the control
is valid for that model and setup.

For a benchmark, prefer targets whose experimental structures were released after a
verified training cutoff, then audit homologs, domains, templates, and shared database
records. Freeze target inclusion, metric, alignment, and threshold before inspecting
results. Report target count, exclusions, missing targets, and per-target results; do
not let a few easy cases imply general accuracy.

Vary MSA source or depth, template use/date, recycle count, and random seed while
holding other inputs fixed. Record coordinate changes after fixed residue/chain mapping,
changes in confidence and interface geometry, and claim-level decisions. Define
fragility before the sweep: a claim is fragile if plausible settings reverse its status,
alter a key contact/topology, or move an agreed structural metric across its
prespecified acceptance boundary. Seeds from one parameter/database version are
correlated samples, not independent replications.

## Applicability and failure detection

AF2 is principally applicable to protein structure prediction within the capabilities of
the selected monomer or multimer preset. Unsupported ligands, nonstandard chemistry,
missing partners, conformational ensembles, disordered regions, membrane or cell
context, and state-dependent complexes can put the question outside that setup. State
when AF2 cannot represent the requested chemistry or biological state.

Detect common failures by retaining input validation and outputs: malformed or truncated
sequences (parse/length checks); wrong construct or residue mapping (sequence-to-
coordinate mapping); insufficient or biased MSA (coverage and depth report); template
leakage (template-hit review); chain-order or stoichiometry errors (explicit chain map
and control); ranking instability (all candidate scores and structures); low-confidence
interfaces (per-chain PAE/ipTM and geometry); stale or mixed databases (snapshot
identity); failed relaxation or invalid coordinates (structure parser and geometry
checks); and unreported run failure (exit code, logs, and output-presence checks).
Missing output remains a failure, not an empty successful prediction.

## Sources

- Jumper et al., “Highly accurate protein structure prediction with AlphaFold,” *Nature*
  (2021): AF2 architecture, evaluation, and confidence concepts.

- Evans et al., “Protein complex prediction with AlphaFold-Multimer,” *bioRxiv* (2021):
  multimer setup and interface confidence context.

- wwPDB, PDB archive documentation (version/release used by the run): experimental
  structure identifiers and release provenance.

These sources do not establish that a particular target prediction is experimentally
correct. Check the pinned implementation's own documentation for output field
definitions and asset terms.
