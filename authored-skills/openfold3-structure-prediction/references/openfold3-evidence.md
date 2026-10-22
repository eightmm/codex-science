# OpenFold3 Preview Evidence and Interpretation

## Claim classes

Assign stable claim IDs before inspecting structures:

- **Preview-conditioned prediction:** the pinned OpenFold3 preview produced coordinates
  for the supplied entities and settings. Support requires valid input mappings,
  recognized release identity, parsed structures, and retained run records. It supports
  only that a preview model generated those coordinates.

- **Local geometry confidence:** interpret pLDDT only when emitted by the exact preview
  release. It estimates local model confidence; it is not experimental accuracy,
  chemical correctness, or domain-orientation confidence.

- **Relative placement or interface confidence:** interpret PAE-like fields, pTM, or
  ipTM only when the pinned release defines and emits them. Do not assume their
  calibration or semantics match AlphaFold3 solely because field names resemble it.

- **Candidate ranking:** preserve the actual ranking field and version. A score ranks
  outputs under release-specific code; it is not independent evidence or a calibrated
  probability. If no documented ranking score exists, do not create one from other
  fields.

- **Experimental agreement:** requires a separate experimental structure, matched
  entity/state, fixed chain or atom map, prespecified comparison metric, and overlap
  audit. Report experimental and predicted coordinates separately.

- **Binding, mechanism, affinity, or function:** OpenFold3 preview structures and
  confidence cannot establish these claims. Require orthogonal experiment and report the
  software's preview status in any conclusion.

Use `supported`, `contradicted`, `inconclusive`, and `unavailable` consistently. Do not
treat preview completion or apparent parity as validation.

## Release, source dependence, and overlap

Record the OpenFold3 preview release/commit, setup code and dependencies, parameter
source/checksum and terms, database snapshots, kernel versions, MSA/template modes,
seeds, sample count, recycle setting when supported, hardware, precision, and exact
command. Retain query JSON, feature inputs, and mapping between entity IDs, residue
numbering, atoms, and output chains.

Record MSA source, coverage/depth and pairing where available, and template
matches/cutoff. MSA depth indicates available evolutionary input, not correctness;
related sequences are correlated evidence. Track shared records and shared methods
across template databases, PDB references, benchmark targets, and comparator models.
Search exact sequence, homologous domains, related complexes, and chemical components
when assessing overlap, and state query scope and gaps.

Use a training cutoff only if an authoritative source documents it for the exact
OpenFold3 parameter release. Otherwise mark it unknown. Do not claim a post-cutoff
benchmark is held out without a documented cutoff and overlap audit. A structure
released later may share homologous sequence, domain, template, or propagated database
records. Respect OpenFold3's own preview, source, weight, and database terms; an MIT
skill license does not grant asset rights.

## Confidence and uncertainty

Report the exact field names and definitions from the pinned release. Preserve per-atom
or per-residue pLDDT and full PAE matrices instead of only averages; name the chain,
residue/atom mask, and aggregation. Treat `sample_ranking_score`, when emitted, as a
model-reported ranking score. Read and record its formula from the exact OpenFold3
release used; do not infer its composition or equate it with AlphaFold3's `ranking_score`
unless that release documents the relationship. pLDDT concerns local confidence; PAE
concerns relative placement as defined by the release; pTM/ipTM estimate global/interface
structure confidence. None is an experimental uncertainty interval, probability of
binding, or proof of affinity.

Inspect structures independently for residue/atom mapping, stereochemistry, bond
geometry, clashes, chain completeness, interface contacts, and whether the required
chemical state was represented. Missing confidence outputs remain missing. Carry sample
variation, uncertain input mapping, MSA/template dependence, preview maturity, and
experimental-reference quality as distinct limitations. A small seed ensemble cannot
estimate population uncertainty.

## Controls and sensitivity

Use a positive workflow control consisting of an official example or a known
experimental structure with matching entity and state, chosen before inference. Compare
against the experiment using fixed chain/atom mappings and a declared metric. It checks
workflow operation and limited model behavior; it does not validate an unrelated query.
Add a negative/sanity control matched to the claim: a deliberately invalid atom mapping
that must fail validation, a wrong-partner assembly, or a known non-interacting
arrangement when an appropriate reference exists. Record the expected observation and
what the control cannot establish.

For benchmarking, prefer post-cutoff targets only when the exact release cutoff is
documented; audit homologs, templates, and shared PDB/MSA records regardless. Freeze
inclusion, exclusions, alignment, metric, and threshold before comparing. Preserve
failures and per-target results, and do not generalize from a handful of examples or
from preview status.

Vary MSA source/depth, template mode/cutoff, recycle count if supported, preview release
when a justified comparison exists, and random seeds. Compare fixed-mapping local
geometry, domain arrangement, interface/ligand pose, emitted confidence, and claim
status. Define a material change in advance; call the result fragile if plausible
settings reverse the status, alter the key structural interpretation, or cross the
chosen criterion. Samples from the same parameters and data are correlated sensitivity
probes, not independent replications.

## Applicability and failure detection

The preview label limits claims about maturity and parity. Supported entity types and
chemistry depend on the pinned release; noncanonical residues, ligand atom maps,
covalent links, modified bases, assemblies, conformational states, membrane environment,
and missing biological partners require explicit coverage review. If the preview cannot
represent the question faithfully, report it as unavailable or inconclusive rather than
silently adapting the input.

Detect failures through retained checks: invalid JSON or unsupported fields
(schema/release validation); wrong entity, chain, residue, or atom IDs (mapping table);
malformed or misassigned chemistry (bond, stereochemistry, and geometry checks);
incomplete MSA/template input (coverage audit); uncertain PDB or training overlap
(versioned search record); inconsistent candidate ranks or seeds (retain all samples);
implausible interfaces and clashes (geometry and negative control); absent or
undocumented confidence metrics (record unavailable); stale/mixed parameters or
databases (version/checksum audit); and partial execution (exit status, expected-output
parser, logs, and cancellation record). A valid command exit is not sufficient if parsed
structures or mappings fail.

## Sources

- Abramson et al., “Accurate structure prediction of biomolecular interactions with
  AlphaFold 3,” *Nature* (2024): AlphaFold3 comparison context and reported confidence
  concepts; it is not an OpenFold3 validation study.

- wwPDB, PDB archive documentation (version/release used by the run): experimental
  structure identity and release history.

- OpenFold3 official inference documentation and release notes (version pinned with the
  run): preview capabilities, exact output fields, setup, and asset terms; do not
  generalize beyond the inspected release.

No AlphaFold3 parity or OpenFold3 benchmark result is implied by these references. The
pinned OpenFold3 documentation and artifacts govern actual field availability and
applicability.
