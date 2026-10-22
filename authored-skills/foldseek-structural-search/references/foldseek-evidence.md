# Foldseek structural-search evidence

## Claim semantics

Assign one claim class per conclusion and keep the levels distinct:

- **Returned structural hit:** a complete Foldseek response contains the target
  and alignment under a named search/database setup. This is a returned-result
  claim only.
- **Structural similarity:** the reported alignment type and scores support
  geometric correspondence over the stated aligned region. Local motif matches
  and partial coverage remain local observations.
- **Candidate homology:** a structural match may support common ancestry, but
  shape alone does not prove evolutionary relationship. Require coherent
  coverage, sequence/domain context, and independent evolutionary evidence;
  keep ambiguous matches inconclusive.
- **Shared function:** a hypothesis requiring compatible active/binding sites,
  domain architecture, biological context, and independent functional evidence.
  Similar folds can support different functions.
- **Orthology:** not established by a Foldseek hit or top-ranked match; it
  requires gene/species-tree context and duplication/loss analysis.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable`. A failed,
truncated, or incomplete response is unavailable, not evidence of no structural
match.

## Alignment types and metrics

Record the alignment type, metric name, value, target/query definition, and
whether the field came directly from the service or was computed later. Interpret
only fields actually returned or derived by a declared method:

- **Alignment type:** Foldseek compares structural representations (including
  its 3Di structural alphabet) and may include amino-acid sequence or
  structure-superposition scoring depending on mode. State the actual mode;
  scores from different modes are not interchangeable.
- **E-value:** expected chance matches under the search model and database
  search space. It changes with database size/composition and filtering; pin the
  database snapshot and report the value as search evidence, not a probability
  of homology or function.
- **Probability (`Prob`):** Foldseek's reported match-confidence score supports
  a likely structural match when high (for example near 1.0 in the original
  workflow), but is not a calibrated probability of shared function or
  evolutionary history. Keep the service score name and interpretation scoped.
- **TM-score:** a length-normalized structural similarity score from a stated
  superposition/normalization. Higher values indicate stronger global shape
  agreement under that calculation; state the normalization length and do not
  treat a score as proof of homology. Values from different query/target lengths
  or alignment modes require care.
- **LDDT:** local distance-difference agreement over local residue neighborhoods
  (when reported or separately computed). It describes local structural
  agreement; it does not establish global fold identity, common ancestry, or
  function.
- **Identity and coverage:** sequence identity is descriptive of aligned
  residues; query coverage (Q-Cov) describes the fraction of the query covered.
  High Q-Cov means much of the query shape participates, not that every domain
  is aligned or function is shared. Record target coverage too when available.

No single score is a universal biological cutoff. Freeze score/coverage
thresholds and claim criteria before reviewing matches.

## Source dependencies and independence

Record exact coordinate file/hash, chain/model/state, source, preparation or
prediction status, endpoint, search mode, parameters, access date, job ID,
database choices, reported release/snapshot, and full JSON/Markdown artifact
hashes. If database version is not returned, mark it `unreported`; do not
retroactively substitute the current database. The same structure submitted to
multiple databases is one query, not independent replication.

Trace target records to their source structures, publication, and underlying
sequence. PDB chains can share a construct, complex, publication, or near
duplicate; database entries may propagate the same structure or annotation.
AlphaFold and other predicted-structure databases are model-derived, not
experimental observations. A predicted target and a predicted query can share
training or template dependencies; record that overlap when known. Compare
database results as source coverage, not independent confirmation, when records
or prediction pipelines overlap.

Pin database names and snapshots for repeated searches. PDB, AlphaFold, CATH,
MGnify, and other collections differ in provenance, redundancy, taxonomy,
experimental status, and coverage. A database change can reorder hits and alter
E-values even when the query is unchanged.

## Uncertainty, controls, and sensitivity

Carry uncertainty from coordinate quality, missing residues/domains, chain
selection, biological assembly/state, model confidence, alignment type,
partial coverage, metric normalization, database coverage, and annotation
provenance. Record unknowns rather than filling them from a target name.

- **Positive control:** use a self-hit or known structural homolog when allowed.
  Confirm that expected chain, broad coverage, and a plausible structural match
  appear. A failure prompts checks of file, chain, mode, database, and service;
  it does not prove the query lacks homologs.
- **Negative control:** search an unrelated structure or a carefully selected
  unrelated decoy query. A strong unexpected match can reveal generic shape,
  repetitive architecture, or a too-permissive threshold. Label the decoy and
  do not treat it as biological evidence.
- Vary score thresholds, query/target coverage filters, alignment mode where
  supported, and database choice. A claim is **fragile** if plausible settings
  change hit classification, rank/family, aligned domains, or the inferred
  relationship/function. Report sensitivity and all failed runs.
- Compare top hits by alignment and domain coverage, not rank alone; inspect
  whether a multidomain query is matched by different unrelated target domains.

## Applicability and failure detection

Foldseek is for a physical coordinate query with supported `.pdb`, `.cif`, or
`.mmcif` input and a named database set. It cannot search by sequence, protein
name, or accession. Structural similarity is constrained by model/coordinate
quality, selected chain/state, database contents, and alignment mode. One query
and one database do not establish search completeness.

Detect common failures:

- **Wrong input route or absent file:** path/extension/content validation fails;
  stop and request a physical structure using the existing handoff.
- **Partial or multidomain match:** Q-Cov or target coverage is low, or distinct
  query domains match unrelated families; report local structural similarity
  and reject transitive whole-protein claims.
- **Composition/repeat or generic-fold match:** a decoy or unrelated control
  matches similarly; downgrade ancestry/function claims and report the shared
  geometry.
- **Predicted structure treated as experimental:** target source or query
  provenance is model-derived; label it as predicted and avoid experimental
  claims.
- **Database/version drift:** snapshot is unreported or differs across runs;
  mark comparison as non-matched and avoid interpreting rank/E-value changes as
  biological change.
- **Malformed/truncated/API failure:** completion, schema, count, or artifact
  checks fail; retain the exact failure and classify unavailable rather than
  empty.

## Sources

- van Kempen et al. (2024), *Fast and sensitive protein structure search with
  Foldseek* — Foldseek structural representation and search method.
- Zhang and Skolnick (2005), *TM-align: a protein structure alignment
  algorithm based on the TM-score* — structural superposition and TM-score.
- Mariani et al. (2013), *lDDT: a local superposition-free score for
  comparing protein structures and models using distance difference tests* —
  local distance-difference interpretation.
