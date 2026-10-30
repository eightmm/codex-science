"""Small bounded JSON helpers shared by scientific command-line contracts."""
from __future__ import annotations

import errno
import json
import os
import stat
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable, Mapping

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
    except RecursionError as error:
        raise ValueError(f"invalid JSON in {path}: excessive nesting") from error
    if not isinstance(payload, dict):
        raise ValueError(f"input JSON must be an object: {path}")
    return payload


def resolve_input_path(path: Path) -> Path:
    """Resolve an input with component-wise loop refusal on supported runtimes."""
    def check_components(candidate: Path) -> None:
        for entry in (*reversed(candidate.parents), candidate):
            try:
                is_link = entry.is_symlink()
            except OSError:
                continue
            if is_link:
                try:
                    os.stat(entry)
                except OSError as error:
                    if error.errno == errno.ELOOP:
                        raise ValueError(f"invalid protected input path: {entry}: {error}") from error

    check_components(path)
    try:
        resolved = path.resolve()
    except RuntimeError as error:
        raise ValueError(f"invalid protected input path: {path}: {error}") from error
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"invalid protected input path: {path}: {error}") from error
        resolved = Path(os.path.realpath(path))
    # Non-strict resolution can remove missing/.. components and leave a loop
    # unresolved on Python 3.13+, so check the resulting spelling as well.
    check_components(resolved)
    return resolved


def _same_file(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except OSError:
        return False


def preflight_output_paths(
    *paths: Path | None,
    inputs: Iterable[Path] = (),
    protected_dirs: Iterable[Path] = (),
) -> None:
    """Reject destination conflicts, input replacement and protected-tree writes.

    Trees use resolved containment and identities from resolved ancestry, without
    listing descendants or detecting their external hardlinks. Portable keys use
    canonical caseless components after resolving the deepest existing entry.
    This does not reserve paths against concurrent changes or make writes
    transactional.
    """
    def identity(entry: Path) -> tuple[int, int] | None:
        try:
            info = os.stat(entry)
        except OSError:
            return None
        return info.st_dev, info.st_ino

    def component_key(name: str) -> str:
        """Unicode D145 canonical caseless matching, without compatibility folding."""
        return unicodedata.normalize("NFD", unicodedata.normalize("NFD", name).casefold())

    def portable_key(path: Path) -> tuple[str, ...]:
        return tuple(component_key(component) for component in path.parts)

    def resolved_state(ancestor: Path, remaining: tuple[str, ...] = ()):
        prefix = Path(os.path.realpath(ancestor))
        resolved = prefix.joinpath(*remaining)
        ancestor_id = None
        suffix = ()
        existing = []
        # Lexical ancestors above a symlink may belong to a tree it escapes.
        for entry in (prefix, *prefix.parents):
            entry_id = identity(entry)
            if entry_id is not None:
                existing.append(entry_id)
                if ancestor_id is None:
                    ancestor_id = entry_id
                    suffix = portable_key(resolved.relative_to(entry))
        return portable_key(resolved), ancestor_id, suffix, existing

    def is_prefix(parent: tuple[str, ...], child: tuple[str, ...]) -> bool:
        return child[:len(parent)] == parent

    sources = []
    for source in inputs:
        source_key, source_id, source_suffix, _ = resolved_state(resolve_input_path(source))
        sources.append((source, source_key, source_id, source_suffix))
    directories = []
    for directory in protected_dirs:
        directory_resolved = Path(os.path.realpath(resolve_input_path(directory)))
        directories.append((directory, portable_key(directory_resolved), identity(directory_resolved)))
    checked = []
    for path in paths:
        if path is None:
            continue
        if ".." in path.parts:
            raise ValueError(f"invalid output path: parent component is not allowed: {path}")
        for entry in (*reversed(path.parents), path):
            try:
                info = os.lstat(entry)
            except FileNotFoundError:
                continue
            if stat.S_ISLNK(info.st_mode):
                try:
                    info = os.stat(entry)
                except OSError as error:
                    raise ValueError(f"invalid output path: {entry}: {error}") from error
            if entry == path:
                if stat.S_ISDIR(info.st_mode):
                    raise ValueError(f"output destination is a directory: {path}")
            elif not stat.S_ISDIR(info.st_mode):
                raise ValueError(f"output ancestor is not a directory: {entry}")
            ancestor = entry
            remaining = path.relative_to(entry).parts
        portable, ancestor_id, suffix, existing = resolved_state(ancestor, remaining)
        for source, source_key, source_id, source_suffix in sources:
            same_ancestor = source_id is not None and ancestor_id == source_id
            if (portable == source_key or _same_file(path, source)
                    or (same_ancestor and suffix == source_suffix)):
                raise ValueError(f"output path would overwrite input: {source}: {path}")
            if (is_prefix(portable, source_key)
                    or (same_ancestor and is_prefix(suffix, source_suffix))):
                raise ValueError(f"output path is an input ancestor: {source}: {path}")
        for directory, directory_key, directory_id in directories:
            if (is_prefix(directory_key, portable) or is_prefix(portable, directory_key)
                    or (directory_id is not None and directory_id in existing)):
                raise ValueError(f"output path overlaps protected directory: {directory}: {path}")
        for previous, previous_key, previous_id, previous_suffix in checked:
            same_ancestor = ancestor_id is not None and ancestor_id == previous_id
            if (portable == previous_key or _same_file(path, previous)
                    or (same_ancestor and suffix == previous_suffix)):
                raise ValueError(f"output paths refer to the same file: {previous} and {path}")
            if (is_prefix(portable, previous_key) or is_prefix(previous_key, portable)
                    or (same_ancestor and (is_prefix(suffix, previous_suffix)
                                          or is_prefix(previous_suffix, suffix)))):
                raise ValueError(f"output paths overlap: {previous} and {path}")
        checked.append((path, portable, ancestor_id, suffix))


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
