# UCSC coordinates, evaluation and controls

## Claim classes and evaluation unit

The retrieval unit is one assembly-specific interval, one named conservation or
TFBS track, one response version/time and one aggregation over returned records.
An evolutionary score describes sequence evolution in the track's alignment;
it is not a present-day measurement of gene expression, chromatin state,
protein occupancy or phenotype. A track overlap is an annotation assertion,
not proof of activity in the sample under study. Keep these evidence classes
separate in tables and prose.

If benchmarking regions or variants, define the unit (base, interval, variant,
gene or locus), score summary, threshold and evaluation set before inspecting
target scores. Report denominators, missing alignment/score coverage and
exclusions. Intervals from the same gene, overlapping windows, related species
alignments and records propagated from a shared source are dependent.

## Assembly and coordinate contract

UCSC `/getData/track` accepts assembly (`genome`), track, optional chromosome,
and optional start/end; the API documentation specifies start as zero-relative
and end as one-relative. Record the submitted query exactly, including its
coordinate convention. Normalize incoming variant conventions before making
requests and preserve the original coordinates. Human tracks `hg38` and `hg19`
are different references and score tracks; never combine them without a
documented, checked coordinate mapping.

Use the public base `https://api.genome.ucsc.edu`. List tracks with
`/list/tracks?genome=<assembly>` before retrieval and retain the exact selected
track name and IDs. Human conservation sets include hg38 100-way vertebrate
and 470-way mammal, and hg19 100-way and 46-way; these are distinct alignments,
so record the exact selected track name. Fetch with `/getData/track`; verify
returned assembly, chromosome, interval and track. Inspect response item limits
and page or truncation indications. A track list only proves that a track is
available for query, not that it has records over the requested interval.

For each score, record source alignment and species coverage when known, track
release and neutral model. For TFBS tracks, retain the source database, assay or
motif method, sample/cell metadata and version. If the API omits these fields,
record unknown and consult the track description; do not invent metadata.

## Source dependencies and independence

phyloP and phastCons tracks can share alignments, genome assemblies and
phylogenetic assumptions. An adjacent base or second score track from the same
alignment does not constitute replication. TFBS tracks may share source assays,
peak calls or motif annotations with external benchmarks. Track source names,
accessions/releases and source cohorts should be retained so duplicate or
propagated evidence is not counted twice.

For split-based validation, group by non-overlapping locus and source assay or
cohort as needed. Avoid train/test separation that leaves overlapping genomic
windows or the same propagated label in both sets. If source provenance is
incomplete, record that independence is unverified and avoid a held-out claim.

## Uncertainty, controls and sensitivity

Separate uncertainty from assembly/coordinate mapping, alignment, species set,
neutral model, score precision, track metadata, missing bases, repeat context
and assay/sample applicability. Record counts for queried bases, aligned bases,
scored bases and omitted bases where available. Missing does not mean zero or
unconserved.

For conservation checks, compare a conserved coding exon and a neutral region
on the same assembly, alignment and score track; for variant comparisons also
use matched random or common variants. For TFBS checks, choose a known positive
site for the same assay/source and a matched background region. Record
coordinates, selection rule, matching fields, track source and expected check.
These are sanity controls rather than independent evidence of function.

Vary track, alignment/species set, interval/window width, score summary and
original score download versus API representation where available. For TFBS,
vary source/assay and sample context. A material change in class, sign, rank or
overlap status makes the conclusion fragile; keep all compared results and
selection decisions.

## Applicability domain and failure checks

Scores apply to aligned, represented sequence from the pinned assembly and
species set. They can fail at repeats, segmental duplications, assembly gaps,
poorly aligned or lineage-specific sequence and loci affected by uncertain
coordinate conversion. Track availability is not uniform across assemblies.
No score cannot exclude function. TFBS tracks reflect a particular assay,
sample, antibody or motif method and may not transfer to another cell state.

- **Build mismatch:** verify assembly and reference allele; compare a known
  landmark and stop on inconsistent coordinate mapping.
- **API interval semantics error:** check the documented start/end convention
  and request boundary bases explicitly where ambiguity matters.
- **Response truncation:** compare returned counts with item limits and parse
  explicit truncation/pagination cues; classify incomplete data unavailable.
- **Alignment/repeat gap:** calculate coverage and inspect repeat annotations;
  retain missingness and report any predeclared exclusion.
- **Version mismatch:** record exact track descriptions/releases and do not
  combine incompatible score tracks as though calibrated alike.
- **Source dependency:** compare accessions/cohorts and group shared records;
  label unknown independence rather than claiming replication.

## Sources

- UCSC Genome Browser REST API data-interface documentation, current version
  and access date recorded per analysis, for coordinate and endpoint semantics.
- Haeussler et al., “The UCSC Genome Browser database: 2019 update,” *Nucleic
  Acids Research* (2019), for UCSC database and browser context.
- Pollard et al. (2010) and Siepel et al. (2005), for the distinct evolutionary
  score models; see the companion conservation reference for claim semantics.
