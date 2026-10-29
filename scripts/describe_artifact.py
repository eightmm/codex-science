#!/usr/bin/env python3
"""Create or verify streaming/Merkle descriptors for large scientific artifacts."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.artifact_store import (  # noqa: E402
    ContentAddressedStore,
    describe_directory,
    describe_file,
    stream_sha256,
    validate_descriptor,
    write_descriptor,
)
from codex_science.cli_io import preflight_output_paths, resolve_input_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="file or directory to describe")
    parser.add_argument("--output", type=Path, help="output path for the descriptor JSON; without it the descriptor is printed to stdout")
    parser.add_argument("--verify", type=Path, help="descriptor JSON (schema_version 1) to check against local bytes, including an external reference's digest and size; missing paths are refused; the validated descriptor is then written or printed")
    parser.add_argument("--chunk-size", type=int, help="file only: chunk size in bytes (positive); omit for one whole-file hash (artifact_type file), set for per-chunk hashes (chunked-file); ignored for directories")
    parser.add_argument("--media-type", help="media type recorded in the descriptor (default: none)")
    parser.add_argument("--store", type=Path, help="content-addressed store directory; adds the file (files only) and prints its sha256 and stored_path")
    args = parser.parse_args()
    try:
        return describe(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def describe(args: argparse.Namespace) -> int:
    target = resolve_input_path(args.path)
    inputs = [target]
    if args.verify:
        inputs.append(args.verify)
    protected = [target] if target.is_dir() else []
    store = None
    if args.store:
        if not target.is_file():
            raise ValueError("--store currently accepts files only")
        store = ContentAddressedStore(resolve_input_path(args.store))
        digest, _ = stream_sha256(target)
        stored = store.object_path(digest)
        preflight_output_paths(args.store / stored.relative_to(store.root))
        if stored.is_file() and not store.verify(digest):
            raise ValueError("content-addressed store corruption")
        inputs.append(stored)
        protected.append(store.objects)
    preflight_output_paths(args.output, inputs=inputs, protected_dirs=protected)
    if args.verify:
        payload = json.loads(args.verify.read_text(encoding="utf-8"))
        descriptor = validate_descriptor(payload, target)
    elif target.is_dir():
        descriptor = describe_directory(target, media_type=args.media_type)
    else:
        descriptor = describe_file(target, media_type=args.media_type, chunk_size=args.chunk_size)
    if args.output:
        write_descriptor(args.output.resolve(), descriptor)
    stored_record = None
    if store is not None:
        digest, stored = store.add_file(target)
        stored_record = {"sha256": digest, "stored_path": str(stored)}
    if not args.output:
        print(json.dumps(descriptor.to_dict(), indent=2, sort_keys=True))
    if stored_record is not None:
        print(json.dumps(stored_record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
