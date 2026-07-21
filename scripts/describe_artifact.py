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
    validate_descriptor,
    write_descriptor,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path, help="Existing descriptor to validate against path")
    parser.add_argument("--chunk-size", type=int)
    parser.add_argument("--media-type")
    parser.add_argument("--store", type=Path, help="Add a file to a content-addressed store")
    args = parser.parse_args()
    target = args.path.resolve()
    if args.verify:
        payload = json.loads(args.verify.read_text(encoding="utf-8"))
        descriptor = validate_descriptor(payload, target)
    elif target.is_dir():
        descriptor = describe_directory(target, media_type=args.media_type)
    else:
        descriptor = describe_file(target, media_type=args.media_type, chunk_size=args.chunk_size)
    if args.output:
        write_descriptor(args.output.resolve(), descriptor)
    else:
        print(json.dumps(descriptor.to_dict(), indent=2, sort_keys=True))
    if args.store:
        if not target.is_file():
            raise SystemExit("--store currently accepts files only")
        digest, stored = ContentAddressedStore(args.store.resolve()).add_file(target)
        print(json.dumps({"sha256": digest, "stored_path": str(stored)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
