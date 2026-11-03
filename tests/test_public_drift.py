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

    def test_cli_preflights_every_destination_before_probing_or_writing(self) -> None:
        for option in ("--state-out", "--output-json", "--output-md", "summary"):
            for kind in ("directory", "missing-parent", "file-parent", "loop"):
                for existing in (False, True):
                    with self.subTest(option=option, kind=kind, existing=existing), tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        outputs = [root / name / "report" for name in ("state", "json", "markdown")]
                        for path in outputs:
                            if existing:
                                path.parent.mkdir()
                                path.write_bytes(b"preserve")
                        bad = root / "bad"
                        if kind == "directory":
                            bad.mkdir()
                        elif kind == "missing-parent":
                            bad = bad / "nested" / "report"
                        elif kind == "file-parent":
                            bad.write_bytes(b"preserve")
                            bad = bad / "report"
                        else:
                            bad.symlink_to(bad.name)
                        arguments = ["public_drift.py"]
                        destinations = []
                        for flag, path in zip(("--state-out", "--output-json", "--output-md"), outputs):
                            destination = bad if flag == option else path
                            destinations.append(destination)
                            arguments.extend((flag, str(destination)))
                        environment = {"GITHUB_STEP_SUMMARY": str(bad)} if option == "summary" else {}
                        before = set(root.rglob("*"))
                        succeeds = kind == "missing-parent" and option != "summary"
                        def healthy_probe(*args, **kwargs):
                            for destination in destinations:
                                self.assertTrue(destination.parent.is_dir())
                            return {"source": "mock", "status": "healthy", "consecutive_failures": 0,
                                    "checked_at": "fixed", "detail": "record=1"}
                        with mock.patch.object(sys, "argv", arguments), \
                             mock.patch.object(self.module, "CHECKS", [("mock", object(), "query")]), \
                             mock.patch.object(self.module, "probe", side_effect=healthy_probe) as probe, \
                             mock.patch.dict(os.environ, environment, clear=True), \
                             contextlib.redirect_stderr(io.StringIO()) as stderr:
                            self.assertEqual(0 if succeeds else 1, self.module.main())
                        if succeeds:
                            probe.assert_called_once()
                            self.assertEqual("", stderr.getvalue())
                            self.assertTrue(bad.parent.is_dir())
                            for destination in destinations:
                                self.assertTrue(destination.is_file())
                            self.assertEqual(1, json.loads(destinations[0].read_text())["schema_version"])
                            self.assertEqual("healthy", json.loads(destinations[1].read_text())["status"])
                            self.assertIn("Overall: **healthy**", destinations[2].read_text())
                        else:
                            probe.assert_not_called()
                            self.assertTrue(stderr.getvalue().startswith("error:"), stderr.getvalue())
                            self.assertEqual(before, set(root.rglob("*")))
                            for path in outputs:
                                if existing:
                                    self.assertEqual(b"preserve", path.read_bytes())
                                else:
                                    self.assertFalse(path.exists())

    def test_cli_labels_write_failure_after_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = [root / name for name in ("state.json", "report.json", "report.md")]
            arguments = ["public_drift.py", "--state-out", str(outputs[0]),
                         "--output-json", str(outputs[1]), "--output-md", str(outputs[2])]
            original_write = self.module.write_text_atomic
            def fail_report(path, *args, **kwargs):
                if path == outputs[2]:
                    raise OSError("injected write failure")
                return original_write(path, *args, **kwargs)
            with mock.patch.object(sys, "argv", arguments), \
                 mock.patch.object(self.module, "CHECKS", []), \
                 mock.patch.object(self.module, "probe") as probe, \
                 mock.patch.object(self.module, "write_text_atomic", fail_report), \
                 mock.patch.dict(os.environ, {}, clear=True), \
                 contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.assertEqual(1, self.module.main())
            probe.assert_not_called()
            self.assertIn("error: injected write failure", stderr.getvalue())
            self.assertTrue(outputs[0].is_file())
            self.assertTrue(outputs[1].is_file())
            self.assertFalse(outputs[2].exists())

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

    def test_non_object_and_deep_bodies_become_semantic_drift_rows(self) -> None:
        from codex_science.connectors import ChEMBLConnector, UniProtConnector
        def deep(url):
            raise RecursionError("maximum recursion depth exceeded")
        for connector_class in (UniProtConnector, ChEMBLConnector):
            for fetch in (lambda url: None, lambda url: [], lambda url: "text", deep):
                with self.subTest(connector=connector_class.__name__):
                    record = self.module.probe("source", connector_class(fetch_json=fetch), "query", previous_failures=0)
                    self.assertEqual("semantic-drift", record["status"])
                    self.assertNotEqual("", record["detail"])
        record = self.module.probe("source", UniProtConnector(fetch_json=lambda url: None), "query", previous_failures=0)
        self.assertIn("(AttributeError)", record["detail"])

    def test_http_408_and_429_are_transient_like_5xx(self) -> None:
        import urllib.error
        for code, status in ((408, "transient-failure"), (429, "transient-failure"), (503, "transient-failure"), (404, "semantic-drift")):
            class Failing:
                def search(self, query, *, limit, code=code):
                    raise urllib.error.HTTPError("https://example.invalid", code, "x", {}, None)
            with self.subTest(code=code):
                self.assertEqual(status, self.module.probe("s", Failing(), "q", previous_failures=0)["status"])

    def test_connect_timeout_wrapped_in_urlerror_is_retried(self) -> None:
        import urllib.error
        calls = []
        class Flaky:
            def search(self, query, *, limit):
                calls.append(1)
                if len(calls) == 1:
                    raise urllib.error.URLError(TimeoutError("timed out"))
                return [{"id": "record-1"}]
        self.assertEqual("healthy", self.module.probe("s", Flaky(), "q", previous_failures=0)["status"])
        self.assertEqual(2, len(calls))
        calls.clear()
        class Always:
            def search(self, query, *, limit):
                calls.append(1)
                raise urllib.error.URLError(TimeoutError("timed out"))
        record = self.module.probe("s", Always(), "q", previous_failures=0)
        self.assertEqual(2, len(calls))
        self.assertEqual("timeout after two attempts", record["detail"])

    def test_markdown_collapses_upstream_newlines(self) -> None:
        report = {"checked_at": "t", "status": "findings", "sources": [{"source": "s", "status": "semantic-drift", "consecutive_failures": 1, "detail": "a\n# heading\r\n| x | y |"}]}
        rendered = self.module.render_markdown(report)
        self.assertIn("| s | semantic-drift | 1 | a # heading \\| x \\| y \\| |", rendered)
        self.assertNotIn("\n# heading", rendered)

    def test_outputs_are_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ("state.json", "report.json", "report.md")
            arguments = ["public_drift.py", "--state-out", str(root / names[0]),
                         "--output-json", str(root / names[1]), "--output-md", str(root / names[2])]
            with mock.patch.object(sys, "argv", arguments), \
                 mock.patch.object(self.module, "CHECKS", []), \
                 mock.patch.dict(os.environ, {}, clear=True):
                (root / names[0]).write_text("preserve", encoding="utf-8")
                with mock.patch("codex_science.cli_io.os.replace", side_effect=OSError("injected")), \
                     contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(1, self.module.main())
                self.assertEqual("preserve", (root / names[0]).read_text(encoding="utf-8"))

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
