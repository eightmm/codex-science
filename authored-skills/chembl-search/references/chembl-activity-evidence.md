# ChEMBL activity evidence

## Claim semantics

Classify each statement before interpreting returned rows:

- **Deposited/curated record:** ChEMBL returns an identified molecule, target,
  assay, mechanism, or indication record. This establishes what the database
  contains at the pinned release, not independent experimental validation.
- **Reported measurement:** an activity row reports an endpoint and value for a
  particular compound, assay, target assignment, organism, and source document.
  Preserve relation (`<`, `=`, `>`, etc.), `standard_type`, `standard_value`,
  `standard_units`, and the raw activity ID. It supports that the value was
  reported/curated, subject to quality flags.
- **Comparable potency/property:** compare only after fixing structure, target,
  organism, assay context, endpoint, units, relation, validity status, and
  aggregation rule. A normalized number remains a scoped estimate, not an
  intrinsic universal property.
- **Mechanistic/clinical claim:** requires evidence beyond an activity or
  mechanism database row. ChEMBL mechanism/indication records are attributed
  records; they do not establish causal mechanism in a new context, efficacy,
  safety, or clinical advice.

Use statuses supported, contradicted, inconclusive, unavailable, or withdrawn.
Do not mark a claim supported when an essential assay/identity link is unknown.

## Source dependencies and independence

Pin the ChEMBL release/version when exposed by the service; if not exposed,
record retrieval timestamp and the version/status page checked. Preserve the
ChEMBL document/source, assay ID, activity ID, molecule ID, target ID, target
components, and organism. Assays and activities copied from one publication,
depositor, or shared experimental campaign are dependent even when represented
by separate rows. ChEMBL duplicate flags and identical compound/target/type/
unit/value rows are not independent replications. Record source-document and
assay links before aggregating; deduplicate only under a declared rule and keep
the uncollapsed rows.

## Uncertainty and interpretation

Retain reported relations and values; do not turn censored bounds into exact
values. Keep null units, unmapped targets, and missing assay metadata explicit.
Record uncertainty from assay variability, target mapping, species assignment,
structure state, source quality, duplicate handling, and any unit conversion.
`pChEMBL` is a negative base-10 molar scale for selected dose-response
endpoints when the record meets ChEMBL curation conditions. It helps compare
rough potency scale but does not erase assay protocol, construct, organism,
target confidence, or endpoint differences. It must not be treated as a
universal cross-assay ranking.

Inspect assay type (`B`, `F`, `A`, `T`, `P`, `U`) and assay-to-target
`confidence_score`; confidence describes target assignment, not measurement
precision or probability of biological truth. Preserve `data_validity_comment`
and activity comments. A validity flag is a review trigger; do not silently
delete the value. Distinguish manually validated values from unresolved flags.

## Controls

- **Positive reference:** query a known reference compound with a predeclared
  target and assay context. Check identity, expected record family, endpoint
  type/unit, and retrieval completeness. A mismatch tests the pipeline and
  does not authorize changing the expected result after seeing it.
- **Negative name control:** query a deliberately similar but distinct name
  (for example, a salt, stereoisomer, or near-spelling decoy). Confirm that
  identifier resolution and structure checks do not silently collapse it.
- **Sanity checks:** verify target components and organism, preserve relation
  symbols, reject impossible/malformed numeric conversions, inspect validity
  and duplicate comments, and compare record counts against pagination state.

## Sensitivity analysis

Repeat the selection using predeclared activity thresholds (include boundary
values), explicit unit conversions, and at least the unaggregated and proposed
aggregation view. Where aggregation is needed, compare median and a justified
alternative, stratify by assay type/target confidence, and never combine
incompatible endpoints. Record changed row IDs, estimate, and status. Call a
claim fragile if plausible choices change claim status, reverse ranking, move
the estimate across the declared decision threshold, or make it depend on a
single assay/source. Preserve all excluded rows and the reason.

## Applicability domain and failure modes

This method covers ChEMBL's curated public records, not all experiments or
chemical space. It is weakest for sparse targets, non-protein targets,
cell/organism assays, cross-species homologue mappings, unusual endpoints,
poorly specified constructs, and measurements without clear units or
protocols. Search failure, absent endpoint rows, and unresolved target mapping
cannot establish universal absence.

| Failure | Detection and response |
|---|---|
| Name resolves to wrong structure/state | Compare ChEMBL ID, structure, InChI/InChIKey where available, salt and stereo; keep candidates separate. |
| Activity treated as validated property | Require assay/target/context and explicit status; downgrade to reported measurement. |
| pChEMBL values treated as interchangeable | Stratify by type, assay, target, species, and confidence; report incompatibility. |
| Unit/relation conversion distorts evidence | Recompute from retained original value/unit/relation; compare threshold sensitivity. |
| Duplicate rows inflate support | Inspect duplicate flags, source document and assay; count shared source once under a stated rule. |
| Validity flag suppressed | Retain comment and compare flagged/unflagged views; unresolved flags limit claim. |
| Truncated response mistaken for no result | Check status, payload shape, page links/counts and bounded continuation; mark unavailable. |

## Sources

- Gaulton et al., *The ChEMBL database in 2017*, Nucleic Acids Research, 2017.
- Bento et al., *The ChEMBL bioactivity database: an update*, Nucleic Acids
  Research, 2014.
- ChEMBL Interface Documentation, *Assay and Activity Questions* and
  *ChEMBL Data Web Services*, accessed 2026.
