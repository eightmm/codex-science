"""Shared malformed-JSON and no-write assertions for loader CLI tests."""

import json
import os
import subprocess
import sys
from pathlib import Path


def malformed_json():
    values = [[], "x", 1, None, True, float("nan"), float("inf"), {},
              {"schema_version": 1},
              {"schema_version": 1, "id": "\ud800", "name": "\ud800", "question": "\ud800"}]
    return [b"", b"{", b"\xff", *(json.dumps(value).encode("utf-8") for value in values)]


def nested_values():
    return [None, [], {}, "x", True, 10**400, float("nan"), float("inf"), "\ud800"]


def assert_refused(test, script, arguments, status, output=None):
    before = None
    if output is not None and output.exists():
        before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()} if output.is_dir() else output.read_bytes()
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / script), *map(str, arguments)],
        capture_output=True, text=True,
        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")),
    )
    test.assertEqual(status, result.returncode, result.stderr)
    test.assertEqual("", result.stdout)
    test.assertIn("error: ", result.stderr)
    test.assertNotIn("Traceback", result.stderr)
    if output is not None:
        if before is None:
            test.assertFalse(output.exists())
        elif output.is_dir():
            test.assertEqual(before, {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()})
        else:
            test.assertEqual(before, output.read_bytes())
