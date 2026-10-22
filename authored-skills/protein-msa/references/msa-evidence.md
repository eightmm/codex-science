# Multiple-sequence alignment evidence

## Claim semantics

Classify each claim before reading the alignment:

- **Input-set alignment:** the service returned an alignment for the submitted
  records. This is a process/result claim, established only by a complete result
  with matching IDs and dimensions.
- **Column or region conservation:** specified residues remain similar across
  the aligned input set under a named residue grouping and gap policy. This is a
  descriptive claim about those sequences, not proof of shared ancestry.
- **Candidate homology:** outside this skill's inference boundary. A multiple
  alignment does not discover homologs or by itself distinguish common ancestry
  from convergence, composition, or biased sampling. Route candidate discovery
  to sequence search, then assess independent evidence.
- **Shared function or evolutionary relationship:** not established by column
  conservation alone. Require independent domain, structure, phylogenetic,
  biochemical, or curated evidence appropriate to the claim; retain
  contradictions.

Use the consistent statuses `supported`, `contradicted`, `inconclusive`, and
`unavailable`. A service error or incomplete response is unavailable, not a
negative conservation result. A weak or ambiguous alignment is inconclusive.

## Input dependencies and independence

Record exact sequence bytes, IDs, normalization, hashes, exclusions, query
composition, and the source of each sequence. Preserve the full submitted set:
sequences sampled from the same organism, family database, publication, or
upstream search are related observations, not independent replications. A
near-duplicate-heavy set can make a residue appear conserved because a narrow
clade is overrepresented.

Record the service endpoint, access date, job ID, request fields, and any
service-reported software/release metadata. If no version or database is
reported, write `unreported`; do not substitute a current version. For a
reproducible comparison, pin the exact FASTA and request, and rerun both sets
under the same reported method/version when available. Clustal Omega uses
progressive alignment and guide-tree decisions; order and sequence sampling can
affect the result, so record input order and any comparison run.

## Alignment depth, redundancy, and uncertainty

Report raw sequence count and effective sequence number (Neff) when available
or computed. State the identity threshold and weighting rule used to compute
Neff; there is no universal threshold. A common transparent form is
`Neff = sum_i w_i`, where each sequence weight discounts near-duplicates under
the declared rule. Neff summarizes redundancy-adjusted depth; it is not an
independent sample size for every column and does not prove representative
sampling.

For each region report aligned coverage, gaps, residue counts or frequencies,
and the denominator (sequences with a non-gap residue). State how ambiguous
residues, gaps, conservative substitutions, and excluded sequences are treated.
Carry uncertainty from small Neff, uneven taxonomic/family sampling, low
complexity, uncertain residue mapping, and service/version opacity. Do not
convert a conservation fraction into a confidence interval unless a sampling
model and its assumptions are stated.

## Controls and sensitivity

- **Positive sanity control:** include a pair or set of known related sequences
  with an expected conserved region when suitable records exist. Confirm that
  IDs, residue mapping, and the known motif are recovered; this checks the
  workflow, not every alignment decision.
- **Negative sanity control:** compare an unrelated or composition-preserving
  shuffled sequence/set only when the scientific question and service accept it.
  Unexpected coherent alignment or conservation suggests composition or
  alignment bias. Label synthetic controls and do not include them in biological
  claims.
- Check returned sequence count, exact IDs, alignment length, gap pattern,
  residue mapping, and known invariant positions before interpretation.
- Repeat the summary after declared redundancy filtering, alternative
  sequence subsets, and reasonable gap/conservation definitions. A conclusion
  is **fragile** if the key region or claim status changes under plausible
  filtering, modest subset changes, or a declared alternative conservation rule.

## Applicability and failure detection

This workflow applies to at least two valid protein sequences within the
service's current size limits. It is not a homolog search, structural alignment,
phylogenetic reconstruction, or function predictor. A global alignment can
misplace domains across rearranged or multidomain proteins; a local motif may
look conserved without global homology. Low-complexity or compositionally
biased regions can align spuriously. Divergent sequences, fragmented proteins,
missing domains, and uneven taxonomic sampling reduce interpretability.

Detect common failures explicitly:

- **Input or truncation error:** submitted/returned IDs or counts differ, result
  lacks complete rows, or dimensions conflict; stop and classify unavailable.
- **Overrepresented near-duplicates:** raw depth is high but Neff is low or
  filtering changes conservation; report the effective depth and fragility.
- **Gap/mapping artifact:** key residues move across columns or coverage changes
  under a reasonable alignment subset; report ambiguity and do not map by
  column index alone.
- **Composition/low-complexity artifact:** an unrelated or shuffled control
  shows similar patterns; downgrade the conservation interpretation.
- **Service failure:** terminal status, rate limit, missing result, or parse
  error; retain the request and failure record and do not call it absence.

## Sources

- Sievers et al. (2011), *Fast, scalable generation of high-quality protein
  multiple sequence alignments using Clustal Omega* — alignment procedure and
  guide-tree context.
- Henikoff and Henikoff (1994), *Position-based sequence weights* — sequence
  weighting to reduce redundancy effects.
- Morcos et al. (2011), *Direct-coupling analysis of residue coevolution* —
  effective sequence count as an alignment-depth consideration; it does not
  validate conservation claims by itself.
