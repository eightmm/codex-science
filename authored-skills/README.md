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

| Authored skill | Supersedes (excluded upstream) | Default status |
| --- | --- | --- |
| `cx-alphagenome-variant-analysis` | `gdm/alphagenome_single_variant_analysis` | inactive (needs API key) |
| `cx-alphafold-structure-analysis` | `gdm/alphafold_database_fetch_and_analyze` | active |
| `cx-foldseek-structural-search` | `gdm/foldseek_structural_search` | active |
| `cx-arxiv-search` | `gdm/literature_search_arxiv` | active |
| `cx-pubmed-search` | `gdm/pubmed_database` | active |
| `cx-uniprot-search` | `gdm/uniprot_database` | active |
| `cx-pdb-search` | `gdm/pdb_database` | active |
| `cx-chembl-search` | `gdm/chembl_database` | active |

The `cx-arxiv-search`, `cx-pubmed-search`, and `cx-uniprot-search` skills wire
directly to this plugin's built-in read-only MCP tools (`science_search_arxiv`,
`science_search_pubmed`, `science_search_uniprot`). `cx-pdb-search` and
`cx-chembl-search` use the public RCSB and ChEMBL REST APIs directly (no built-in
MCP tool exists for them).

Content is adapted from
[google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
(Apache-2.0 + CC-BY-4.0); attribution and upstream terms are noted in each
`SKILL.md`.

To add another: create `authored-skills/<name>/SKILL.md` (frontmatter `name`,
`description`, `license`), add the superseded upstream folder to the relevant
source's `exclude`, then run `./scripts/check.sh fast` (regenerates inventory and
wrappers, then validates).
