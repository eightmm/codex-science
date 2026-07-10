# Changelog

## Unreleased

- Completed the Codex-native tier: authored the remaining 23 DeepMind science skills (genomics, regulatory/TF, proteins, ontologies, pathways, chem/drug, and more) over their public APIs. The `cx` tier now covers all 35 DeepMind science skills; only the 3 infrastructure entries (`credentials`, `uv`, `workflow_skill_creator`) remain as `gdm` pointers. Catalog stays 187 (149 kdense + 3 gdm + 35 cx); 34 of 35 cx skills are active (only `cx-alphagenome-variant-analysis` needs a key).
- Added `cx-biorxiv-search`, `cx-europepmc-search`, `cx-openalex-search`, and `cx-clinical-trials-search` (all active): Codex-native skills over the public bioRxiv, Europe PMC, OpenAlex, and ClinicalTrials.gov v2 APIs; they supersede the corresponding DeepMind folders via `exclude`. The authored `cx` tier now covers 12 skills.
- Added `cx-pdb-search` and `cx-chembl-search` (active): Codex-native skills using the public RCSB and ChEMBL REST APIs directly (no built-in MCP tool exists for them); they supersede the DeepMind `pdb_database` and `chembl_database` folders via `exclude`.
- Added three Codex-native authored skills wired to the plugin's built-in MCP search tools: `cx-arxiv-search`, `cx-pubmed-search`, `cx-uniprot-search` (all active); they supersede the corresponding DeepMind `literature_search_arxiv`, `pubmed_database`, and `uniprot_database` folders via `exclude`.
- Added GitHub Actions CI (`.github/workflows/ci.yml`): runs `scripts/check.sh fast` on Python 3.11 and 3.12; README shows the build badge.
- Removed the redundant `catalog/source.json` (superseded by `catalog/sources.json`) and the unused ML-template stub `scripts/ml_smoke.py`; refreshed `docs/CONFIGS.md`, `docs/DATA.md`, and `docs/REPRODUCIBILITY.md` for the multi-source layout.
- Added a Codex-native authored skill tier (`authored-skills/`, `cx-*` source): first-class rewrites of high-value skills that map onto Codex tools instead of pointing at upstream. Shipped `cx-alphafold-structure-analysis` and `cx-foldseek-structural-search` (active) and `cx-alphagenome-variant-analysis` (inactive; needs an API key). Per-source `exclude` in `catalog/sources.json` drops the superseded DeepMind folders so each skill appears once.
- Added `scripts/install.sh`: one-command `curl … | bash` installer that clones into `~/.codex-science`, runs the light bootstrap, and registers the plugin globally with Codex (idempotent; re-run to update). README now leads with it and clarifies the plugin is user-global — no per-project install.
- Added a second skill source: Google DeepMind `science-skills` (38 skills), vendored under `vendor/gdm-science-skills/` at commit `0b42509` with preserved LICENSE, SKILL_LICENSES.md, and PROVENANCE.md.
- Generalized the catalog to multiple sources via `catalog/sources.json`; inventory schema bumped to 2 with per-skill `source` and per-source commit metadata (loader stays backward-compatible with schema 1).
- Source-prefixed every wrapper name (`kdense-*`, `gdm-*`) to keep provenance clear and avoid cross-source collisions; catalog now holds 187 wrappers.
- Added a source-level default license so skills without a per-skill license inherit their repository license (DeepMind: Apache-2.0); descriptions sanitize angle brackets for Codex validation.
- Simplified installation: `bootstrap.sh` is now a light installer (Python check + shallow submodule) and no longer requires `uv`; fixed a hardcoded validator path in `doctor.sh`/`check.sh` that broke setup on non-author machines.
- Refreshed README with a banner and an install/usage/license focus.

## 0.1.0

- Added Codex plugin and personal marketplace installation.
- Pinned 149 Scientific Agent Skills at commit `4d97e293dc6f604fb6b63dcd49b9028df413d65b`.
- Added explicit-invocation Codex wrappers for all 149 pinned skills.
- Made Codex Science an explicit, task-scoped mode and moved catalog wrappers out of global skill discovery.
- Added deterministic audit and conservative activation policy.
- Added coordinator, provenance, and reviewer skills.
- Added PubMed, arXiv, and UniProt read-only MCP tools.
- Cataloged 55 public sources documented by Claude Science.
- Added reviewed example artifact and deterministic checks.
