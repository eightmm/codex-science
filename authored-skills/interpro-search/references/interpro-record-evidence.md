# InterPro integrated and member-database evidence

## Claim classes

Keep the following evidence classes distinct:

Use only these claim statuses: **supported** means the stated claim is
supported at the named record or evidence level; **contradicted** means
retrieved evidence conflicts with it; **inconclusive** means evidence exists
but does not decide it; **unavailable** means the source or required evidence
could not be retrieved or was not reported. Database membership status does
not by itself establish experimental function.

- **Integrated-entry claim:** InterPro reports an integrated family, domain,
  site or hierarchy entry with a name/description. This is a database
  integration assertion, not direct observation that a target protein has a
  biochemical function.
- **Member-signature claim:** a named member database and signature method
  matches a sequence. Report the member database, signature accession,
  sequence, coordinates and method provenance; do not replace this with only
  the aggregate InterPro accession.
- **Protein-membership claim:** a specific UniProt protein is listed as a
  member of an entry in the retrieved release. This supports membership in the
  database snapshot, not necessarily an independently validated biological
  classification.
- **Architecture claim:** ordered matches and coordinates describe the
  returned sequence and release. Do not infer domain interactions, structure,
  or function from architecture alone.
- **Functional interpretation:** assign a direct functional claim only when
  the specific annotation has suitable evidence beyond a family/domain label.
  Preserve generalizations and uncertainty from the member database.
- **No-match claim:** absence from returned members means no match in the
  query scope and snapshot, not biological absence of the domain or family.

## Identity, dependencies, and version pinning

Resolve the canonical UniProt accession, isoform and taxon before comparing
protein matches. Record sequence version or sequence hash where available;
domain coordinates are meaningful only against a specified sequence.
Distinguish `IPR` integrated accessions from member-database signature IDs and
protein accessions. Record entry type (family, domain, site or other returned
type) and hierarchy/relationships without collapsing them.

InterPro integrates signatures from member databases using different
classification methods. An integrated entry can group related signatures;
member databases can share source sequence sets, literature, algorithms,
curation or propagated annotations. Multiple signatures or an InterPro entry
plus its contributing signature are not automatically independent evidence.
Trace each result to the member database and, where available, the source
release and annotation provenance.

Pin the InterPro release reported by the API or response; also record
UniProt/source sequence version when available. Record exact endpoint and
parameters, access time, response status, pagination token/pages, query cap,
entry/signature IDs and response hash. If release or member-database version
is absent, label it unavailable and retain the response artifact rather than
guessing a version.

## Uncertainty and controls

Carry uncertainty for protein/isoform mapping, taxonomy, sequence coverage,
signature method, member-database version, coordinates, integrated-entry
mapping and missing pages. Keep disagreement between member databases
visible; do not resolve it by counting signatures or averaging scores. A
reported coordinate is a sequence match range, not a validated structural
boundary unless a source explicitly establishes that interpretation.

Use a known positive protein/entry whose match is documented in the same
release to check endpoint and identifier handling. Use a negative query such
as an invalid accession or incompatible taxon to confirm that empty results,
input rejection and API failure remain distinct. These checks do not validate
the target's biological function.

## Sensitivity and applicability

Vary plausible protein synonyms, canonical/isoform accession, taxonomy,
sequence release, page/result cap and relevant filters. For a domain
comparison, vary sequence identity/coverage criteria only when those are part
of the query and retain the exact values. A conclusion is fragile if a
reasonable identity, taxon, release or filter change alters protein
membership, domain order/boundaries, member-database agreement, or the
decision-bearing interpretation. Record each variation before summarizing.

InterPro is designed to classify protein families, domains and sites by
integrating member-database signatures. Coverage and resolution depend on
sequence quality, database-specific model scope, submitted sequence set,
taxonomic representation and release. Short, low-complexity, disordered,
fragmentary or divergent sequences may yield no match or ambiguous matches.
Integration can lag source updates; a missing annotation or protein member
does not establish biological absence. This search does not replace
InterProScan on a private/novel sequence when public submission would violate
confidentiality; use the permitted local route if authorized.

## Failure modes and detection

| Failure | Detection and handling |
| --- | --- |
| Truncated pagination | Compare next-page state and page count to the declared cap; label enumeration incomplete. |
| Silent empty result | Validate HTTP status, JSON schema, accession format, endpoint and query; distinguish zero hits from errors. |
| Wrong protein or isoform | Check canonical accession, taxon and sequence; stop if coordinate mapping is ambiguous. |
| Integrated entry mistaken for independent evidence | Trace contributing member signatures and shared data/method lineage; report dependence. |
| Member database omitted | Preserve signature database and accession for every contributing match; do not report only IPR IDs. |
| Match interpreted as biochemical function | Separate family/domain classification from functional evidence; downgrade unsupported function claims. |
| Coordinates compared across sequences | Bind coordinates to accession and sequence version/hash; remap before comparing. |
| Release drift | Capture reported release and access date; compare only pinned or explicitly version-mismatched snapshots. |
| No match overread as absence | Check sequence quality, length, coverage and model scope; report no returned match only. |

## Sources

- Mitchell et al. *InterPro in 2021—improving coverage, classification and
  access to protein sequence annotations* (2021), Nucleic Acids Research.
  Supports the integrated resource model and member-database coverage, not
  independent experimental confirmation of every match.
- Hunter et al. *InterPro: the integrative protein signature database* (2009),
  Nucleic Acids Research. Describes integration of protein signatures and
  entry relationships.
- InterPro, *InterPro data* and *Getting data from InterPro*. Consult current
  documentation for member databases and API response behavior.
