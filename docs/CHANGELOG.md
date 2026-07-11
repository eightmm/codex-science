# Changelog

## Unreleased

- Expanded scientific computer use: `cx-compute-environment` now covers local shell, Python, R, Julia, Jupyter, containers, CPUs, and GPUs with a non-sensitive capability probe. Added `cx-remote-scientific-compute` for existing SSH, Slurm/HPC, cloud GPU, and private object-storage workflows with login-node protection, one explicit target/data/resource/cost/cancellation approval packet, checkpointed monitoring, retrieval, and cleanup records. Catalog: 254 (149 kdense + 3 gdm + 102 cx).
- Added task-scoped Codex Science persistence with plugin-bundled `UserPromptSubmit` and `SessionStart` hooks. One explicit `$codex-science`/start request stores only a hashed `session_id` marker under `PLUGIN_DATA`; later turns, resume, and context compaction inject coordinator context and self-invoke the skill. Explicit stop, `clear`, and new tasks remain inactive, and abandoned markers expire after 180 days. Starter prompts now activate the mode explicitly, and installer/tests cover hook trust, privacy, isolation, malformed input, and lifecycle behavior.
- Audit fixes. **P0 search routing**: the skill-search tokenizer now splits on any non-alphanumeric, gives explicit skill-name tokens priority over generic prompt words, and ignores common English search stopwords. Hyphenated names (e.g. `cx-clinvar-search`) and full requests naming `sympy`, `pylabrobot`, `docking`, or `gromacs` now resolve to the intended skill. **P1 authored validity**: quoted the `description:` frontmatter in all authored skills (colons no longer break YAML), and `doctor.sh`/`check.sh` now validate `authored-skills/*` originals (not just generated wrappers). **P1 physical-experiment safety**: an audit `physical_lab` flag (pylabrobot, opentrons, cloud labs) injects a mandatory device/biosafety/dry-run/e-stop/billing gate into those wrappers. **P2 metadata**: `plugin.json` no longer hardcodes a stale skill count. Added regression tests for natural-name search and the physical-lab flag.
- Completed the remaining full-catalog audit remediation: every authored skill now has UI metadata, every active skill is regression-tested for natural-name discovery, vendored DeepMind content is locked by a deterministic SHA-256 tree digest, and all 48 upstream instructions over 500 lines receive heading-first progressive-loading guidance in their generated wrappers.
- Added six Codex-native analytical chemistry skills: spectroscopy and spectral
  inference, NMR structure analysis, mass-spectrometry identification, X-ray
  diffraction/scattering, chromatography quantification, and evidence-integrated
  chemical structure elucidation. The skills compose existing matchms, pyOpenMS,
  pymatgen, EDA, Fourier, and measurement-uncertainty capabilities while adding
  modality-specific provenance, artifact, calibration, identification-confidence,
  and alternative-hypothesis checks. Catalog: 253 (149 kdense + 3 gdm + 101 cx;
  141 active).
- Added eighteen Codex-native mathematics and physics skills spanning probability,
  statistical design, optimization, asymptotics, complex/Fourier analysis,
  measurement uncertainty, continuum mechanics, relativity, computational
  validation, control, geometry/topology, Lean theorem proving, optics, condensed
  matter, nuclear/particle physics, inverse problems, chaos, and tensor geometry.
  Each workflow includes explicit assumptions, method selection, verification, and
  source basis. Catalog: 247 (149 kdense + 3 gdm + 95 cx; 135 active).
- Added ten Codex-native, textbook-grounded mathematics and physics skills:
  mathematical problem execution, proof/counterexample, linear algebra, ODE/PDE,
  numerical error control, dimensional analysis, classical mechanics,
  electromagnetism, thermodynamics/statistical mechanics, and quantum mechanics.
  Seven openly licensed textbooks were downloaded to a Git-ignored local cache and
  recorded by URL, edition, license, and SHA-256 in `docs/TEXTBOOK_SOURCES.md`.
  Catalog: 229 (149 kdense + 3 gdm + 77 cx).
- Added verified current model workflows for Biohub ESMFold2 and ESMC,
  AlphaFold3, Protenix-v2, SimpleFold, RoseTTAFold All-Atom, RFdiffusion, and
  BindCraft. Added `cx-modeling-problem-execution`: when concrete inputs are
  supplied, Codex Science now continues after one approval through preflight,
  a smallest falsifying smoke run, full execution, downstream analysis,
  provenance, and review. Catalog: 219 (149 kdense + 3 gdm + 67 cx).
- Added eleven Codex-native workflows from Claude Science's publicly documented
  featured skill set: indication dossier, AlphaFold2, Chai-1, public ESMFold,
  OpenFold3 preview, ProteinMPNN/LigandMPNN/SolubleMPNN, ESM-2, Evo 2, Borzoi,
  scGPT, and scvi-tools. Each compute skill pins code/weights/configuration,
  gates downloads/GPU/remote sequence transfer, and records artifacts and
  scientific evaluation boundaries. Catalog: 210 (149 kdense + 3 gdm + 58 cx).
- Expanded the read-only MCP from 3 to 15 public sources: PubMed, arXiv, UniProt,
  RCSB PDB, ChEMBL, PubChem, Europe PMC, OpenAlex, ClinicalTrials.gov v2,
  InterPro, QuickGO, OLS, Reactome, STRING, and AlphaFold DB. Added ten
  Codex-native modeling workflows for molecular input preparation, AutoDock
  Vina, GNINA, DiffDock, docking validation, OpenFF, OpenMM, GROMACS, MDAnalysis,
  and PLIP. The audited catalog is now 199 skills (149 kdense + 3 gdm + 47 cx).
- Added real execution capability (Codex-native, `uv`-based): `cx-compute-environment` builds an isolated `uv` environment and runs code end-to-end, and `cx-boltz-structure-prediction` installs and runs the open-source Boltz model to predict structures/affinity from sequence. Both use an "ask once, then run to completion" gate for install/download/compute. The coordinator now routes modeling work to them. Catalog is 189 (149 kdense + 3 gdm + 37 cx).
- `scripts/install.sh` now runs a runtime self-check after registering: it drives the MCP server with a real `initialize` + `tools/list` handshake and fails loudly if the machine's `python3` cannot run it — so a successful `curl … | bash` means the plugin is ready to use, with no package install or `uv`.
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
