#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

git submodule update --init --recursive
uv sync
uv run python scripts/audit_skills.py
uv run python scripts/generate_wrappers.py
bash scripts/doctor.sh
