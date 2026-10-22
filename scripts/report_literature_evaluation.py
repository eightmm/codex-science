#!/usr/bin/env python3
"""Grade receipts from a literature evaluation run directory."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from codex_science.literature_evaluation_report import grade_run, render_markdown, summarize  # noqa: E402
from codex_science.literature_evaluation_runner import load_task_set  # noqa: E402


@contextlib.contextmanager
def _locked_ledger(path: Path):
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise ValueError("append ledger must be a regular file")
    flags = os.O_CREAT | os.O_APPEND | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("append ledger must be a regular file")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield descriptor
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _ledger_lines(descriptor: int) -> list[str]:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8").splitlines()


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]
    os.fsync(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--append-ledger", type=Path)
    args = parser.parse_args()
    try:
        task_set = load_task_set(args.tasks)
        task_by_id = {row["id"]: row for row in task_set["tasks"]}
        plans = sorted(args.runs.glob("plan*.json"))
        execute_plans = []
        planned_ids = set()
        for plan_path in plans:
            try:
                if not stat.S_ISREG(plan_path.lstat().st_mode):
                    raise ValueError("plan is not a regular file")
                plan = json.loads(plan_path.read_text(encoding="utf-8"))
                if not isinstance(plan, dict) or type(plan.get("execute")) is not bool:
                    raise ValueError("plan execute must be a boolean")
                if plan["execute"] is False:
                    continue
                plan_tasks = plan.get("tasks")
                if not isinstance(plan_tasks, list):
                    raise ValueError("plan tasks must be a list")
                for entry in plan_tasks:
                    if not isinstance(entry, dict) or not isinstance(entry.get("task_id"), str):
                        raise ValueError("plan task entries require task_id")
                    planned_ids.add(entry["task_id"])
                execute_plans.append(plan_path)
            except (OSError, ValueError, json.JSONDecodeError, AttributeError, TypeError, KeyError) as error:
                print(f"invalid plan {plan_path}: {error}", file=sys.stderr)
                return 2
        receipt_paths = sorted(args.runs.glob("*/receipt.json"))
        seen_task_paths = {}
        parsed_receipts = []
        executed_receipts = 0
        for receipt_path in receipt_paths:
            try:
                if not stat.S_ISDIR(receipt_path.parent.lstat().st_mode):
                    raise ValueError(f"run directory is not a real directory: {receipt_path.parent}")
                if not stat.S_ISREG(receipt_path.lstat().st_mode):
                    raise ValueError(f"receipt is not a regular file: {receipt_path}")
                receipt_bytes = receipt_path.read_bytes()
                receipt = json.loads(receipt_bytes)
                if not isinstance(receipt, dict):
                    raise TypeError("receipt root must be an object")
                task_id = receipt.get("task_id")
                if not isinstance(task_id, str):
                    raise TypeError("receipt task_id must be a string")
                previous_path = seen_task_paths.get(task_id)
                if previous_path is not None:
                    print(f"duplicate task_id {task_id!r} in receipts {previous_path} and {receipt_path}", file=sys.stderr)
                    return 2
                seen_task_paths[task_id] = receipt_path
                receipt_digest = hashlib.sha256(receipt_bytes).hexdigest()
                receipt["_report_receipt_sha256"] = receipt_digest
                executed_receipts += receipt.get("executed") is True
                parsed_receipts.append((receipt_path, receipt, receipt_digest))
            except (OSError, ValueError, json.JSONDecodeError, AttributeError, TypeError, KeyError) as error:
                print(f"invalid receipt {receipt_path}: {error}", file=sys.stderr)
                return 2
        graded = []
        for receipt_path, receipt, receipt_digest in parsed_receipts:
            task_id = receipt["task_id"]
            try:
                if receipt_path.parent.name != task_id:
                    raise ValueError(f"receipt directory {receipt_path.parent.name!r} does not match task_id {task_id!r}")
                if receipt.get("set_digest") != task_set["set_digest"]:
                    print(f"receipt {receipt_path}: set_digest does not match the frozen task set", file=sys.stderr)
                    return 2
                if task_id not in task_by_id:
                    graded.append({"schema": "literature-eval-graded-run-v1", "task_id": task_id,
                                   "task_digest": None, "set_digest": receipt.get("set_digest"),
                                   "outcome": "rejected", "stop_reason": "unknown_task", "errors": ["unknown_task"],
                                   "criteria": [], "citations": {"status": "unavailable"},
                                   "executed": receipt.get("executed") is True,
                                   "receipt_sha256": receipt_digest})
                    continue
                task = dict(task_by_id[task_id], set_digest=task_set["set_digest"])
                graded_run = grade_run(receipt, task, receipt_path.parent)
                graded_run["receipt_sha256"] = receipt_digest
                graded.append(graded_run)
            except (OSError, ValueError, json.JSONDecodeError, AttributeError, TypeError, KeyError) as error:
                print(f"invalid receipt {receipt_path}: {error}", file=sys.stderr)
                return 2
        missing = sorted(planned_ids - set(seen_task_paths))
        if missing:
            print(f"missing receipts for planned task ids: {', '.join(missing)}", file=sys.stderr)
            return 2
        if not receipt_paths:
            print(f"refusing report: no receipts found under {args.runs}", file=sys.stderr)
            return 2
        if not execute_plans and not executed_receipts:
            print("refusing report: no execute plan or executed receipts found", file=sys.stderr)
            return 2
        report = summarize(graded)
        report["runs"] = graded
        if args.append_ledger:
            rejected = [row for row in graded if row.get("outcome") == "rejected"]
            if rejected:
                reasons = ", ".join(f"{row.get('task_id')}:{row.get('stop_reason')}" for row in rejected)
                print(f"refusing ledger append: rejected receipt(s): {reasons}", file=sys.stderr)
                return 2
            if any(row.get("executed") is not True for row in graded):
                print("refusing ledger append: every receipt must have executed: true", file=sys.stderr)
                return 2
            with _locked_ledger(args.append_ledger) as ledger_fd:
                known_hashes = set()
                for line_number, raw in enumerate(_ledger_lines(ledger_fd), 1):
                    try:
                        entry = json.loads(raw)
                    except json.JSONDecodeError as error:
                        raise ValueError(f"invalid ledger JSON on line {line_number}") from error
                    if isinstance(entry, dict) and isinstance(entry.get("receipt_sha256"), str):
                        known_hashes.add(entry["receipt_sha256"])
                duplicates = []
                new_rows = []
                for row in graded:
                    digest = row.get("receipt_sha256")
                    if digest in known_hashes:
                        duplicates.append(row)
                    else:
                        new_rows.append(row)
                        if isinstance(digest, str):
                            known_hashes.add(digest)
                report["ledger_duplicates"] = [row.get("task_id") for row in duplicates]
                if duplicates:
                    print("skipped duplicate receipt(s): " + ", ".join(str(row.get("task_id")) for row in duplicates), file=sys.stderr)
                if not new_rows:
                    print("all receipts already present in ledger; nothing appended", file=sys.stderr)
                    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
                    return 0
                ledger_summary = summarize(new_rows)
                lines = []
                for row in new_rows:
                    lines.append({key: row.get(key) for key in ("schema", "set_digest", "task_id", "task_digest", "codex_version", "runtime_identity", "loaded_runtime", "branch_runtime_version", "outcome", "receipt_sha256")})
                lines.append({"schema": ledger_summary["schema"], "set_digest": ledger_summary["set_digest"],
                              "loaded_runtime": ledger_summary["loaded_runtime"],
                              "branch_runtime_version": ledger_summary["branch_runtime_version"],
                              "summary": ledger_summary["overall"]})
                payload = "".join(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n" for line in lines)
                _write_all(ledger_fd, payload.encode("utf-8"))
        print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"literature evaluation report failed: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
