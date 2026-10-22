# PubChem chemical identity and search sensitivity

## Claim semantics

An identity claim names the exact structure representation and PubChem record
class: a SID asserts depositor identity, while a CID is PubChem's standardized
structure grouping. A search result by name is a candidate only. A structure
match must specify whether it means exact stereochemical identity,
connectivity, or a broader similarity relation. Similarity is not identity;
property and bioactivity claims need separate source-specific evidence.

## Structure comparison

Retain input name, SMILES or InChI, selected CID/SID, and returned canonical and
isomeric SMILES. Compare InChI/InChIKey where available, but do not use a
connectivity-only match to assert equal stereochemistry or salt state. Inspect
charge, counterions, mixtures, isotopes, tautomeric representation, and
unspecified stereocenters. State which fields were returned versus inferred.
Keep input and standardized structures side by side; do not overwrite the
original query.

## Dependencies, release, and uncertainty

Record PUG-REST endpoint/query, retrieval time, reported update/release and
record dates, CID/SID, depositor IDs, and linked AIDs. Standardization is a
PubChem transformation, so linked SIDs share a normalized CID without sharing
depositor evidence. Name resolution may produce several candidates, and
standardization can be incomplete or fail. Report identity uncertainty at the
level of the unresolved atom/state distinction rather than a single generic
confidence.

## Controls and sensitivity

Use a known reference compound with a predeclared expected identifier and
structure. Include a decoy name that differs by salt, stereo, or close spelling
to check collision handling. Re-run the candidate selection with: exact
structure versus parent structure; stereo-specific versus connectivity-only
matching; salt/tautomer inclusion; and for similarity searches, more than one
declared threshold and result cap. If the search supports activity selection,
also vary the activity cutoff, unit conversion, and grouping/aggregation rule.
Record candidate IDs gained/lost and any claim-status change. Treat any
decision-changing variation as fragile and report the variant explicitly.

## Applicability and failure detection

PubChem standardization does not certify the material used in an experiment,
purity, protonation under assay conditions, or biological interchangeability.
Similarity/substructure results depend on query representation and chosen
threshold. Sparse or missing depositor details limit identity resolution.

| Failure | Detection |
|---|---|
| Name collision | Retain all CIDs and compare formula, structure, charge, stereo and depositor/source context. |
| Salt or mixture collapsed | Inspect SID structure against standardized CID; preserve source form and components. |
| Stereo omitted by representation | Compare isomeric structure/InChI; unknown stereo remains unresolved. |
| Similarity presented as equivalence | Report search mode and threshold; label candidates as similar, not identical. |
| Standardized CID mistaken for tested material | Trace assay outcome back to tested SID and depositor record. |

## Sources

- Heller et al., *InChI, the IUPAC International Chemical Identifier*, Journal
  of Cheminformatics, 2015.
- Kim et al., *PubChem Substance and Compound databases*, Nucleic Acids
  Research, 2016.
- PubChem Documentation, *Substances* and *PUG REST*, accessed 2026.
