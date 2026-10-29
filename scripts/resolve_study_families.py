#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.literature_v2 import resolve_study_families  # noqa: E402

FAMILY_EPILOG = """\
records JSON: a list of study objects, or an object whose studies[] is used.
  study_id            required, non-empty string; must be unique across records
  relationships       optional list of {type, target_study_id}; type is one of
                      preprint_of, published_as, corrected_by, retracted_by,
                      secondary_analysis_of, protocol_for, registry_for;
                      target_study_id must be a study_id in the same input
  publication_state   optional; corrected-peer-reviewed, peer-reviewed,
                      accepted-manuscript, preprint, conference-abstract or registry
                      (absent: ranked as registry; unlisted values rank last)
                      and used to choose canonical_study_id
  persistent_ids      optional list; persistent_id, doi, pmid, pmcid, arxiv and nct
                      are also read; records sharing any identifier join one family
Output keys: schema_version 1 and families[] (family_id, canonical_study_id,
study_ids, persistent_ids, publication_states).
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Group study records into families linked by publication relationships.",
        epilog=FAMILY_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("records", type=Path, help="study records JSON (format below)")
    parser.add_argument("--output", type=Path, help="write the family report JSON to this path instead of stdout")
    args = parser.parse_args()
    try:
        payload = json.loads(args.records.read_text())
        records = payload.get("studies", payload) if isinstance(payload, dict) else payload
        report = {"schema_version": 1, "families": resolve_study_families(records)}
        text = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if args.output: args.output.write_text(text, encoding="utf-8")
        else: print(text, end="")
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0
if __name__ == "__main__": raise SystemExit(main())
