# Platform implementation status

## Completed in 0.3.0

### Release and update safety

- Single release identity for plugin, package, MCP server, and release manifest.
- New plugin cachebuster.
- Candidate validation shared by fresh bootstrap and managed update hooks.
- Legacy transactional updater retained behind a strict validation entry point.

### Public-source access

- Legacy 34-tool MCP contract preserved.
- Connector Contract v2 implemented with typed requests, canonical receipts, snapshots, offline replay, and drift classification.
- New adapters added for ClinVar, dbSNP, gnomAD, ENCODE, JASPAR, UniBind, GEO, ArrayExpress, MetaboLights, BindingDB, openFDA, EMDB, Complex Portal, IntAct, and a versioned eQTL Catalogue release snapshot.
- Weekly structured operational drift workflow added.

### Evidence and review

- Evidence graph v2 relation typing and cycle detection.
- Dependency components for shared studies, cohorts, samples, mirrors, derivations, and model-training overlap.
- Hash-covered review receipts and deterministic staleness.
- Reviewer benchmark with critical/major recall, weighted precision/recall/F1, false-positive rate, and unsafe-pass rate.

### Literature synthesis

- Namespace-safe identifiers.
- Union-find study-family resolution.
- Publication-version relationships and canonical-version selection.
- Risk-of-bias domain/rationale contract.

### Model execution

- Model registry v2 maturity, contracts, receipt invalidation, and constrained selection.
- Deterministic executable SBDD acceptance with numeric metrics, thresholds, artifact bundle, model receipt, and review receipt.

### Artifact collaboration

- Hash-bound annotations and stale anchors.
- General run diff.
- Impact propagation and selective rerun planning.
- Offline workbench rendering.

## Deliberate boundaries

The new source adapters are not all labeled live-smoke-tested. Their maturity remains visible through `science_list_source_contracts`. Public API availability and legal reuse terms remain source-specific.

The executable SBDD example is a deterministic scientific-contract fixture. It is not a substitute for a prospective docking benchmark, experimental binding assay, or medicinal-chemistry decision.

The deterministic reviewer benchmark evaluates explicit defects in checked-in fixtures. It does not establish that a language-model reviewer will catch every scientific error.

## Next empirical milestones

The platform contracts are implemented. Future work should primarily add real redistributable scientific acceptance datasets and increase empirical coverage rather than introducing another incompatible schema:

1. externally pinned docking and structure-model runs using the same receipts;
2. real multi-source literature snapshots with redistributable extracts;
3. additional source replay fixtures and live-smoke promotion criteria;
4. larger reviewer defect corpora across omics, statistics, spectroscopy, and model evaluation;
5. human-in-the-loop annotation workflows on top of the existing sidecar contract.
