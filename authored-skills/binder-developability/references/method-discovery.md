# Method discovery

## Search before selection

Use dated seeds in `methods.json` as discovery starting points, not a fixed list.
Search current official source/release documentation and primary papers. Check
input type, supported construct/chemical domain, preparation, endpoint meaning,
training overlap, calibration, terms, hardware and independent validation. Keep
`discovered`, `documented` and `real-pilot` evidence distinct. Method discovery
never proves the method is installed or authorizes installation or heavy compute.

## Additive selected-method descriptor

Save a run-local descriptor as an ordinary hashed artifact with method ID,
repository URL/exact commit, weight/database identities where applicable,
source URLs/access date, route, input/output hashes, score direction and units,
controls, applicability and limits. A new descriptor needs no global registry or
schema change. Reuse the existing compute environment and provenance routes;
stop when an endpoint or preparation cannot be matched. Descriptor acceptance
is separate from scientific validation and engine execution.

## Current implementation

Sequence observations and supplied matched-panel margins only; no TAP/TNP execution, aggregation/solubility/expression/immunogenicity predictor, antibody annotation, independent assay or clinical assessment.
