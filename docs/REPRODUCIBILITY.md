# Reproducibility

The upstream catalog is pinned by Git submodule commit and `catalog/source.json`. Python tooling is pinned by `uv.lock`. The generated inventory contains no timestamp, so identical source and policy produce identical bytes.

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
