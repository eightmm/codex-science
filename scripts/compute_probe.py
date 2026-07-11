#!/usr/bin/env python3
"""Report non-sensitive local scientific compute capabilities as JSON."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TOOL_COMMANDS = {
    "python": [sys.executable, "--version"],
    "uv": ["uv", "--version"],
    "R": ["R", "--version"],
    "julia": ["julia", "--version"],
    "jupyter": ["jupyter", "--version"],
    "docker": ["docker", "--version"],
    "podman": ["podman", "--version"],
    "nvidia-smi": ["nvidia-smi", "--version"],
    "rocm-smi": ["rocm-smi", "--version"],
    "ssh": ["ssh", "-V"],
    "rsync": ["rsync", "--version"],
    "sbatch": ["sbatch", "--version"],
    "squeue": ["squeue", "--version"],
    "sacct": ["sacct", "--version"],
}


def _memory_bytes() -> int | None:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024
    except (FileNotFoundError, OSError, ValueError, IndexError):
        pass
    return None


def _tool_report(command: list[str]) -> dict[str, Any]:
    executable = command[0]
    resolved = executable if Path(executable).is_file() else shutil.which(executable)
    if resolved is None:
        return {"available": False, "version": None}
    try:
        result = subprocess.run(
            [resolved, *command[1:]],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        text = (result.stdout or result.stderr).strip().splitlines()
        version = text[0][:300] if text else None
    except (OSError, subprocess.TimeoutExpired):
        version = None
    return {"available": True, "version": version}


def build_report(cwd: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "resources": {
            "cpu_count": os.cpu_count(),
            "memory_bytes": _memory_bytes(),
            "disk_free_bytes": shutil.disk_usage(cwd).free,
        },
        "tools": {name: _tool_report(command) for name, command in TOOL_COMMANDS.items()},
    }


def _write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.chmod(0o600)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = json.dumps(build_report(Path.cwd()), indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        _write_private(args.output, content)
    sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
