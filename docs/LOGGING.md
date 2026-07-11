# Logging

Each research run uses `artifacts/<run-id>/manifest.json`. Record the approved plan, inputs, code, commands, exit codes, environment, output hashes, claims, evidence, and review.

After validation, `scripts/render_artifact_index.py` generates a private local
`index.md` and optional offline `index.html`. These are reproducible navigation
views, not evidence records. Primary raster figures are displayed in Codex; all
files are linked by absolute local path in the final response.

Never log secrets, tokens, credential-bearing URLs, or sensitive raw data. Failed and inconclusive runs remain in the record.
