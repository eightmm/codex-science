#!/usr/bin/env bash
# Resolve the persistent interpreter selected by the installer, then execute it.
set -euo pipefail

runtime_file="${CODEX_SCIENCE_RUNTIME_FILE:-$HOME/.codex-science-python}"

compatible() {
  [ -x "$1" ] \
    && "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' \
      >/dev/null 2>&1
}

python="${CODEX_SCIENCE_PYTHON:-}"
if [ -n "$python" ] && ! compatible "$python"; then
  printf 'error: CODEX_SCIENCE_PYTHON must point to Python 3.11+\n' >&2
  exit 1
fi

if [ -z "$python" ] && [ -f "$runtime_file" ] && [ ! -L "$runtime_file" ]; then
  IFS= read -r recorded < "$runtime_file" || recorded=""
  case "$recorded" in
    /*)
      if compatible "$recorded"; then python="$recorded"; fi
      ;;
  esac
fi

if [ -z "$python" ] && command -v python3 >/dev/null 2>&1; then
  system_python="$(command -v python3)"
  if compatible "$system_python"; then python="$system_python"; fi
fi

if [ -z "$python" ]; then
  printf '%s\n' \
    'error: Codex Science requires Python 3.11+; rerun the installer with uv available' >&2
  exit 1
fi

exec "$python" "$@"
