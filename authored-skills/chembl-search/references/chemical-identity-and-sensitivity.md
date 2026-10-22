# ChEMBL chemical identity and comparison sensitivity

## Claim semantics

Use an identity claim only for the specific ChEMBL molecule record and its
returned structure. A name/synonym match supports a candidate link, not chemical
equivalence. A measured-activity claim additionally requires the same chemical
state, target assignment, assay context, endpoint, relation, and units. State
whether the conclusion is record-level, measured, or an inference from a set of
measurements.

## Identity checks

Preserve the input string and selected `molecule_chembl_id`. Compare returned
canonical structure with the user's requested structure using InChI and
InChIKey where available, while retaining the original SMILES. Check molecular
connectivity, charge, stereochemistry, isotopic labels, and salt/counterion
handling. A shared InChIKey connectivity block can indicate a related parent
structure but is not proof that salt form or stereoisomer is identical. Do not
canonicalize away tautomeric or stereochemical distinctions without naming the
rule and showing the resulting mapping.

## Dependencies, release, and uncertainty

Record molecule record ID, structure representation and provenance, release or
retrieval time, source document, activity ID, assay ID, and target components.
ChEMBL standardized structures and assays may change across releases; do not
merge historical and current records without identifying the version. Several
activity rows may derive from one document or assay and therefore share
experimental provenance. Report unresolved identity, tautomer, salt, stereo,
target, and assay uncertainty as separate items rather than compressing them
into one confidence score.

## Controls and sensitivity

Resolve a known reference compound with a fixed expected ChEMBL ID/structure
and verify its returned representation. Use a near-name decoy representing a
different stereoisomer, salt, or analog to verify that resolution preserves
distinct IDs. Vary: (1) exact ID versus name-derived candidates; (2) parent
versus salt inclusion; (3) stereochemical/tautomer matching rule; (4) unit
conversion and activity cutoff; and (5) unaggregated versus justified
assay-stratified summary. A decision is fragile if any plausible variant
changes identity, included record set, ordering, or claim status.

## Applicability and failure detection

Structure matching is limited by missing, partial, or differently represented
structures and by chemistry normalization policies. It does not establish
sample purity, experimental material identity, or biological equivalence.

| Failure | Detection |
|---|---|
| Similar name resolves to another entity | Compare ID, InChI/InChIKey, full structure, charge and stereo; report all candidates. |
| Salt stripped or tautomer merged silently | Compare supplied and returned forms and record the explicit normalization rule. |
| Stereochemistry omitted | Check stereo annotations; treat unspecified stereo as unresolved. |
| Assay rows join through only a parent structure | Keep salt/state relation and assay provenance; do not imply exact-material replication. |
| Release drift alters identifiers or mapping | Pin version when reported; otherwise retain retrieval time and full IDs/structures. |

## Sources

- Heller et al., *InChI, the IUPAC International Chemical Identifier*, Journal
  of Cheminformatics, 2015.
- Gaulton et al., *The ChEMBL database in 2017*, Nucleic Acids Research, 2017.
- ChEMBL Interface Documentation, *Assay and Activity Questions*, accessed 2026.
