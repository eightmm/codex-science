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

The `cx` tier (37 skills) covers **every DeepMind science skill** (35 skills);
only the three infrastructure entries (`credentials`, `uv`,
`workflow_skill_creator`) remain as `gdm` pointers. Each superseded upstream
folder is listed in the `gdm` source's `exclude`, so each capability appears
once.

Two of the 37 are original **execution** skills (no upstream): `cx-compute-environment`
builds an isolated `uv` environment and runs code; `cx-boltz-structure-prediction`
installs and runs the Boltz structure-prediction model. Both use an "ask once,
then run to completion" gate for install/download/compute.

By access method:

- **Built-in MCP tools** — `cx-arxiv-search`, `cx-pubmed-search`,
  `cx-uniprot-search` wire to this plugin's read-only MCP (`science_search_*`).
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
