# NCBI sequence record handling

## Claim semantics and record classes

The primary output is an identified database record, not a claim about biology. Assign status `retrieved-and-validated`, `retrieved-with-limits`, `unavailable`, or `failed`; reserve scientific claim statuses `supported`, `contradicted`, `inconclusive`, and `unavailable` for downstream interpretations.

- **RefSeq:** identify the accession.version and record type; RefSeq status does not guarantee that a record is experimentally validated or suitable for every organism/claim.
- **GenBank:** preserve the submitted record's accession.version, organism annotation, source/features, and update context; annotations and sequence may change between versions.
- **Patent sequence:** preserve the patent/sequence identifier and source record context. Patent inclusion is not evidence of expression, function, novelty, or clinical relevance.
- **CDS-derived protein:** record the source nucleotide record, CDS feature coordinates, genetic code table, frame, partial-start/stop state, and translation exceptions. A derived translation is not an independently retrieved protein record.

Accession without version is mutable. Store the returned accession.version exactly. For search results, retain the exact search basis and candidate identifiers; gene symbols and names can map to paralogs, synonyms, pseudogenes, or multiple organisms.

## Source dependencies and versioning

Record database (`protein` or `nuccore`), record class, accession.version, organism and taxon as reported, molecule type, feature/region, retrieval date, query, endpoint, and source update/release metadata when returned. Keep raw response bytes or file and a cryptographic hash as provenance. Link derived CDS translation to its exact nucleotide record/version and translation settings.

Do not count the same sequence replicated across NCBI views or formats as independent evidence. RefSeq records may be derived from GenBank or other source records; retain cross-references and provenance when visible. Record search result ordering and excluded candidates because a changed database can change future results.

For each request, preserve the method and parameters needed to reconstruct the search without exposing unnecessary account/access details: database, operation (`esearch` or `efetch`), query terms, requested record type/format, and retrieval date. Keep the raw URL/query artifact access-controlled if it contains sensitive user search terms.

Use the exact public E-utilities base endpoint already named in the skill. Follow current NCBI request-rate limits; the cited documentation advises considering an API key above 3 requests per second per IP, so this no-credential workflow stays at or below 3 requests per second. Avoid unnecessary repeated requests. Set the E-utilities `tool` value to name this workflow (`ncbi-sequence-fetch`). Send an `email` contact only when the user supplied or approved that contact for this purpose; otherwise omit it. Never fill it in from the environment or a local profile. Do not add an API key or other account/access parameter. Bound transient retries and pause or stop when the service indicates throttling; a retry loop must not amplify load.

For gene+organism queries, preserve the original search string and the resolved taxon constraint. If the response contains more candidates than can be reviewed, do not select the first result silently: narrow the query with a justified identifier, report the unresolved candidate set, or stop before fetching full sequences.

For accession retrieval, preserve the requested identifier separately from the returned identifier. If a version is suppressed, superseded, replaced, or maps to a different record, state that mapping rather than rewriting the original request.

## Uncertainty and completeness

Preserve uncertainty about identity, annotation, completeness, organism, record version, and translation. A missing field differs from a null field; zero records differs from a failed request; an incomplete response differs from a complete record with an annotated partial sequence. Report each explicitly.

Check response status and size, parser completion, final record terminator/structure where applicable, header/accession agreement, sequence alphabet, declared length when present, and feature bounds. Do not infer completeness from a successful HTTP response alone. Retain truncation or parse failures and do not silently repair them.

## Controls and sanity checks

- For accession retrieval, compare returned accession.version and record type with the requested identifier and database.
- For a gene+organism search, verify taxon and gene context for each candidate; inspect paralogs and one-to-many matches before selection.
- For CDS translation, independently verify coordinate range, strand/frame, genetic code, partial flags, and annotated translation when present; retain the nucleotide source.
- For FASTA, require a parsable header and sequence content, expected alphabet, nonempty sequence unless explicitly requested, and header accession consistent with the record.
- For GenBank, require a parsable record boundary and feature table; confirm the extracted region lies within sequence coordinates.
- For large responses, compare fetched record count and identifiers against search results and detect truncation before treating output as complete.

If a record lacks enough annotation to perform a check, report the missing control and limit the identity claim accordingly.

## Sensitivity analysis

When a search is ambiguous, vary gene synonym, organism spelling/taxon constraint, database, and relevant record class while preserving the original query. Compare candidate sets and explain whether accession choice changes. For mutable records, compare a pinned accession.version with the current unversioned lookup only when requested and safe; report sequence or annotation differences.

For translation, check plausible alternative frames or genetic codes only when annotation is uncertain and record them as diagnostics, not as silent replacements. A result is fragile if reasonable query/record choices change the selected sequence, molecule type, translated product, or downstream conclusion.

## Applicability domain and failure modes

NCBI sequence retrieval supports database-record identity and sequence handling. It does not establish that a sequence is expressed, functional, disease-causing, present in a patient's sample, or experimentally correct. Search sensitivity depends on names, taxonomic annotation, database scope, record updates, and indexing.

| Failure mode | Detection and response |
| --- | --- |
| Accession version omitted or changed | Validate and record returned accession.version; report mutable or superseded identity. |
| Gene symbol retrieves a paralog or other species | Check taxon, synonyms, locus, and candidate set; stop until identity is resolved. |
| RefSeq/GenBank/patent records treated as equivalent | Preserve record class and provenance; state what the record class does and does not establish. |
| CDS translated with wrong frame/code or partial flags ignored | Verify feature coordinates, strand, code, frame, and partial state; mark translation inconclusive if unresolved. |
| FASTA or GenBank response is truncated or malformed | Check record structure, counts, headers, length, and parser completion; retry only transient failures and retain failed output. |
| Search no-hit reported as biological absence | Separate query/database scope from biological evidence; report retrieval unavailability only. |
| Sequence used as expression/function evidence | Restrict statement to database record identity and route biological interpretation to appropriate evidence sources. |

## Sources

- Sayers et al., **Database resources of the National Center for Biotechnology Information** (2019), Nucleic Acids Research: NCBI resource context; it does not validate any individual retrieved record.
- Sayers, E., **The E-utilities In-Depth: Parameters, Syntax and More** (2009), Entrez Programming Utilities Help, NCBI: endpoint, request-rate, and `tool`/`email` guidance.

## Sequence feature interpretation

When a request targets a CDS, gene, mature peptide, or named region, use annotated feature coordinates and strand rather than guessing from sequence length or a matching motif. Record coordinate convention and whether endpoints are inclusive as defined by the source format.

Partial-start or partial-stop flags mean that a translated product may lack terminal residues; they are not parse errors and should not be silently padded. Frameshifts, exceptions, or translational table overrides must be recorded with the derived sequence.

FASTA is a sequence representation with limited annotation. If downstream use requires features, qualifiers, or provenance, preserve the GenBank or other requested annotated record in addition to any FASTA export.

Never infer the organism solely from a header description when a taxon identifier or source feature is available. A mismatch between requested organism and returned source annotation requires resolution before presenting the record as the requested sequence.

If a parser normalizes whitespace or case, retain the original response artifact and record the parser/version; normalization must not change residues or erase ambiguity symbols.
