# ChEBI entity identity and ontology evidence

## Claim semantics

Distinguish the following claim classes:

- **Curated ChEBI record:** the database contains an entry with a stable
  `CHEBI:<id>`, name, and available chemical annotations at the recorded
  release. This is a claim about the curated record.
- **Chemical identity:** a candidate matches the intended molecular entity
  only when structure/state evidence (where available) agrees on connectivity,
  charge, isotope and stereochemistry. Name/synonym matches alone are not
  sufficient.
- **Ontology classification:** a relation such as is-a, has-role, or a
  parent/child edge supports the specific ontology assertion. It does not
  establish a measured activity or a context-specific mechanism.
- **Measured/validated property:** requires separate experimental or curated
  property evidence. A ChEBI role or cross-reference alone does not validate
  potency, mechanism, efficacy, or clinical use.

Name the relation and source entry supporting each ontology claim. Report
statuses as supported, contradicted, inconclusive, unavailable, or withdrawn.

## Entity structure and role interpretation

ChEBI covers chemically distinct entities including molecules, ions, groups,
and classes. Determine whether a candidate is a specific molecule, chemical
class, salt, mixture, isotopologue, or other entity before treating it as a
compound. Preserve identifier, preferred name, synonyms, formula, structure,
charge, stereochemical detail, and ontology edges exactly as returned.

An ontology parent/child relationship is not automatically chemical
equivalence. A role describes a behavior or application attributed to an
entity in the ontology; it is not a per-assay observation. Check the relation
type, edge direction, and definition. Missing role annotations do not prove an
entity lacks that role in nature, and a role does not show a specific assay
result.

## Dependencies, release, and uncertainty

Record the ChEBI release/update if exposed, otherwise access time and response
metadata, plus exact search term, endpoint and returned identifier. Preserve
cross-references to ChEMBL/PubChem as links, not independent confirming
observations. If multiple sources propagate an identifier or ontology mapping,
record the shared upstream record. Report uncertainty separately for name
resolution, structure/state, ontology relation semantics, and release drift.
An absent structure or role is missing annotation, not evidence of chemical
absence or biological inactivity.

## Controls

- **Positive identity reference:** query a well-characterized entity with a
  predeclared ChEBI ID and check returned label, formula, structure and entity
  class where populated.
- **Negative collision control:** query a similar spelling or related entity
  with a different salt, stereo, charge, or ontology class. Verify the result
  remains a separate candidate.
- **Ontology sanity:** inspect relation labels and direction, verify that a
  role is not presented as an assay measurement, and ensure null structure or
  role data remains null. Verify candidate/page counts and response validity.

## Sensitivity analysis

Repeat name resolution using exact name, known synonym, and identifier; compare
the candidate set. Vary whether parent classes/children are included and whether
structure matching requires exact stereochemistry, charge, or salt form. For
cross-source activity conclusions, vary the declared activity threshold, unit
conversion, and aggregation, retaining ChEBI identity as a separate axis. A
claim is fragile when a plausible candidate or hierarchy rule changes selected
entity, inclusion, downstream status, or whether the role is interpreted as
measured evidence. Record each changed ID and rule.

## Applicability and failure modes

ChEBI is a curated chemical ontology, not a complete catalog of all submitted
chemical records, assay outcomes, or context-dependent mechanisms. Its entity
granularity may not match a supplier salt, assay preparation, or biological
state. Cross-database references can be absent or stale and require source
verification.

| Failure | Detection and response |
|---|---|
| Synonym collision selects wrong entity | Compare identifier, formula, charge, structure, and entity class; retain alternatives. |
| Parent class mistaken for one molecule | Inspect entity type and hierarchy edge; do not use class ID as compound ID. |
| `has role` mistaken for measured activity | Preserve relation label and downgrade to ontology classification. |
| Parent/child edge treated as structural equivalence | Check edge semantics and compare structures independently. |
| Missing role interpreted as no activity | Report annotation absence; seek a separate assay source if required. |
| Cross-reference treated as independent evidence | Trace linked source/release and record shared provenance. |
| API failure or partial page read as absence | Validate status, payload, count and continuation; mark unavailable if incomplete. |

## Sources

- Degtyarenko et al., *ChEBI: a database and ontology for chemical entities
  of biological interest*, Nucleic Acids Research, 2008.
- Hastings et al., *ChEBI in 2016: Improved services and an expanding
  collection of metabolites*, Nucleic Acids Research, 2016.
- EMBL-EBI ChEBI, *About ChEBI* and *ChEBI Ontology* training documentation,
  accessed 2026.
