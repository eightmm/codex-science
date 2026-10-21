#!/usr/bin/env python3
"""Print a read-only completion report for checkpoint artifacts."""
import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.completion_report import report_completion, render_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts_root", type=Path)
    parser.add_argument("--now")
    parser.add_argument("--stale-after-hours", type=float, default=24)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    try:
        now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
        if not math.isfinite(args.stale_after_hours) or args.stale_after_hours <= 0:
            raise ValueError("stale-after-hours must be finite and positive")
        if not args.artifacts_root.exists():
            raise ValueError("artifacts root does not exist")
        if not args.artifacts_root.is_dir():
            raise ValueError("artifacts root is not a directory")
        report = report_completion(args.artifacts_root, now=now, stale_after=timedelta(hours=args.stale_after_hours))
    except (OSError, ValueError, OverflowError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    output = json.dumps(report, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(report)
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
