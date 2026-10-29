#!/usr/bin/env python3
"""Optionally resolve citation identifiers against public metadata services."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from codex_science.citation_resolve import (
    EVIDENCE_BOUNDARY, normalize_identifiers, resolve_identifiers, supported_identifiers_from_text,
    _normalized_text, _year_value,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "") + " Text input resolves the first 50 supported identifiers "
        "in sorted order; additional supported identifiers are listed as skipped with reason over_cap.")
    parser.add_argument("--input", help="text file to scan for DOI, PMID or arXiv identifiers; - or omitted reads stdin")
    parser.add_argument("--ids", nargs="*", help="identifiers to resolve instead of scanning text (at most 50); cannot be combined with --input")
    parser.add_argument("--network", action="store_true",
                        help="query public metadata services (default: print the plan only)")
    parser.add_argument("--offline-fixture", type=Path,
                        help="directory of recorded <kind>_<id>.json responses; body is raw XML/JSON text or a JSON object")
    parser.add_argument("--run-dir", type=Path, help="load expected citation metadata from a run's study table")
    args = parser.parse_args(argv)
    try:
        if args.ids is not None and args.input is not None:
            raise ValueError("--ids and --input cannot be used together")
        if args.ids is not None:
            ids = normalize_identifiers(args.ids)
            skipped = []
        else:
            input_path = args.input or "-"
            content = sys.stdin.read() if input_path == "-" else Path(input_path).read_text(encoding="utf-8")
            ids, skipped = supported_identifiers_from_text(content)
        expected = {}
        metadata_conflicts: set[str] = set()
        if args.run_dir:
            run_dir = args.run_dir.resolve()
            manifest_path = run_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                raise ValueError("manifest must be an object")
            artifacts = manifest.get("artifacts", [])
            if not isinstance(artifacts, list):
                raise ValueError("manifest artifacts must be a list")
            table_name = None
            for index, entry in enumerate(artifacts):
                if not isinstance(entry, dict):
                    raise ValueError(f"manifest artifact {index} must be an object")
                kind, path = entry.get("kind"), entry.get("path")
                if not isinstance(kind, str):
                    raise ValueError(f"manifest artifact {index} kind must be a string")
                if not isinstance(path, str) or not path.strip():
                    raise ValueError(f"manifest artifact {index} path must be a non-empty string")
                if kind == "study-table" and table_name is None:
                    table_name = path
            if table_name is None:
                table_name = "studies.json"
            table_path = (run_dir / table_name).resolve()
            if run_dir not in table_path.parents:
                raise ValueError("study table path escapes run directory")
            table = json.loads(table_path.read_text(encoding="utf-8"))
            if not isinstance(table, dict):
                raise ValueError("study table must be an object")
            studies = table.get("studies", [])
            if not isinstance(studies, list):
                raise ValueError("study table studies must be a list")
            for index, study in enumerate(studies):
                if not isinstance(study, dict):
                    raise ValueError(f"study {index} must be an object")
                raw_id = study.get("persistent_id")
                if not isinstance(raw_id, str):
                    continue
                try:
                    identifier = normalize_identifiers([raw_id])[0]
                except (ValueError, TypeError):
                    continue
                authors = study.get("authors") or []
                if isinstance(authors, str):
                    authors = [authors]
                first = authors[0] if authors else None
                if isinstance(first, dict):
                    first = first.get("family") or first.get("name")
                first = study.get("first_author") or first
                if first and not study.get("first_author"):
                    first = (str(first).split() or [None])[-1]
                metadata = {"title": study.get("title"), "year": study.get("year"), "first_author": first}
                previous = expected.setdefault(identifier, {})
                for field, value in metadata.items():
                    if value is None or value == "":
                        continue
                    if field in previous:
                        old = previous[field]
                        normalize = _year_value if field == "year" else _normalized_text
                        if normalize(old) != normalize(value) or (normalize(value) is None and old != value):
                            metadata_conflicts.add(identifier)
                    else:
                        previous[field] = value
        if args.offline_fixture:
            def fetch(url: str, *, timeout: float):
                del timeout
                ambiguous_doi = False
                if "crossref.org/works/" in url:
                    value = urllib.parse.unquote(url.rsplit("/", 1)[-1])
                    suffix = value.split("/", 1)[1]
                    ambiguous_doi = "/" in suffix or "_" in suffix
                    name = "doi_" + value.replace("/", "_")
                elif "esummary.fcgi" in url:
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                    name = "pmid_" + query["id"][0]
                else:
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                    name = "arxiv_" + query["id_list"][0].replace("/", "_")
                fixture = args.offline_fixture / (name + ".json")
                payload = json.loads(fixture.read_text(encoding="utf-8"))
                body = payload.get("body", {})
                if ambiguous_doi:
                    identity_body = json.loads(body) if isinstance(body, str) else body
                    message = identity_body.get("message") if isinstance(identity_body, dict) else None
                    if not isinstance(message, dict) or "DOI" not in message:
                        raise ValueError("ambiguous DOI fixture requires response identity")
                return payload["http_status"], (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
            output = resolve_identifiers(ids, fetch=fetch, expected_metadata=expected)
        elif not args.network:
            output = {"schema": "citation-resolution-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
                      "plan": {"identifiers": ids, "network": False}, "skipped_identifiers": skipped}
        else:
            output = resolve_identifiers(ids, expected_metadata=expected)
        if args.offline_fixture or args.network:
            output["skipped_identifiers"] = skipped
            for item in output["results"]:
                if item["identifier"] in metadata_conflicts:
                    item["metadata_check"] = "mismatch"
            if args.run_dir:
                mismatches = sum(item.get("metadata_check") == "mismatch" for item in output["results"])
                print(f"metadata mismatches: {mismatches}", file=sys.stderr)
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError, OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "citation-resolution-error-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
                          "error": {"code": "invalid_request", "message": str(exc)}}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
