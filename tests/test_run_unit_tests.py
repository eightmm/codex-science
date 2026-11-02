from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_unit_tests.py"
CALL_TIMEOUT = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.tests = self.root / "tests"
        self.tests.mkdir()

    def module(self, name, source):
        (self.tests / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")

    def invoke(self, workers="2", script=None):
        environment = os.environ.copy()
        environment["CODEX_SCIENCE_TEST_WORKERS"] = workers
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(script or RUNNER)], cwd=self.root, env=environment,
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )

    def passing(self, name="test_ok"):
        self.module(name, """
            import unittest
            class Example(unittest.TestCase):
                def test_ok(self): pass
        """)

    def test_discovery_parity_and_both_import_styles_in_fresh_children(self):
        self.passing("test_transport_v3")
        self.passing("test_compute_backends")
        self.module("test_imports", """
            import unittest
            import test_transport_v3
            import tests.test_compute_backends
            class Imports(unittest.TestCase):
                def test_imports(self):
                    self.assertTrue(test_transport_v3.Example)
                    self.assertTrue(tests.test_compute_backends.Example)
        """)
        (self.tests / "test_extra.py").write_text("# test*.py includes this file\n", encoding="utf-8")
        serial = subprocess.run(
            [sys.executable, "-c", "import unittest,json; "
             "s=unittest.defaultTestLoader.discover('tests'); "
             "exec('def ids(s):\\n for t in s:\\n  if isinstance(t,unittest.TestSuite): yield from ids(t)\\n  else: yield t.id()'); "
             "print(json.dumps(list(ids(s)))); assert not unittest.defaultTestLoader.errors"],
            cwd=self.root, capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )
        self.assertEqual(0, serial.returncode, serial.stderr)
        expected = json.loads(serial.stdout)
        self.assertEqual(3, len(expected))
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(f"tests_run={len(expected)}", result.stdout)
        self.assertIn("OK:", result.stdout)

    def test_discovery_pattern_and_nested_package(self):
        package = self.tests / "nested"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "test_nested.py").write_text(textwrap.dedent("""
            import unittest
            class Nested(unittest.TestCase):
                def test_ok(self): pass
            def load_tests(loader, tests, pattern):
                assert pattern == 'test*.py', pattern
                return tests
        """), encoding="utf-8")
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("tests_run=1", result.stdout)

        for symlinked in (False, True):
            with self.subTest(symlinked=symlinked):
                if symlinked:
                    external = self.root / "external_package"
                    package.rename(external)
                    try:
                        package.symlink_to(external, target_is_directory=True)
                    except (NotImplementedError, OSError) as exc:
                        if isinstance(exc, OSError) and exc.errno not in (
                            errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP,
                        ):
                            raise
                        self.skipTest(f"directory symlinks unavailable: {exc}")
                (package / "test_nested.py").write_text(textwrap.dedent("""
                    from pathlib import Path
                    import unittest
                    class Example(unittest.TestCase):
                        def __init__(self, methodName='runTest', value=0):
                            super().__init__(methodName)
                            self.value = value
                        def test_value(self):
                            Path('executed').touch()
                            self.assertEqual(0, self.value, 'configured instance marker')
                    def load_tests(loader, tests, pattern):
                        assert pattern == 'test*.py', pattern
                        return tests
                """), encoding="utf-8")
                configured = textwrap.dedent("""
                    import unittest
                    from .test_nested import Example
                    def load_tests(loader, tests, pattern):
                        return unittest.TestSuite([Example('test_value', value=1)])
                """)
                (package / "__init__.py").write_text(configured, encoding="utf-8")
                serial = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    cwd=self.root, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True, text=True, timeout=CALL_TIMEOUT,
                )
                self.assertEqual(1, serial.returncode, serial.stderr)
                self.assertIn("configured instance marker", serial.stderr)
                executed = self.root / "executed"
                self.assertTrue(executed.exists())
                executed.unlink()
                for hook in (configured, "import unittest\ndef load_tests(loader, tests, pattern):\n"
                             "    return unittest.TestSuite()\n", "load_tests = 0\n"):
                    with self.subTest(hook=hook):
                        (package / "__init__.py").write_text(hook, encoding="utf-8")
                        result = self.invoke()
                        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                        self.assertIn("nested", result.stderr)
                        self.assertIn("package load_tests", result.stderr)
                        self.assertIn("unset CODEX_SCIENCE_TEST_WORKERS or set it to 1", result.stderr)
                        self.assertIn("tests_run=0", result.stdout)
                        self.assertNotIn("OK:", result.stdout)
                        self.assertFalse(executed.exists(), "worker ran despite package hook")

    def test_aggregates_all_outcomes_and_labels_tracebacks(self):
        self.module("test_outcomes", """
            import unittest
            class Outcomes(unittest.TestCase):
                def test_pass(self): pass
                def test_failure(self): self.fail('failure marker')
                def test_error(self): raise RuntimeError('error marker')
                @unittest.skip('skip marker')
                def test_skip(self): pass
                @unittest.expectedFailure
                def test_expected(self): self.fail('expected marker')
                @unittest.expectedFailure
                def test_unexpected(self): pass
        """)
        self.passing()
        result = self.invoke()
        self.assertEqual(1, result.returncode)
        self.assertIn("tests_run=7, failures=1, errors=1, skips=1, expected_failures=1, unexpected_successes=1", result.stdout)
        for marker in ("=== test_outcomes ===", "failure marker", "error marker", "Traceback"):
            self.assertIn(marker, result.stderr)

    def test_unexpected_success_alone_fails(self):
        self.module("test_unexpected", """
            import unittest
            class Example(unittest.TestCase):
                @unittest.expectedFailure
                def test_ok(self): pass
        """)
        result = self.invoke()
        self.assertEqual(1, result.returncode)
        self.assertIn("unexpected_successes=1", result.stdout)

    def test_subtest_outcome_counts_are_not_method_counts(self):
        for outcome, statement in (
            ("skip", "self.skipTest('subtest skip marker')"),
            ("failure", "self.fail('subtest failure marker')"),
            ("error", "raise RuntimeError('subtest error marker')"),
        ):
            with self.subTest(outcome=outcome):
                self.module("test_subtests", f"""
                    import unittest
                    class Subtests(unittest.TestCase):
                        def test_subtests(self):
                            for value in range(2):
                                with self.subTest(value=value):
                                    {statement}
                        @unittest.expectedFailure
                        def test_expected(self): self.fail('expected marker')
                """)
                result = self.invoke()
                self.assertEqual(0 if outcome == "skip" else 1, result.returncode, result.stderr)
                self.assertIn(
                    f"tests_run=2, failures={2 if outcome == 'failure' else 0}, "
                    f"errors={2 if outcome == 'error' else 0}, skips={2 if outcome == 'skip' else 0}, "
                    "expected_failures=1, unexpected_successes=0", result.stdout,
                )
                self.assertNotIn("malformed result", result.stderr)
                if outcome != "skip":
                    for marker in ("=== test_subtests ===", f"subtest {outcome} marker", "value=0", "value=1"):
                        self.assertIn(marker, result.stderr)

    def test_fixture_skips_account_for_unexecuted_tests(self):
        for phase in ("setUpClass", "setUpModule", "tearDownClass", "tearDownModule"):
            with self.subTest(phase=phase):
                fixture = f"def {phase}():\n    raise unittest.SkipTest('fixture skip marker')\n"
                source = "import unittest\n"
                if phase.endswith("Module"):
                    source += fixture
                source += "class Example(unittest.TestCase):\n"
                if phase.endswith("Class"):
                    source += "    @classmethod\n" + textwrap.indent(fixture.replace("():", "(cls):"), "    ")
                source += "    def test_one(self): pass\n    def test_two(self): pass\n"
                source += "class Other(unittest.TestCase):\n    def test_other(self): pass\n"
                self.module("test_fixture", source)
                result = self.invoke()
                self.assertEqual(0, result.returncode, result.stderr)
                executed = 1 if phase == "setUpClass" else 0 if phase == "setUpModule" else 3
                self.assertIn(f"tests_run={executed}, failures=0, errors=0, skips=1", result.stdout)

    def test_fixture_errors_are_labelled_failures(self):
        for phase in ("setUpClass", "setUpModule", "tearDownClass", "tearDownModule"):
            with self.subTest(phase=phase):
                fixture = f"def {phase}():\n    raise RuntimeError('fixture error marker')\n"
                source = "import unittest\n"
                if phase.endswith("Module"):
                    source += fixture
                source += "class Example(unittest.TestCase):\n"
                if phase.endswith("Class"):
                    source += "    @classmethod\n" + textwrap.indent(fixture.replace("():", "(cls):"), "    ")
                source += "    def test_one(self): pass\n    def test_two(self): pass\n"
                self.module("test_fixture", source)
                result = self.invoke()
                self.assertEqual(1, result.returncode)
                executed = 0 if phase.startswith("setUp") else 2
                self.assertIn(f"tests_run={executed}, failures=0, errors=1, skips=0", result.stdout)
                scope = "test_fixture.Example" if phase.endswith("Class") else "test_fixture"
                for marker in ("=== test_fixture ===", f"{phase} ({scope})", "fixture error marker"):
                    self.assertIn(marker, result.stderr)
                self.assertNotIn("malformed result", result.stderr)

    def test_import_outcomes_match_serial_discovery(self):
        for statement, status, counts in (
            ("raise unittest.SkipTest('import skip marker')", 0, "errors=0, skips=1"),
            ("raise ImportError('import error marker')", 1, "errors=1, skips=0"),
        ):
            with self.subTest(statement=statement):
                self.module("test_import_outcome", "import unittest\n" + statement)
                serial = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                    cwd=self.root, capture_output=True, text=True, timeout=CALL_TIMEOUT,
                )
                self.assertEqual(status, serial.returncode, serial.stderr)
                result = self.invoke()
                self.assertEqual(serial.returncode, result.returncode, result.stderr)
                self.assertIn("tests_run=1, failures=0, " + counts, result.stdout)
                self.assertNotIn("discovery mismatch", result.stderr)
                if status:
                    self.assertIn("=== test_import_outcome ===", result.stderr)
                    self.assertIn("import error marker", result.stderr)

    def test_uncovered_unexecuted_tests_are_refused(self):
        self.module("test_partial", """
            import unittest
            class Example(unittest.TestCase):
                def test_one(self): self._outcome.result.stop()
                def test_two(self): pass
        """)
        result = self.invoke()
        self.assertEqual(1, result.returncode)
        self.assertIn("=== test_partial ===", result.stderr)
        self.assertIn("missing test IDs without fixture outcomes", result.stderr)

    def test_classes_from_helper_modules_fail_closed(self):
        # Serial runs honour the importer's hook or side effect; replaying the helper alone would not.
        (self.tests / "helpers.py").write_text(textwrap.dedent("""
            import unittest
            LIMIT = 0
            class ParamCase(unittest.TestCase):
                def __init__(self, methodName="runTest", value=0):
                    super().__init__(methodName)
                    self.value = value
                def test_value(self): self.assertEqual(0, self.value)
            class Shared(unittest.TestCase):
                def test_limit(self): self.assertEqual(0, LIMIT)
        """), encoding="utf-8")
        cases = {
            "hook": """
                import unittest
                from helpers import ParamCase
                def load_tests(loader, tests, pattern):
                    return unittest.TestSuite([ParamCase("test_value", value=1)])
            """,
            "side_effect": """
                import helpers
                helpers.LIMIT = 1
                from helpers import Shared
            """,
        }
        for case, source in cases.items():
            with self.subTest(case=case):
                self.module("test_a", source)
                result = self.invoke()
                self.assertEqual(1, result.returncode, result.stdout + result.stderr)
                self.assertIn("non-test module 'helpers'", result.stderr)

    def test_empty_and_single_module_worker_boundaries(self):
        empty = self.invoke()
        # Matches serial unittest: 3.12+ exits 5 when no tests ran.
        self.assertEqual(5 if sys.version_info >= (3, 12) else 0, empty.returncode, empty.stderr)
        self.assertIn("tests_run=0", empty.stdout)
        self.passing()
        for workers in ("1", "2", "0002"):
            with self.subTest(workers=workers):
                result = self.invoke(workers)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertIn("tests_run=1", result.stdout)

    def test_invalid_workers(self):
        for value in ("", "0", "000", "-1", "1.5", "two", " 2", "+2", "9" * 5000):
            with self.subTest(value=value[:20]):
                result = self.invoke(value)
                self.assertEqual(2, result.returncode)
                self.assertIn("CODEX_SCIENCE_TEST_WORKERS must be an integer >= 1", result.stderr)

    def test_discovery_error_is_not_a_successful_empty_suite(self):
        self.module("test_broken", "raise ImportError('loader marker')")
        result = self.invoke()
        self.assertEqual(1, result.returncode)
        self.assertIn("discovery failed", result.stderr)
        self.assertIn("loader marker", result.stderr)

    def test_crash_missing_and_malformed_result(self):
        sources = (
            ("import os; os._exit(7)", "worker crash"),
            ("import os; os._exit(0)", "missing or malformed result"),
            ("import os,sys; from pathlib import Path; "
             "Path(sys.argv[sys.argv.index('--result')+1]).write_text('[]'); os._exit(0)",
             "malformed result"),
        )
        for body, marker in sources:
            with self.subTest(marker=marker):
                self.module("test_crash", f"import unittest\nclass Crash(unittest.TestCase):\n def test_crash(self):\n  {body}\n")
                result = self.invoke()
                self.assertEqual(1, result.returncode)
                self.assertIn("=== test_crash ===", result.stderr)
                self.assertIn(marker, result.stderr)

    def test_discovery_mismatch_is_refused(self):
        self.module("test_changed", """
            import sys
            import unittest
            class Example(unittest.TestCase):
                def test_one(self): pass
            def load_tests(loader, tests, pattern):
                if '--module' in sys.argv:
                    return unittest.TestSuite()
                return tests
        """)
        result = self.invoke()
        self.assertEqual(1, result.returncode)
        self.assertIn("discovery mismatch", result.stderr)

    def test_interrupt_stops_workers_and_removes_scratch(self):
        for interruption in (signal.SIGINT, signal.SIGTERM):
            for module, spawn_descendant in (
                ("test_sleeping", False), ("test_transport_v3", False),
                ("test_sleeping", True), ("test_transport_v3", True),
            ):
                with self.subTest(interruption=interruption, module=module, descendant=spawn_descendant):
                    for path in self.tests.glob("test_*.py"):
                        path.unlink()
                    ready = self.root / "ready.json"
                    ready.unlink(missing_ok=True)
                    self.module(module, f"""
                        import json, os, signal, subprocess, sys, time, unittest
                        from pathlib import Path
                        class Sleeping(unittest.TestCase):
                            def test_sleep(self):
                                if {interruption == signal.SIGINT}:
                                    signal.signal(signal.SIGTERM, signal.SIG_IGN)
                                descendant = subprocess.Popen([
                                    sys.executable, '-c', 'import time; time.sleep(3600)',
                                ]) if {spawn_descendant} else None
                                Path('ready.json').write_text(json.dumps([
                                    os.getpid(), str(Path(os.environ['TMPDIR']).parents[1]),
                                    descendant.pid if descendant is not None else None]))
                                time.sleep(3600)
                    """)
                    environment = os.environ.copy()
                    environment["CODEX_SCIENCE_TEST_WORKERS"] = "2"
                    environment["PYTHONDONTWRITEBYTECODE"] = "1"
                    environment["TMPDIR"] = str(self.root)
                    child = descendant = None
                    with subprocess.Popen(
                        [sys.executable, str(RUNNER)], cwd=self.root, env=environment,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        # Launchers such as `cmd &` leave SIGINT ignored, which the runner must inherit.
                        preexec_fn=lambda: [signal.signal(s, signal.SIG_DFL) for s in (signal.SIGINT, signal.SIGTERM)],
                    ) as parent:
                        try:
                            deadline = time.monotonic() + CALL_TIMEOUT
                            while child is None:
                                self.assertIsNone(parent.poll())
                                self.assertLess(time.monotonic(), deadline, "worker did not become ready")
                                try:
                                    child, scratch, descendant = json.loads(ready.read_text())
                                except (OSError, ValueError):
                                    threading.Event().wait(0.01)
                            parent.send_signal(interruption)
                            try:
                                output, errors = parent.communicate(timeout=CALL_TIMEOUT)
                            except subprocess.TimeoutExpired:
                                self.fail("interrupted parent did not stop its worker")
                            self.assertEqual(128 + interruption, parent.returncode, output + errors)
                            with self.assertRaises(ProcessLookupError):
                                os.kill(child, 0)
                            self.assertFalse(Path(scratch).exists(), scratch)
                        finally:
                            for pid in (child, descendant):
                                if pid is not None:
                                    try:
                                        os.kill(pid, signal.SIGKILL)
                                    except ProcessLookupError:
                                        pass
                            if parent.poll() is None:
                                parent.kill()
                            parent.communicate(timeout=CALL_TIMEOUT)

    def test_child_environment_is_private_before_import_and_cleaned(self):
        before = {name: os.environ.get(name) for name in ("HOME", "CODEX_HOME", "TMPDIR")}
        for index in range(2):
            self.module(f"test_environment_{index}", f"""
                import json, os, sys, unittest
                from pathlib import Path
                if '--module' in sys.argv:
                    Path('environment-{index}.json').write_text(json.dumps(
                        {{name: os.environ[name] for name in ('HOME', 'CODEX_HOME', 'TMPDIR')}}))
                class Environment(unittest.TestCase):
                    def test_private(self):
                        for name in ('HOME', 'CODEX_HOME', 'TMPDIR'):
                            self.assertTrue(Path(os.environ[name]).is_dir())
            """)
        wrapper = self.root / "wrapped_runner.py"
        wrapper.write_text(
            "import os, runpy, sys\n"
            "before = dict(os.environ)\n"
            f"runner = runpy.run_path({str(RUNNER)!r})\n"
            "status = runner['main']()\n"
            "assert dict(os.environ) == before, 'runner changed its parent environment'\n"
            "sys.exit(status)\n",
            encoding="utf-8",
        )
        result = self.invoke(script=wrapper)
        self.assertEqual(0, result.returncode, result.stderr)
        paths = []
        for index in range(2):
            payload = json.loads((self.root / f"environment-{index}.json").read_text())
            paths.extend(payload.values())
        self.assertEqual(6, len(set(paths)))
        self.assertTrue(all(not Path(path).exists() for path in paths))
        self.assertEqual(before, {name: os.environ.get(name) for name in before})

    def test_parallel_bound_and_serial_phase_ordering(self):
        for index in range(4):
            self.module(f"test_parallel_{index}", f"""
                import json, os, threading, time, unittest
                from pathlib import Path
                class Parallel(unittest.TestCase):
                    def test_parallel(self):
                        started = time.monotonic()
                        Path('ready-{index}').touch()
                        if {index} < 2:
                            deadline = started + float(os.environ.get('OMS_TEST_CALL_TIMEOUT', '120'))
                            while not (Path('ready-0').exists() and Path('ready-1').exists()):
                                self.assertLess(time.monotonic(), deadline)
                                threading.Event().wait(0.01)
                        Path('done-{index}').write_text(json.dumps([started, time.monotonic()]))
            """)
        for name in ("test_transport_v3", "test_open_fulltext"):
            self.module(name, f"""
                import json, time, unittest
                from pathlib import Path
                class Serial(unittest.TestCase):
                    def test_serial(self):
                        self.assertTrue(all(Path('done-' + str(i)).exists() for i in range(4)))
                        started = time.monotonic()
                        Path('{name}.json').write_text(json.dumps([started, time.monotonic()]))
            """)
        result = self.invoke()
        self.assertEqual(0, result.returncode, result.stderr)
        intervals = [json.loads((self.root / f"done-{i}").read_text()) for i in range(4)]
        events = sorted([(start, 1) for start, _ in intervals] + [(end, -1) for _, end in intervals])
        active = maximum = 0
        for _, change in events:
            active += change
            maximum = max(maximum, active)
        self.assertEqual(2, maximum)
        serial = sorted(json.loads((self.root / f"{name}.json").read_text())
                        for name in ("test_transport_v3", "test_open_fulltext"))
        self.assertGreaterEqual(serial[0][0], max(end for _, end in intervals))
        self.assertGreaterEqual(serial[1][0], serial[0][1])

    def test_result_validation_rejects_invalid_counts_and_ids(self):
        specification = importlib.util.spec_from_file_location("unit_runner", RUNNER)
        runner = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(runner)
        good = dict.fromkeys(runner.COUNTS, 0)
        good.update(tests_run=1, ids=["test_one.Example.test_one"],
                    executed_ids=["test_one.Example.test_one"], fixture_skips=[], fixture_errors=[])
        self.assertEqual(good, runner.validate_result(good, good["ids"], "test_one"))
        for key in runner.COUNTS:
            for value in (0, 2):
                with self.subTest(key=key, value=value):
                    independent = {**good, key: value}
                    self.assertEqual(independent, runner.validate_result(independent, good["ids"], "test_one"))
        for replacement in ({"tests_run": True}, {"failures": -1}, {"errors": "0"},
                            {"ids": None}, {"ids": [1]}, {"ids": []}, {"executed_ids": None},
                            {"executed_ids": [1]}, {"executed_ids": ["unknown"]},
                            {"executed_ids": good["ids"] * 2}, {"fixture_skips": None},
                            {"fixture_errors": [1]}):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                runner.validate_result({**good, **replacement}, good["ids"], "test_one")
        ids = ["test_one.Example.test_one", "test_one.Other.test_two"]
        skipped = {**good, "ids": ids, "executed_ids": ids[1:], "skips": 1,
                   "fixture_skips": ["setUpClass (test_one.Example)"]}
        self.assertEqual(skipped, runner.validate_result(skipped, ids, "test_one"))
        module_skip = {**skipped, "tests_run": 0, "executed_ids": [],
                       "fixture_skips": ["setUpModule (test_one)"]}
        self.assertEqual(module_skip, runner.validate_result(module_skip, ids, "test_one"))
        for independent in ({**skipped, "skips": 0},
                            {**skipped, "fixture_errors": ["setUpModule (test_one)"]}):
            with self.subTest(independent=independent):
                self.assertEqual(independent, runner.validate_result(independent, ids, "test_one"))
        for replacement in ({"fixture_skips": []}, {"fixture_skips": ["invalid"]},
                            {"fixture_skips": ["setUpClass (test_one.Unknown)"]},
                            {"fixture_skips": ["setUpModule (unknown)"]},
                            {"fixture_skips": ["tearDownClass (test_one.Example)"]},
                            {"tests_run": 0, "executed_ids": []}):
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                runner.validate_result({**skipped, **replacement}, ids, "test_one")
        output = io.StringIO()
        with mock.patch.object(runner.subprocess, "Popen", side_effect=OSError("launch refused")):
            with mock.patch.object(runner, "discover", return_value={"test_one": good["ids"]}), \
                    redirect_stdout(output), redirect_stderr(output):
                self.assertEqual(1, runner.run(self.tests, 2))
        self.assertIn("=== test_one ===", output.getvalue())
        self.assertIn("worker launch failed", output.getvalue())
        processes = runner.WorkerProcesses()
        processes.stop()
        processes.stop()
        with mock.patch.object(runner.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(OSError, "worker launch cancelled"):
                processes.start([])
            launch.assert_not_called()

    def test_check_dispatch_preserves_serial_command_and_environment(self):
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_uv = fake_bin / "uv"
        fake_uv.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\"\nprintf '%s\\n' \"$HOME\" \"${CODEX_HOME-unset}\"\nexit \"${FAKE_EXIT-0}\"\n")
        fake_uv.chmod(0o755)
        for workers in (None, "1", "2", "", "0", "-1", "x"):
            for code in (0, 7):
                with self.subTest(workers=workers, code=code):
                    environment = os.environ.copy()
                    environment["PATH"] = str(fake_bin) + os.pathsep + environment["PATH"]
                    environment["FAKE_EXIT"] = str(code)
                    if workers is None:
                        environment.pop("CODEX_SCIENCE_TEST_WORKERS", None)
                    else:
                        environment["CODEX_SCIENCE_TEST_WORKERS"] = workers
                    result = subprocess.run(
                        ["bash", str(ROOT / "scripts/check.sh"), "tests"], env=environment,
                        capture_output=True, text=True, timeout=CALL_TIMEOUT,
                    )
                    if workers in ("", "0", "-1", "x"):
                        self.assertEqual(2, result.returncode)
                        self.assertEqual("", result.stdout)
                    else:
                        self.assertEqual(code, result.returncode)
                        command = "run python scripts/run_unit_tests.py" if workers == "2" else "run python -m unittest discover -s tests"
                        self.assertEqual(command, result.stdout.splitlines()[0])
                        self.assertEqual(os.environ["HOME"], result.stdout.splitlines()[1])
                        self.assertEqual(os.environ.get("CODEX_HOME", "unset"), result.stdout.splitlines()[2])
                        self.assertEqual(code == 0, "unit tests: ok" in result.stdout)


if __name__ == "__main__":
    unittest.main()
