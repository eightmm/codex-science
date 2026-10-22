# dbSNP identifier and allele reconciliation

## Claim semantics

Use claim IDs and the shared statuses `supported`, `contradicted`,
`inconclusive`, and `unavailable`.

- **Identifier mapping:** supported only when a returned current rsID or merge
  relationship matches the queried identifier and allele/locus context.
- **Allele identity:** supported only when reference/alternate sequence and
  assembly agree after explicit normalization or remapping. A coordinate alone
  is insufficient.
- **Annotation lookup:** supported as a report of what the returned dbSNP or
  linked source record contains. A clinical assertion or frequency does not
  establish clinical or functional truth.
- **No returned record:** unavailable for the queried identifier; it is not
  evidence that a variant is absent from biology. Query failure or incomplete
  pages are inconclusive.

Keep rsID mapping claims separate from linked clinical significance, gene,
frequency, and functional annotation claims. Preserve source and version for
each annotation. An rsID may represent a cluster record and can be merged or
updated; it is not itself a stable allele description across all contexts.

## Representation, merges, and release pinning

Record input and returned forms separately: rsID, assembly accession/version,
chromosome/position, REF/ALT, HGVS expression with reference sequence and
transcript when supplied, and SPDI or other normalized form when returned.
Distinguish genomic HGVS from transcript/protein HGVS. HGVS and VCF use
different reporting conventions around repeats; indels can have equivalent
sequence descriptions at different positions. Normalize genomic VCF alleles
against the declared reference (including left alignment where applicable),
then compare the normalized sequence change, not raw strings alone. Use NCBI
Variation Services for explicit conversion/remapping and retain its output.

When an old rsID is merged, retain the queried ID, returned current ID, and the
service's explicit merge status. Do not infer identity solely from numeric
proximity or a redirect. Validate that the merged record has compatible
variant type, allele, and mapping. Multi-allelic records may contain several
alternate alleles; map the specific requested allele and retain the original
unsplit representation. Do not silently treat each alternate as the same
variant.

Pin NCBI endpoint, query, access date, assembly, and database/release metadata
when available. Preserve the returned record and response hash. If a service
does not report a release, say it is unreported rather than assigning a current
version. Keep annotations from different releases or endpoints separate.

## Dependencies and uncertainty

Variation Services remapping and dbSNP annotations may derive from shared
underlying submissions or assemblies; a successful mapping through two NCBI
views is not independent biological evidence. Record shared record IDs,
source accessions, submitters, and evidence sources where returned.

Carry uncertainty as unresolved assembly, transcript choice, strand, ambiguous
REF/ALT, multi-allelic decomposition, merge history, stale release, absent
annotation, or incomplete response. Report which representation choices alter
the mapping. Do not convert the number of database views into a confidence
score.

## Controls

Use a known pathogenic and known benign variant as identity/retrieval controls
only: choose variants from a pinned control list with recorded ClinVar accessions (no fresh ClinVar query per lookup), compatible
builds, and unambiguous alleles; confirm those expected records before the run.
These controls check retrieval and mapping, not whether dbSNP can classify
clinical truth. Include a deliberately nonexistent rsID/query as a negative
retrieval control and confirm that the API returned a complete no-match rather
than an error or truncated page. Record exact control IDs/queries, expected and
observed outcomes, and release. Do not cite or invent a control that the source
did not return.

## Sensitivity and applicability

Re-run identity checks after comparing input rsID and returned current rsID,
VCF and HGVS/SPDI representations, declared assembly and any explicit remap,
and available database releases. For repeat indels, compare normalized
sequence-level changes; for transcript-based HGVS, state the transcript choice.
A change in allele, locus, merge target, annotation linkage, or supported status
is material fragility. Report all mappings and leave the result inconclusive
until the intended representation is resolved.

dbSNP is primarily an identifier and variation resource; annotations may be
missing, stale, assembly-specific, or linked from other resources. It does not
establish disease relevance, patient genotype, penetrance, or pathogenicity.
This skill covers short variants and does not assume complete handling of
structural variants, complex haplotypes, or every transcript consequence.

## Common failure modes and detection

- **Build mismatch:** check assembly on both query and returned coordinate;
  remap explicitly or stop rather than comparing positions directly.
- **REF/ALT or strand mismatch:** validate alleles against the declared
  reference sequence; do not use reverse complement without recording and
  verifying the transformation.
- **Equivalent indel representations:** normalize against the same reference
  and compare sequence change; raw-coordinate mismatch alone does not prove a
  different allele.
- **Merged rsID treated as unchanged:** inspect explicit merge history and
  verify current allele/type/locus before accepting the target ID.
- **Multi-allelic splitting error:** preserve the original record and identify
  the exact alternate allele; verify each split maps to the requested sequence.
- **HGVS/VCF convention mismatch:** record reference sequence and transcript,
  convert through a stated service, and compare normalized alleles rather than
  strings.
- **Absence or failure overclaim:** check HTTP/API errors, page limits, and
  complete response; distinguish no match from missing annotation, null, and
  service failure.
- **Annotation provenance loss:** retain the linked source and release for each
  frequency or clinical assertion; a dbSNP link is not independent validation.

## Sources

- Sherry, Ward, and Sirotkin, “Use of molecular variation in the NCBI dbSNP
  database,” *Human Mutation*, 2000. Describes dbSNP submitted and reference SNP records.
- Holmes et al., “SPDI: data model for variants and applications at NCBI,”
  2020. Describes NCBI normalization and representation conversion across
  SPDI, HGVS, and VCF.
- den Dunnen et al., “HGVS Recommendations for the Description of Sequence
  Variants: 2016 Update,” 2016. Covers variant description conventions; it does
  not establish dbSNP record identity by itself.
