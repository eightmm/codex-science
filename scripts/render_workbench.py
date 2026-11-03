#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.run_packaging import digest_mismatch_hint  # noqa: E402
from codex_science.workbench import write_workbench  # noqa: E402

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, help="HTML destination (must not overwrite run inputs or registered directory trees, or leave the run directory through a link inside it)")
    args = parser.parse_args()
    output = args.output or args.manifest.parent / "workbench.html"
    try:
        skipped: list[str] = []
        write_workbench(args.manifest.resolve(), output, skipped)
        if skipped:
            print("warning: ignoring resolution events for unregistered annotation IDs: " + ", ".join(skipped), file=sys.stderr)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}{digest_mismatch_hint(error, args.manifest.resolve().parent)}", file=sys.stderr)
        return 1
    except RecursionError:
        print("error: workbench manifest exceeds the supported nesting depth", file=sys.stderr)
        return 1
    print(output.resolve())
    return 0
if __name__ == "__main__": raise SystemExit(main())
