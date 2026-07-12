# Authored (Codex-native) skills

First-class skills authored in this repository, as opposed to thin wrappers that
point at pinned upstream instructions. They are for high-value cases where a
Codex-tailored rewrite is clearly better than a pointer — the instructions map
onto Codex tools (shell with approval, `uv run`, read-only MCP) and drop
assumptions from other agent runtimes.

Each is registered as its own catalog source in `catalog/sources.json` under the
`cx` prefix (e.g. `cx-foldseek-structural-search`) and flows through the same
audit and wrapper generation as every other skill. When an authored skill
supersedes an upstream one, the upstream folder is listed in that source's
`exclude` so the two do not both appear.

The `cx` tier (127 skills) covers **every DeepMind science skill** (35 skills);
only the three infrastructure entries (`credentials`, `uv`,
`workflow_skill_creator`) remain as `gdm` pointers. Each superseded upstream
folder is listed in the `gdm` source's `exclude`, so each capability appears
once.

Ninety-two of the 127 are original **execution/modeling and synthesis** skills (no upstream): `cx-compute-environment`
builds an isolated `uv` environment and runs code; `cx-boltz-structure-prediction`
installs and runs the Boltz structure-prediction model; ten more cover molecular
input preparation, AutoDock Vina, GNINA, DiffDock, docking validation, OpenFF,
OpenMM, GROMACS, MDAnalysis, and PLIP. All use an "ask once, then run to
completion" gate for install/download/compute. The expanded set also covers the
publicly documented Claude Science featured workflows for indication dossiers,
AlphaFold2, Chai-1, public ESMFold, OpenFold3 preview, ProteinMPNN variants,
ESM-2, Evo 2, Borzoi, scGPT, and scvi-tools.
Current additions include Biohub ESMFold2 and ESMC, AlphaFold3 with its
restricted asset gate, Protenix-v2, SimpleFold, RoseTTAFold All-Atom,
RFdiffusion, BindCraft, and a concrete-problem executor that drives approved
work through downstream analysis and review.

Twenty-eight textbook-grounded mathematics and physics skills cover rigorous
proof/refutation, core mathematical methods and physical theories, experimental
uncertainty, computational validation, inverse problems, nonlinear dynamics, and an
end-to-end mathematical problem runner. The downloaded books stay in a Git-ignored
local cache; [`docs/TEXTBOOK_SOURCES.md`](../docs/TEXTBOOK_SOURCES.md) records URLs,
editions, licenses, hashes, consulted web references, and explicit exclusions.

Six analytical-chemistry conductors add optical spectroscopy, NMR, mass
spectrometry, X-ray diffraction/scattering, chromatography quantification, and
evidence-integrated structure elucidation. They compose the existing EDA,
matchms, pyOpenMS, and pymatgen tools while enforcing acquisition provenance,
artifact checks, calibration, identification confidence, alternatives, and
uncertainty. [`docs/ANALYTICAL_SOURCES.md`](../docs/ANALYTICAL_SOURCES.md)
records official standards and the capability-overlap audit.

By access method:

- **Built-in MCP tools** — 15 public sources wire to this plugin's read-only MCP
  (`science_search_*`): PubMed, arXiv, UniProt, PDB, ChEMBL, PubChem, Europe PMC,
  OpenAlex, ClinicalTrials.gov, InterPro, QuickGO, OLS, Reactome, STRING, and
  AlphaFold DB.
- **Agentic life-science research** — 19 additional public APIs plus a local
  planner support entity normalization, PheWAS replication, locus-to-gene,
  expression/cell context, omics dataset discovery, pharmacology, cancer
  genomics, and conflict reconciliation. See
  [`docs/LIFE_SCIENCE_RESEARCH_SOURCES.md`](../docs/LIFE_SCIENCE_RESEARCH_SOURCES.md).
- **Public REST/GraphQL APIs** (no key) — structures/chem: `cx-pdb-search`,
  `cx-chembl-search`, `cx-pubchem-search`, `cx-alphafold-structure-analysis`,
  `cx-foldseek-structural-search`; literature: `cx-biorxiv-search`,
  `cx-europepmc-search`, `cx-openalex-search`; genomics/variants:
  `cx-clinvar-search`, `cx-dbsnp-search`, `cx-ensembl-search`, `cx-gnomad-search`,
  `cx-gtex-search`, `cx-ucsc-conservation`; regulatory/TF: `cx-encode-ccres-search`,
  `cx-jaspar-search`, `cx-unibind-search`; proteins/ontologies/pathways:
  `cx-interpro-search`, `cx-hpa-search`, `cx-quickgo-search`, `cx-reactome-search`,
  `cx-string-ppi-search`, `cx-ols-search`, `cx-protein-msa`,
  `cx-protein-similarity-search`, `cx-ncbi-sequence-fetch`; drugs/targets/clinical:
  `cx-openfda-search`, `cx-opentargets-search`, `cx-clinical-trials-search`;
  other: `cx-predicting-the-past`.
- **Local tool / credentialed** — `cx-pymol-visualize` (local PyMOL);
  `cx-alphagenome-variant-analysis` is the only inactive one (needs an API key).

Content is adapted from
[google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
(Apache-2.0 + CC-BY-4.0); attribution and upstream terms are noted in each
`SKILL.md`.

To add another: create `authored-skills/<name>/SKILL.md` (frontmatter `name`,
`description`, `license`), add the superseded upstream folder to the relevant
source's `exclude`, then run `./scripts/check.sh fast` (regenerates inventory and
wrappers, then validates).
