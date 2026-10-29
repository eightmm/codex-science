#!/usr/bin/env python3
"""Build studies.json from screening decisions and declarative extraction data."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.evidence import EVIDENCE_TYPES  # noqa: E402
from codex_science.study_table import build_study_table  # noqa: E402

EPILOG = f"""\
extraction file (JSON):
  {{"schema": "study-extraction-v1", "studies": [...], "not_extracted": [...]}}
Every record with screening decision "include" appears exactly once, in
studies or in not_extracted. Unknown or non-included record IDs are errors.
not_extracted[]: {{"record_id", "reason"}}; reason must be non-empty.
studies[]: record_id (required); evidence_type (required, one of:
  {", ".join(sorted(EVIDENCE_TYPES))});
  supports_claim_ids, contradicts_claim_ids (string lists); optional study_id
  (default S + alphanumerics of record_id), cohort_id, fields, excerpts.
  fields: object of extra extraction fields merged into the study row; builder-
  owned keys (study_id, title, identifiers, supports_claim_ids,
  support_excerpts, ...) are rejected.
excerpts[]: claim_id (must be in this study's supports/contradicts list);
  text (20-2000 characters, verbatim; must occur in the source after
  whitespace normalisation); optional source_artifact (run-relative path,
  default: the screening row's evidence_artifact); optional locator (object).
  The builder computes source_sha256.
Title, identifiers, persistent IDs, query IDs and publication date come from
screening.json and candidates.json; do not supply them.
Screening title, identifiers and query_ids must match the candidate record.
Every included record's supplied screening evidence must retain its hash,
including not_extracted records. Integer locator lines follow splitlines()
boundaries, including CR and CRLF. Output cannot replace consumed inputs or
evidence files, even when there are no excerpts.
On any problem nothing is written and all problems are listed in one error.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", type=Path, required=True, help="run directory containing screening.json and candidates.json")
    parser.add_argument("--extraction", type=Path, required=True, help="extraction JSON file (format below)")
    parser.add_argument("--output", default="studies.json", help="output file name (default: studies.json)")
    args = parser.parse_args(argv)
    try:
        result = build_study_table(args.run_dir, args.extraction, args.output)
    except (ValueError, OSError, RuntimeError, UnicodeError, TypeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
