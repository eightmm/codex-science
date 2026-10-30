#!/usr/bin/env python3
"""Run public-source probes and emit structured operational drift state."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.cli_io import preflight_output_paths  # noqa: E402
from public_smoke import CHECKS  # type: ignore  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {"schema_version": 1, "sources": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("state must be an object")
    sources = payload.get("sources", {})
    if not isinstance(sources, dict):
        raise ValueError("state sources must be an object")
    for name, source in sources.items():
        if not isinstance(source, dict):
            raise ValueError(f"state source {name!r} must be an object")
        failures = source.get("consecutive_failures", 0)
        if isinstance(failures, bool) or not isinstance(failures, int) or failures < 0:
            raise ValueError(f"state source {name!r} consecutive_failures must be a non-negative integer")
    return payload


def _operational_status(base: str, previous_failures: int) -> tuple[str, int]:
    if base == "healthy":
        return "healthy", 0
    if base == "environment-blocked":
        return base, previous_failures
    failures = previous_failures + 1
    if base == "semantic-drift":
        return base, failures
    if failures >= 3:
        return "unavailable", failures
    if failures == 2:
        return "degraded", failures
    return "transient-failure", failures


def probe(name: str, connector: Any, query: str, *, previous_failures: int) -> dict[str, Any]:
    started = time.monotonic()
    base = "healthy"
    detail = ""
    record_id = None
    try:
        try:
            results = connector.search(query, limit=1)
        except TimeoutError:
            results = connector.search(query, limit=1)
        if results:
            record_id = str(results[0].get("id", ""))
            detail = f"record={record_id}"
        else:
            base = "semantic-drift"
            detail = "query returned no normalized records"
    except TimeoutError:
        base = "transient-failure"
        detail = "timeout after two attempts"
    except urllib.error.HTTPError as error:
        if error.code == 403 and name == "reactome":
            base = "environment-blocked"
            detail = "HTTP 403 in hosted runner environment"
        elif error.code >= 500:
            base = "transient-failure"
            detail = f"HTTP {error.code}"
        else:
            base = "semantic-drift"
            detail = f"unexpected HTTP {error.code}"
    except (KeyError, TypeError, ValueError) as error:
        base = "semantic-drift"
        detail = f"normalization/schema error: {error}"
    except OSError as error:
        base = "transient-failure"
        detail = f"network error: {error}"
    status, consecutive = _operational_status(base, previous_failures)
    return {
        "source": name,
        "query": query,
        "status": status,
        "base_status": base,
        "detail": detail,
        "record_id": record_id,
        "consecutive_failures": consecutive,
        "duration_seconds": round(time.monotonic() - started, 3),
        "checked_at": _now(),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Codex Science public-source drift",
        "",
        f"Checked at: `{report['checked_at']}`",
        "",
        "| Source | Status | Consecutive failures | Detail |",
        "| --- | --- | ---: | --- |",
    ]
    for item in report["sources"]:
        detail = str(item["detail"]).replace("|", "\\|")
        lines.append(f"| {item['source']} | {item['status']} | {item['consecutive_failures']} | {detail} |")
    lines.extend(["", f"Overall: **{report['status']}**", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-in", type=Path)
    parser.add_argument("--state-out", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path, required=True)
    args = parser.parse_args()
    summary = Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None
    try:
        outputs = (args.state_out, args.output_json, args.output_md)
        preflight_output_paths(*outputs, summary)
        if summary is not None and not summary.parent.is_dir():
            raise ValueError(f"output parent is not a directory: {summary.parent}")
        previous = _load_state(args.state_in).get("sources", {})
        for path in outputs:
            path.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    records = [
        probe(name, connector, query, previous_failures=previous.get(name, {}).get("consecutive_failures", 0))
        for name, connector, query in CHECKS
    ]
    blocking = [item for item in records if item["status"] in {"semantic-drift", "degraded", "unavailable"}]
    report = {
        "schema_version": 1,
        "checked_at": _now(),
        "status": "findings" if blocking else "healthy",
        "sources": records,
        "summary": {status: sum(item["status"] == status for item in records) for status in sorted({item["status"] for item in records})},
    }
    state = {"schema_version": 1, "updated_at": report["checked_at"], "sources": {item["source"]: {"status": item["status"], "consecutive_failures": item["consecutive_failures"], "checked_at": item["checked_at"]} for item in records}}
    try:
        args.state_out.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        args.output_md.write_text(render_markdown(report), encoding="utf-8")
        if summary is not None:
            with summary.open("a", encoding="utf-8") as handle:
                handle.write(render_markdown(report))
    except (OSError, RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 1 if blocking else 0


if __name__ == "__main__":
    raise SystemExit(main())
