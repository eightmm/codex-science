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
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--network", action="store_true")
    parser.add_argument("--offline-fixture", type=Path)
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
        if args.offline_fixture:
            def fetch(url: str, *, timeout: float):
                del timeout
                if "crossref.org/works/" in url:
                    name = "doi_" + urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace("/", "_")
                elif "esummary.fcgi" in url:
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                    name = "pmid_" + query["id"][0]
                else:
                    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                    name = "arxiv_" + query["id_list"][0].replace("/", "_")
                fixture = args.offline_fixture / (name + ".json")
                payload = json.loads(fixture.read_text(encoding="utf-8"))
                return payload["http_status"], json.dumps(payload.get("body", {})).encode()
            output = resolve_identifiers(ids, fetch=fetch)
        elif not args.network:
            output = {"schema": "citation-resolution-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
                      "plan": {"identifiers": ids, "network": False}, "skipped_identifiers": skipped}
        else:
            output = resolve_identifiers(ids)
        if args.offline_fixture or args.network:
            output["skipped_identifiers"] = skipped
        print(json.dumps(output, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError, OverflowError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "citation-resolution-error-v1", "evidence_boundary": EVIDENCE_BOUNDARY,
                          "error": {"code": "invalid_request", "message": str(exc)}}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
