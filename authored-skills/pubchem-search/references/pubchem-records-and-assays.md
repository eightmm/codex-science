# PubChem record and assay interpretation

## Claim semantics

Separate the three PubChem record classes:

- **Substance (SID):** depositor-submitted content. Supports what that
  contributor supplied; retain contributor and source record provenance.
- **Compound (CID):** PubChem's derived, standardized structure record that may
  link multiple SIDs. Supports a normalized structure record, not experimental
  validation of every linked depositor statement.
- **BioAssay (AID):** assay description and tested Substance outcomes. A result
  supports that the depositor reported an outcome for a particular submitted
  substance and protocol; it does not alone validate mechanism, potency in a
  new context, or a universal property.

Classify property claims separately as computed, deposited, curated, or
measured. A CID property or depositor-provided value is not an assay result
unless the assay record and measurement support it. Use statuses supported,
contradicted, inconclusive, unavailable, or withdrawn.

## Source dependencies and versioning

Preserve SID, CID, AID, depositor/source organization, source identifiers,
protocol, record dates, and cross-references. Multiple SIDs may be deposited
by different organizations for the same compound and can be aggregated into a
CID; this is shared standardized identity, not independent experimental
replication. BioAssay rows refer to tested SIDs, so joining through a CID must
not erase which submitted material was tested. Pin a release or update date
when reported; otherwise record retrieval time and record-level dates. Treat
depositor records from a shared publication, dataset, or screening campaign as
dependent.

## Uncertainty

Record missing structure, failed standardization, incomplete assay data,
ambiguous depositor provenance, and unknown test material as distinct
uncertainties. Preserve null values and exact outcome labels; do not infer
missing values from linked records. A derived CID can compile information from
linked SIDs but does not make them identical in source or quality. Distinguish
PubChem processing/annotation from contributor-supplied text when displaying
evidence.

## Controls

- **Positive reference:** retrieve a known reference structure with a fixed
  CID/structure expectation; verify returned identifier, formula, and
  connectivity/stereochemistry relevant to the query.
- **Negative collision control:** submit a similar but distinct name as a
  decoy and verify resolution does not select the reference CID or silently
  map a salt/stereoisomer to the wrong material.
- **Record sanity:** for bioactivity, trace AID result to SID and depositor;
  if a CID link exists, retain it as an additional derived relationship.
  Verify response completeness, result identifiers, and continuation state.

## Sensitivity analysis

Repeat identity matching under explicit salt, tautomer, charge, and stereo
handling. For similarity/substructure, vary the requested threshold and result
cap; report the exact values returned and how the candidate set changes. For
activity, vary the cutoff, unit conversion, and aggregation (raw SID/AID rows
versus any summary). Call an inference fragile if plausible variants change
claim status, inclusion, ordering, or whether the selected material matches.
Never average outcomes from unrelated protocols or depositors without a
justified stratified rule.

## Applicability and failure modes

PubChem is a broad public archive; depositor coverage and record detail vary.
Substances can lack a usable structure, fail standardization, or represent
materials whose precise experimental state is unclear. BioAssay outcomes are
protocol- and depositor-specific, and database annotations may not be
equivalent to depositor conclusions.

| Failure | Detection and response |
|---|---|
| SID, CID, and AID conflated | Check identifier namespace and trace AID result to SID, then optional CID; report class explicitly. |
| Depositor provenance lost | Record contributing organization/source ID and distinguish contributor text from PubChem processing. |
| CID treated as proof that linked SIDs are equivalent | Inspect each SID structure/source; keep source rows distinct. |
| Assay outcome generalized into mechanism/property | Require protocol, tested SID, endpoint and independent support; downgrade to record-level report. |
| Missing or failed standardization hidden | Inspect structure availability and CID linkage; preserve absent mapping. |
| Partial response treated as no records | Check status, JSON structure, count/continuation and bounded pages; mark unavailable. |

## Sources

- Kim et al., *PubChem Substance and Compound databases*, Nucleic Acids
  Research, 2016.
- Kim et al., *PubChem 2023 update*, Nucleic Acids Research, 2023.
- PubChem Documentation, *Substances*, *Compound vs Substance*, *BioAssay
  Overview*, and *PUG REST*, accessed 2026.
