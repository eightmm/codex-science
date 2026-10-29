"""Small bounded JSON helpers shared by scientific command-line contracts."""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

DEFAULT_MAX_JSON_BYTES = 64 * 1024 * 1024


def load_json_object(path: Path, *, max_bytes: int = DEFAULT_MAX_JSON_BYTES) -> dict[str, Any]:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise ValueError(f"input JSON file is missing: {path}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"input JSON exceeds {max_bytes} bytes: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"input JSON must be an object: {path}")
    return payload


def preflight_output_paths(*paths: Path | None) -> None:
    """Reject predictable destination conflicts before writing any output."""
    checked: list[tuple[Path, Path]] = []
    for path in paths:
        if path is None:
            continue
        if ".." in path.parts:
            raise ValueError(f"invalid output path: parent component is not allowed: {path}")
        for entry in (*reversed(path.parents), path):
            try:
                mode = os.lstat(entry).st_mode
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(mode):
                try:
                    mode = os.stat(entry).st_mode
                except OSError as error:
                    raise ValueError(f"invalid output path: {entry}: {error}") from error
            if entry == path:
                if stat.S_ISDIR(mode):
                    raise ValueError(f"output destination is a directory: {path}")
            elif not stat.S_ISDIR(mode):
                raise ValueError(f"output ancestor is not a directory: {entry}")
        try:
            resolved = path.resolve()
        except RuntimeError as error:
            raise ValueError(f"invalid output path: {path}: {error}") from error
        for previous, previous_resolved in checked:
            if resolved == previous_resolved or (
                path.exists() and previous.exists() and os.path.samefile(path, previous)
            ):
                raise ValueError(f"output paths refer to the same file: {previous} and {path}")
            if resolved in previous_resolved.parents or previous_resolved in resolved.parents:
                raise ValueError(f"output paths overlap: {previous} and {path}")
        checked.append((path, resolved))


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    write_text_atomic(path, rendered)


def write_text_atomic(path: Path, rendered: str) -> None:
    """Write UTF-8 text through a same-directory atomic replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
