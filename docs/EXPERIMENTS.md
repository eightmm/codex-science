# Experiments

Research experiments belong in the user's research project and follow the `$science-provenance` artifact contract.

The checked-in smoke example is `examples/reviewed-run/`: a deterministic mathematical comparison with code, execution log, result, environment, hashes, claim, and passed record-based review.

The checked-in life-science acceptance run is
`examples/life-science-reviewed-run/`. It tests whether three public PheWAS
sources provide comparable directional diabetes evidence for one normalized
variant query. The pre-registered hypothesis was not supported: FinnGen and
UKB/TOPMed had descriptive signals, but only FinnGen had verified build metadata
in the retrieval contract and BioBank Japan returned no comparable diabetes
phenotype. Missing or build-incomparable evidence is not treated as negative
evidence.
