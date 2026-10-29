import importlib.util
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class PublicDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.root = Path(__file__).resolve().parents[1]
        scripts = str(cls.root / "scripts")
        sys.path.insert(0, scripts)
        spec = importlib.util.spec_from_file_location("public_drift", cls.root / "scripts" / "public_drift.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load public_drift")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_healthy_and_semantic_drift_are_distinct(self) -> None:
        class Healthy:
            def search(self, query, *, limit):
                return [{"id": "record-1"}]
        class Empty:
            def search(self, query, *, limit):
                return []
        healthy = self.module.probe("source", Healthy(), "query", previous_failures=2)
        empty = self.module.probe("source", Empty(), "query", previous_failures=0)
        self.assertEqual("healthy", healthy["status"])
        self.assertEqual(0, healthy["consecutive_failures"])
        self.assertEqual("semantic-drift", empty["status"])

    def test_malformed_state_is_refused_before_probing_or_writing(self) -> None:
        malformed = [[], None, 0, True, "state"]
        malformed.extend({"sources": value} for value in ([], None, 0, True, "sources"))
        malformed.extend({"sources": {"pubmed": value}} for value in ([], None, 0, True, "source"))
        malformed.extend(
            {"sources": {"pubmed": {}, name: {"consecutive_failures": value}}}
            for name in ("pubmed", "arxiv", "unused-source")
            for value in ("bad", "1", None, 1.5, 0.0, -1, True, False, [], {})
        )
        contents = [b"", b"{", bytes([255])]
        contents.extend(json.dumps(value).encode("utf-8") for value in malformed)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "input"
            outputs = [root / name for name in ("state", "output", "report")]
            for content in contents:
                for existing in (False, True):
                    with self.subTest(content=content, existing=existing):
                        state.write_bytes(content)
                        for path in outputs:
                            if existing:
                                path.write_bytes(b"preserve")
                            else:
                                path.unlink(missing_ok=True)
                        arguments = [str(self.root / "scripts" / "public_drift.py"),
                                     "--state-in", str(state), "--state-out", str(outputs[0]),
                                     "--output-json", str(outputs[1]), "--output-md", str(outputs[2])]
                        with mock.patch.object(sys, "argv", arguments), \
                             mock.patch.object(self.module, "probe", return_value={
                                 "source": "mock-source", "status": "healthy", "consecutive_failures": 0,
                                 "checked_at": "fixed", "detail": "record=1",
                             }) as probe, \
                             contextlib.redirect_stderr(io.StringIO()) as stderr, \
                             contextlib.redirect_stdout(io.StringIO()) as stdout:
                            self.assertEqual(1, self.module.main())
                        probe.assert_not_called()
                        self.assertEqual("", stdout.getvalue())
                        self.assertIn("error: ", stderr.getvalue())
                        result = subprocess.run(
                            [sys.executable, *arguments], cwd=root, capture_output=True, text=True,
                            timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                        )
                        self.assertEqual(1, result.returncode, result.stderr)
                        self.assertEqual("", result.stdout)
                        self.assertIn("error: ", result.stderr)
                        self.assertNotIn("Traceback", result.stderr)
                        self.assertEqual(content, state.read_bytes())
                        for path in outputs:
                            if existing:
                                self.assertEqual(b"preserve", path.read_bytes())
                            else:
                                self.assertFalse(path.exists())
                        self.assertEqual({"input", *([p.name for p in outputs] if existing else [])},
                                         {p.name for p in root.iterdir()})
        self.check_initial_optional_fields_and_writer_output()

    def check_initial_optional_fields_and_writer_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            initial = {"schema_version": 1, "sources": {}}
            self.assertEqual(initial, self.module._load_state(None))
            self.assertEqual(initial, self.module._load_state(state))
            valid = [{}, initial, {"sources": {"pubmed": {}}}]
            valid.extend({"sources": {"pubmed": {"consecutive_failures": count}}}
                         for count in (0, 1, 3, 10**100))
            for payload in valid:
                with self.subTest(payload=payload):
                    state.write_text(json.dumps(payload), encoding="utf-8")
                    self.assertEqual(payload, self.module._load_state(state))

            arguments = ["public_drift.py", "--state-out", str(state),
                         "--output-json", str(root / "report.json"),
                         "--output-md", str(root / "report.md")]
            record = {"source": "pubmed", "query": "query", "status": "healthy",
                      "consecutive_failures": 0, "checked_at": "fixed", "detail": "record=1"}
            with mock.patch.object(sys, "argv", arguments), \
                 mock.patch.object(self.module, "CHECKS", [("pubmed", object(), "query")]), \
                 mock.patch.object(self.module, "probe", return_value=record) as probe, \
                 mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(0, self.module.main())
                self.assertEqual(0, probe.call_args.kwargs["previous_failures"])
                written = self.module._load_state(state)
                self.assertEqual(0, written["sources"]["pubmed"]["consecutive_failures"])
                with mock.patch.object(sys, "argv", [*arguments, "--state-in", str(state)]):
                    self.assertEqual(0, self.module.main())
                self.assertEqual(2, probe.call_count)
                self.assertEqual(0, probe.call_args.kwargs["previous_failures"])

    def test_repeated_transient_failures_degrade_then_become_unavailable(self) -> None:
        class Timeout:
            def search(self, query, *, limit):
                raise TimeoutError("timeout")
        first = self.module.probe("source", Timeout(), "query", previous_failures=0)
        second = self.module.probe("source", Timeout(), "query", previous_failures=1)
        third = self.module.probe("source", Timeout(), "query", previous_failures=2)
        self.assertEqual("transient-failure", first["status"])
        self.assertEqual("degraded", second["status"])
        self.assertEqual("unavailable", third["status"])

    def test_markdown_report_is_stable_and_human_readable(self) -> None:
        report = {"checked_at": "2026-07-19T00:00:00Z", "status": "healthy", "sources": [{"source": "pubmed", "status": "healthy", "consecutive_failures": 0, "detail": "record=1"}]}
        rendered = self.module.render_markdown(report)
        self.assertIn("| pubmed | healthy | 0 | record=1 |", rendered)
        self.assertIn("Overall: **healthy**", rendered)

    def test_scheduled_workflow_restores_and_saves_drift_state(self) -> None:
        workflow = (self.root / ".github" / "workflows" / "public-api-drift.yml").read_text(encoding="utf-8")
        self.assertIn("actions/cache/restore@", workflow)
        self.assertIn("--state-in drift/state.json", workflow)
        self.assertIn("actions/cache/save@", workflow)


if __name__ == "__main__":
    unittest.main()
