---
name: alphagenome-variant-analysis
description: Analyze how a single non-coding genetic variant affects gene expression, chromatin accessibility, histone marks, transcription factors, and splicing using the AlphaGenome API. Use when the user gives a variant in chr:pos:ref/alt form and asks about regulatory or splicing effects, tissue-specific impact, or pathogenicity of a non-coding change. Requires an AlphaGenome API key.
license: Apache-2.0
---

# AlphaGenome Single-Variant Analysis (Codex-native)

Codex-native adaptation of Google DeepMind's `alphagenome-single-variant-analysis`
skill. It keeps the upstream workflow and interpretation rules but maps execution
onto Codex tools instead of a bundled script harness.

> Attribution: adapted from
> [google-deepmind/science-skills](https://github.com/google-deepmind/science-skills)
> (Apache-2.0 + CC-BY-4.0). Model terms: https://deepmind.google.com/science/alphagenome/

## Gates (ask before proceeding)

- **Credential**: this workflow calls the AlphaGenome API and needs
  `ALPHAGENOME_API_KEY`. Do not read, print, or hardcode the key. Confirm the
  user has it exported (e.g. in `~/.env`) before running anything. If absent,
  stop and ask them to register at the model terms URL above.
- **Terms notice**: on first use in a workspace, tell the user to review the
  AlphaGenome terms, and record that you did so in the run's provenance.
- **Package install / network**: the API client (`alphagenome`, `pandas`,
  `numpy`) is installed on demand. Ask before installing, and run all Python
  through `uv run` — never bare `python3`, never `pip install` into the system
  environment.

## Workflow

1. **Parse the variant.** Accept `chr:pos:ref/alt` (or `ref>alt`). Split into
   chrom, pos (int), ref, alt. Reject malformed input.
2. **Set up an output folder** for plots, the JSON of scores, and `report.md`.
3. **Broad discovery scan.** Score the variant across the recommended
   *differential* scorers to find unexpected tissue effects, then rank by
   absolute effect. Run as a `uv run` script:

   ```python
   import os, dotenv, pandas as pd
   from alphagenome.models import dna_client, variant_scorers
   from alphagenome.data import genome

   dotenv.load_dotenv(os.path.expanduser("~/.env"))
   model = dna_client.create(api_key=os.environ["ALPHAGENOME_API_KEY"],
                             address="dns:///gdmscience.googleapis.com:443")

   chrom, pos_s, ref_alt = "chr2:1234:A>C".replace("/", ">").split(":")
   ref, alt = ref_alt.split(">"); pos = int(pos_s)
   L = 2**20
   interval = genome.Interval(chrom, pos - L // 2, pos + L // 2)
   variant = genome.Variant(chrom, pos, ref, alt)
   scorers = [variant_scorers.RECOMMENDED_VARIANT_SCORERS[m]
              for m in variant_scorers.RECOMMENDED_VARIANT_SCORERS
              if all(t not in m for t in ("ACTIVE", "CAGE", "PROCAP"))]
   dfs = [variant_scorers.tidy_scores([a], match_gene_strand=True)
          for a in model.score_variant(interval=interval, variant=variant,
                                        variant_scorers=scorers)]
   df = pd.concat([d for d in dfs if d is not None])
   top = df[df["quantile_score"].abs() > 0.995].sort_values("raw_score", key=abs, ascending=False)
   print(top[["biosample_name", "gene_name", "output_type", "quantile_score", "raw_score"]])
   ```

4. **Focus on disease-relevant tissues** by keyword-filtering `biosample_name`
   when the user gives a phenotype/tissue context.
5. **Interpret carefully** (this is where errors happen):
   - `tidy_scores` uses `gene_name` (not `gene_symbol`) and `output_type` (not
     `modality`); inspect `df.columns` before filtering.
   - Effect direction and magnitude both matter; a high quantile score is a
     *relative* signal, not proof of pathogenicity.
   - Treat near-boundary or single-tissue hits as weak evidence. Report negative
     results honestly.
6. **Write `report.md`** with the variant, the top-hits table, per-tissue
   interpretation, explicit caveats, and note that AlphaGenome was used.
7. **Provenance & review**: record inputs, API endpoint, and outputs with
   `$science-provenance`, then check claims with `$science-review` before
   presenting.

## Boundaries

- Predictions are computational hypotheses, not clinical or diagnostic
  conclusions. Do not assert pathogenicity, disease causation, or treatment
  implications from these scores alone.
- Do not substitute external gene/annotation APIs for the model's own outputs
  when reproducing the upstream method.
- Preserve failures, uncertainty, and the model's known limitations (e.g. weak
  performance on some ncRNA structures).
