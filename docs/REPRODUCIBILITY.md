# Reproducibility

Each skill source is pinned in `catalog/sources.json` (repository, commit, kind). K-Dense is a pinned Git submodule; DeepMind is a pinned vendored copy with a deterministic `content_sha256` tree digest; `authored-skills/` is in-repo. `doctor.sh` verifies the submodule commit and vendored digest before validating the catalog. Python tooling is pinned by `uv.lock`. The generated inventory contains no timestamp, so identical sources and policy produce identical bytes.

```bash
git submodule update --init --recursive
uv sync
uv run python scripts/audit_skills.py
uv run python scripts/generate_wrappers.py
./scripts/doctor.sh
```

Reproduce the reviewed example with:

```bash
uv run python examples/reviewed-run/analysis.py
uv run python scripts/validate_artifact.py examples/reviewed-run/manifest.json
```
