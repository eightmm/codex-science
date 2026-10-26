#!/usr/bin/env python3
"""Trace literature identifiers in reports to run-local provenance."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.citation_trace import trace_citations  # noqa: E402
from codex_science.run_packaging import _stage_file  # noqa: E402


def emit(payload: str, output: str | None) -> None:
    if output:
        target = Path(output)
        staged = _stage_file(target, (payload + "\n").encode("utf-8"))
        try:
            os.replace(staged, target)
        finally:
            staged.unlink(missing_ok=True)
    print(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__ + " Reports are scanned for DOI, PMID, PMCID and arXiv identifiers; each is matched, after normalization, "
        "to identifiers in any study-table record (doi, pmid, pmcid, arxiv, persistent_id, persistent_ids, identifiers), "
        "or in the query ledger and lane receipts (also returned_record_ids, included_records). "
        "A cited identifier found nowhere is an orphan.")
    parser.add_argument("--run-dir", required=True, help="run directory containing manifest.json and studies.json")
    parser.add_argument("--report", action="append", default=[],
                        help="report file relative to the run directory; repeatable (default: manifest artifacts of kind report)")
    parser.add_argument("--require-traced", action="store_true",
                        help="exit 1 if no report was examined or any cited identifier is not in the run's records")
    parser.add_argument("--output", help="also write the result JSON atomically to this path; untouched on error (exit 2)")
    args = parser.parse_args()
    try:
        result = trace_citations(args.run_dir, args.report or None)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError, RecursionError) as error:
        print(json.dumps({"schema": "citation-trace-error-v1", "error": {"code": "invalid_input", "message": str(error)}}, sort_keys=True))
        if args.output:
            print(f"note: {args.output} was not written because the run is invalid", file=sys.stderr)
        return 2
    if args.require_traced:
        if result["reports_examined"] == 0:
            result["require_traced_failure"] = "no_report_examined"
        elif result["orphans"]:
            result["require_traced_failure"] = "orphan_citations"
    try:
        emit(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(",", ":")), args.output)
    except OSError as error:
        print(json.dumps({"schema": "citation-trace-error-v1", "error": {"code": "output_write_failed",
                          "message": f"cannot write {args.output}: {error}"}}, sort_keys=True))
        return 2
    return 1 if "require_traced_failure" in result else 0


if __name__ == "__main__":
    raise SystemExit(main())
