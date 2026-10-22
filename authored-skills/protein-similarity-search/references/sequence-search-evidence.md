# Protein sequence-search evidence

## Claim semantics

Classify every conclusion separately; never collapse these levels:

- **Sequence hit:** the service returned a local or global alignment under the
  recorded search parameters. Verify the record and alignment; a hit alone is
  not a biological relationship.
- **Sequence similarity:** an observed alignment with reported identity,
  coverage, bit score, and E-value. State the aligned region and denominator.
- **Candidate homology:** a plausible common-ancestry interpretation supported
  by alignment significance, sufficient coverage, domain architecture, and
  independent context. Sequence similarity can support but does not prove it;
  weak/local matches remain inconclusive.
- **Shared function:** a hypothesis only, supported by conserved catalytic or
  binding residues, domain architecture, taxonomic context, and reliable
  annotation. A database annotation copied among records is one evidence source,
  not independent confirmation.
- **Evolutionary relationship/orthology:** requires broader phylogenetic and
  gene-history evidence. A top hit or best score does not establish either.

Use `supported`, `contradicted`, `inconclusive`, or `unavailable` consistently.
Service failure, truncated output, or unknown search scope is unavailable or
inconclusive as appropriate, never evidence that homologs do not exist.

## Score and threshold interpretation

Record raw score fields as returned and do not treat unlike quantities as
interchangeable:

- **E-value** estimates expected chance matches at least this good under the
  search model and search space. It depends on query, scoring/statistical model,
  database size/composition, and filtering. A larger database can yield a larger
  E-value for an otherwise comparable match. Compare E-values only with the
  database/search-space and version recorded; no universal E-value proves
  homology.
- **Bit score** is a normalized alignment score under the scoring system; higher
  scores indicate stronger alignment evidence within comparable methods. It is
  not a probability and does not alone establish relationship or function.
- **Percent identity** is the fraction of identical aligned residue pairs under
  the reported alignment. Always give its denominator and aligned length.
- **Query and target coverage** describe how much of each sequence participates
  in the alignment. Local high identity with low coverage may represent a short
  motif or domain; broad coverage is stronger context but can still be
  misleading for multidomain proteins.

Choose identity, coverage, and score thresholds before viewing results and
justify them for sequence length, domain, and question. The sequence “twilight
zone” describes regions where sequence evidence is too weak to confidently
distinguish homology from chance; it is not a single universal identity cutoff.
Use profile/domain, structural, or phylogenetic evidence to resolve ambiguity,
and preserve inconclusive classifications.

## Source dependencies and independence

Record endpoint, exact query, parameters, database name, reported snapshot or
release, access time, job ID, result hash, and any filtering. If version or
database scope is not returned, say `unreported`. E-values, hit order, and hit
counts are not comparable across database sizes, releases, filters, or search
engines without a matched rerun.

Trace each hit to its primary sequence record and annotation source. Several
accessions may be propagated copies of one submitted sequence, one genome, one
publication, or one annotation pipeline. Cluster redundancy or trace source
lineage before treating records as separate evidence. Shared query databases,
training sets, annotations, or propagated records reduce independence. Pin the
database snapshot/version and the MMseqs2 or BLAST service/method when reported;
do not infer hidden versions. Record MMseqs2-first and BLAST-fallback paths
separately and do not combine their scores as if calibrated alike.

## MSA depth, redundancy, and uncertainty

When a result includes an alignment or supports follow-up alignment, record raw
depth, effective sequence number (Neff), identity-based redundancy rule,
coverage, and taxonomic composition. State the Neff formula or method and its
identity threshold; thresholds are conventions, not biological constants.
Near-duplicate hits can inflate apparent support and conserved residues.

Carry uncertainty from database coverage, release age, sequence fragmentation,
low-complexity/composition bias, local versus full-length alignment, annotation
quality, taxonomic sampling, and score-threshold choice. Do not convert a score
or model probability into calibrated posterior probability without a validated
calibration procedure.

## Controls and sensitivity

- **Positive control:** search a known homolog or self-hit under the same
  service/database when permitted. It should be recovered with plausible
  coverage; failure reveals a query, parameter, database, or service problem,
  not a universal method failure.
- **Negative control:** search a shuffled composition-preserving query or a
  biologically unrelated sequence. A strong full-length hit can reveal
  composition, low-complexity, or overly permissive threshold effects. Treat
  the control as a diagnostic, not a proof of specificity.
- Inspect low-complexity regions, compositional bias, domain boundaries, and
  alignment coordinates. Compare with filtering enabled/disabled only when the
  service permits and record that choice.
- Vary prespecified E-value/bit-score cutoffs, query/target coverage filters,
  redundancy filtering, and database choice. A claim is **fragile** if plausible
  settings change the classification, top family, key domain, or function
  hypothesis. Report the full sensitivity grid, including failed searches.

## Applicability and failure detection

The method searches protein sequence databases with the submitted sequence; it
does not perform structural search. It is limited by the chosen database,
version, search model, and access response. A missing hit cannot establish
absence when sampling is incomplete or remote homology is too divergent.

Detect and report:

- **Composition/low-complexity hit:** similarity concentrates in biased regions
  or disappears after masking/filtering; downgrade and show aligned intervals.
- **Short local motif:** identity is high but query/target coverage is low; do
  not label a full-protein homolog or function from it.
- **Multidomain transitivity error:** query matches different domains in
  different records, creating an apparent chain of relatedness; compare domain
  boundaries and require a shared coherent domain/architecture.
- **Redundant or propagated records:** near-identical sequences or copied
  annotations dominate counts; cluster and trace origins before claims.
- **Predicted/curated annotation overreach:** source record is computationally
  predicted or annotation is unsupported; label source status and do not report
  it as experimental function.
- **Incomplete or failed service response:** schema, IDs, count, status, or
  completeness checks fail; retain artifacts and classify unavailable rather
  than no-hit.

## Sources

- Altschul et al. (1997), *Gapped BLAST and PSI-BLAST: a new generation of
  protein database search programs* — local alignment and statistical search
  scores.
- Rost (1999), *Twilight zone of protein sequence alignments* — limits of
  identity-only interpretation in remote homology.
- Steinegger and Söding (2017), *MMseqs2 enables sensitive protein sequence
  searching for the analysis of massive data sets* — MMseqs2 search method.
- Henikoff and Henikoff (1994), *Position-based sequence weights* — redundancy
  weighting principle relevant to alignment depth.
