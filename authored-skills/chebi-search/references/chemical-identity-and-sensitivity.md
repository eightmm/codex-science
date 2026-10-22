# ChEBI structure matching and cross-source sensitivity

## Claim semantics

State whether a mapping is exact entity identity, parent/child relation,
synonym candidate, or cross-reference. A ChEBI identifier is stable for a
curated entity but does not make a linked PubChem CID, ChEMBL molecule, or
assay-tested material interchangeable. Label cross-source joins as mappings
with explicit evidence, not independent confirmation.

## Structure normalization

Retain query string and returned structure separately. Compare InChI/InChIKey
where available alongside full structure, formula, formal charge, isotope,
stereochemistry, and salt components. Record whether equality means exact
entity, same connectivity, or a broader parent relationship. Do not treat a
shared parent as proof that different protonation states, mixtures, salts, or
stereoisomers match. Preserve missing structure as unresolved.

## Dependencies and release

Capture ChEBI release/update or retrieval time, exact endpoint and parameters,
the returned ChEBI ID, and each external source ID with its own release/date.
An external cross-reference may be curated or propagated from another
resource; trace it before counting independent support. When the mapping is
not versioned, label it time-specific and preserve the complete response
artifact.

## Controls and sensitivity

Check one fixed reference compound and one decoy with a similar name but a
different chemical state. Compare exact name, synonym, and ID retrieval; vary
exact stereo/charge/salt matching versus declared parent-level matching. If
the downstream conclusion uses activity, vary its cutoff, unit conversion,
and aggregation while keeping entity mapping fixed. A change in selected
ChEBI entry, joined record set, role interpretation, or claim status means the
conclusion is fragile; report which choice caused it.

## Applicability and failure detection

Structure encodings may omit experimental protonation or material form.
Identifier crosswalks may be absent or outdated. ChEBI classification helps
organize chemical entities but cannot resolve sample composition or the
identity of a tested batch.

| Failure | Detection |
|---|---|
| Crosswalk merges distinct material states | Compare exact structure, salt, stereo and charge; retain one-to-many candidates. |
| Parent mapping used as exact match | Label relation explicitly and keep parent/child IDs. |
| Release mismatch concealed | Record each database version/date independently. |
| Downstream result depends on arbitrary threshold | Repeat predeclared threshold/unit/aggregation variants and report status changes. |

## Sources

- Heller et al., *InChI, the IUPAC International Chemical Identifier*, Journal
  of Cheminformatics, 2015.
- Hastings et al., *ChEBI in 2016: Improved services and an expanding
  collection of metabolites*, Nucleic Acids Research, 2016.
