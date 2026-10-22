# UniProtKB record and annotation evidence

## Claim classes

Keep these classes distinct in the evidence table and claim ledger:

Use only these claim statuses: **supported** means the stated claim is
supported at the specified record/evidence level; **contradicted** means
retrieved evidence conflicts with it; **inconclusive** means evidence exists
but does not decide it; **unavailable** means the source or required evidence
could not be retrieved or was not reported. Never use record status as a
substitute for this claim status.

- **Record identity:** UniProt returned an accession, entry name, organism and
  sequence. This establishes the contents of the retrieved database snapshot,
  not identity of an experimental sample unless mapping is independently
  supported.
- **Reviewed status:** Swiss-Prot means manually reviewed; TrEMBL means
  unreviewed. This describes record processing, not the evidentiary status of
  every annotation. Store the status observed at the pinned entry version.
- **Literature-supported annotation:** assign only when the annotation has a
  traceable cited source and its evidence qualifier supports the specific
  claim. Inspect the publication and experimental conditions for a material
  claim; a citation attached to an entry is not automatically support for
  every annotation there.
- **Computationally supported annotation:** retain its method, evidence code,
  and any prediction qualifier. Do not restate it as direct experimental
  observation.
- **Record-reported sequence or feature:** report the exact accession and
  sequence/feature version and coordinates; this is a database assertion,
  distinct from independent validation of the sample.
- **Conflict or absence:** conflicting annotations remain separate with their
  provenance. A field not returned is unavailable for that query/version, not
  a negative biological finding.

## Identity, dependencies, and version pinning

Record primary accession, entry version, canonical sequence version, isoform
identifier where relevant, taxon ID and scientific name. Check secondary
accessions, merged/split history, deleted-entry status and cross-reference
mapping before joining records. A gene symbol can map to multiple loci,
species, paralogs or isoforms. Sequence equality or similarity is not a
substitute for resolving the biological entity.

UniProt is a curated knowledgebase with evidence from publications, curator
assessment, computational analysis and imported sources. Trace each claim to
its annotation evidence and source records. A UniProt statement and the cited
publication may be the same evidence lineage; do not count them as two
independent confirmations. Multiple annotations may share the same paper,
organism, assay, submitted record or computational pipeline.

Pin the UniProt release when supplied by the API or bulk source. Record access
date/time, endpoint, exact query, entry and sequence versions, response status,
pagination state and response hash. If no release identifier is reported,
record it as unavailable and preserve the retrieved record artifact. For
reproduction, use the archived entry version where available; otherwise mark
that exact historical content could not be re-fetched.

## Uncertainty and controls

Carry uncertainty at the annotation level: evidence qualifier/code, cited
source, conflicting evidence, missing fields, isoform ambiguity, organism
mapping and record version. Do not collapse these into one confidence score.
Distinguish uncertainty in the underlying biology from uncertainty caused by
identifier mapping, search coverage or source freshness.

Use a known positive accession that matches the requested taxon and annotation
as a retrieval sanity check. Use a deliberately unsupported name or impossible
taxon/query as a negative control to confirm that errors and zero hits remain
distinguishable. Neither control validates the biology of the target result.

## Sensitivity and applicability

Repeat the search over plausible synonyms, gene/protein name variants,
accession aliases, taxonomic scope and relevant filters. Compare candidate
accessions, reviewed/unreviewed composition, annotation provenance and claim
status. Call the result fragile when a plausible query change alters the target
identity, evidence class, or decision-bearing conclusion. Record the variants
and changes; do not choose the most favorable query after seeing outcomes.

The method is applicable to retrieving and reconciling UniProtKB records. It
does not establish that a deposited annotation applies to a particular sample,
validate assay quality, infer causal function from association, or resolve
sequence/structure questions beyond the returned record. Search results can be
incomplete because of query syntax, indexing, taxonomy, release changes,
unreviewed proteome changes, pagination caps or access failures.

## Failure modes and detection

| Failure | Detection and handling |
| --- | --- |
| Truncated pagination | Compare returned page/continuation state with the declared cap; preserve incomplete status as unavailable. |
| Silent empty result | Check HTTP status, response shape and exact query; distinguish valid zero hits from API error, wrong field or unsupported syntax. |
| Stale/merged accession | Inspect entry history and secondary/primary mappings; report the resolved accession and mapping chain. |
| Wrong species or isoform | Compare taxon, sequence and isoform; stop if unresolved identity changes the claim. |
| Reviewed-status overclaim | Inspect each annotation's evidence; do not treat Swiss-Prot review as experimental validation. |
| Provenance double count | Trace annotations to common publications, submissions or pipelines; combine shared lineage as dependent evidence. |
| Missing annotation overread | Check record version, sequence coverage and returned fields; report unavailable rather than biological absence. |
| Query-sensitive candidate set | Repeat plausible synonym/taxonomy/filter variants and report material changes. |

## Sources

- UniProt Consortium. *UniProt: the Universal Protein Knowledgebase in 2023*.
  Nucleic Acids Research (2023). Supports the resource scope and annotation
  framework, not independent validation of any target annotation.
- UniProt Help, *Entry information section*, *Entry history*, and *Accession*.
  These define reviewed status, version/history and accession mapping; consult
  the live help pages for current behavior.
