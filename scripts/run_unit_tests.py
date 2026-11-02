#!/usr/bin/env python3
"""Run unittest modules in isolated processes; opt in via CODEX_SCIENCE_TEST_WORKERS.

Import skips/errors retain unittest outcomes. SIGINT/SIGTERM stop workers,
remove scratch directories, and exit with status 130/143 respectively.
Worker output uses private files so test descendants cannot delay shutdown.
Limits: discovery imports modules in this process; shared TestCase classes and
package load_tests hooks fail closed. Use serial discovery for such suites.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest


# Timing-sensitive assertions require these modules to run after the parallel phase.
SERIAL_MODULES = frozenset({
    "test_transport_v3", "test_open_fulltext", "test_run_driver",
    "test_cli_literature_evaluation", "test_mcp_proxy", "test_update_hook",
    "test_trajectory_consensus",
})
COUNTS = ("tests_run", "failures", "errors", "skips", "expected_failures", "unexpected_successes")


def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test


def prepare_imports(start):
    # Match `python -m unittest discover -s tests`, including namespace imports.
    sys.path[0] = os.getcwd()
    sys.path.insert(0, str(start))


def discover(start):
    loader = unittest.TestLoader()
    imported = set(sys.modules)
    suite = loader.discover(str(start))
    # Children reload test modules, so package hooks cannot preserve configured instances.
    for name, module in sys.modules.copy().items():
        if name not in imported and hasattr(module, "__path__") and hasattr(module, "load_tests"):
            raise ValueError(
                f"package load_tests hook in {name!r} cannot be replayed safely; "
                "run serially (unset CODEX_SCIENCE_TEST_WORKERS or set it to 1)"
            )
    modules = defaultdict(list)
    for test in test_ids(suite):
        module = type(test).__module__
        if module == "unittest.loader" and type(test).__name__ in ("ModuleSkipped", "_FailedTest"):
            module = test._testMethodName
        modules[module].append(test.id())
    return dict(modules)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_ids = []

    def startTest(self, test):
        self.executed_ids.append(test.id())
        super().startTest(test)


def run_child(module, destination):
    loader = unittest.TestLoader()
    try:
        imported = importlib.import_module(module)
    except unittest.SkipTest as exc:
        suite = unittest.loader._make_skipped_test(module, exc, loader.suiteClass)
    except Exception:
        suite, _ = unittest.loader._make_failed_import_test(module, loader.suiteClass)
        print("discovery failed:", file=sys.stderr)
    else:
        suite = loader.loadTestsFromModule(imported, pattern="test*.py")
        if loader.errors:
            raise ValueError("discovery failed:\n" + "\n".join(loader.errors))
    ids = [test.id() for test in test_ids(suite)]
    result = unittest.TextTestRunner(verbosity=1, resultclass=RecordedResult).run(suite)
    payload = dict(zip(COUNTS, (
        result.testsRun, len(result.failures), len(result.errors), len(result.skipped),
        len(result.expectedFailures), len(result.unexpectedSuccesses),
    )))
    payload["ids"] = ids
    payload["executed_ids"] = result.executed_ids
    # Fixture outcomes use unittest's non-TestCase holders and do not start tests.
    for name, outcomes in (("fixture_skips", result.skipped), ("fixture_errors", result.errors)):
        payload[name] = [test.id() for test, _ in outcomes if not isinstance(test, unittest.TestCase)]
    Path(destination).write_text(json.dumps(payload), encoding="utf-8")
    return 0 if result.wasSuccessful() else 1


def validate_result(payload, expected, module):
    if not isinstance(payload, dict):
        raise ValueError("malformed result: expected an object")
    # Subtests and fixtures contribute outcomes independently of method counts.
    for key in COUNTS:
        if type(payload.get(key)) is not int or payload[key] < 0:
            raise ValueError(f"malformed result: invalid {key}")
    for key in ("ids", "executed_ids", "fixture_skips", "fixture_errors"):
        values = payload.get(key)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            raise ValueError(f"malformed result: invalid {key}")
    ids = payload["ids"]
    if Counter(ids) != Counter(expected):
        raise ValueError("discovery mismatch: child test-ID multiset differs from serial discovery")
    executed = payload["executed_ids"]
    if Counter(executed) - Counter(ids):
        raise ValueError("malformed result: unknown or repeated executed test ID")
    covered = set()
    classes = {name.rsplit(".", 1)[0] for name in ids}
    for key in ("fixture_skips", "fixture_errors"):
        for fixture in payload[key]:
            match = re.fullmatch(r"(setUpClass|tearDownClass|setUpModule|tearDownModule) \((.+)\)", fixture)
            if match is None:
                raise ValueError("malformed result: invalid fixture outcome")
            phase, scope = match.groups()
            if phase.endswith("Class"):
                if scope not in classes:
                    raise ValueError("malformed result: unknown fixture class")
                affected = [name for name in ids if name.rsplit(".", 1)[0] == scope]
            else:
                if scope != module:
                    raise ValueError("malformed result: unknown fixture module")
                affected = ids
            if phase.startswith("setUp"):
                covered.update(affected)
    if any(name not in covered for name in Counter(ids) - Counter(executed)):
        raise ValueError("malformed result: missing test IDs without fixture outcomes")
    return payload


class WorkerProcesses:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = set()
        self.stopped = False

    def start(self, *args, **kwargs):
        # Serialize launch with cancellation so queued tasks cannot escape cleanup.
        with self.lock:
            if self.stopped:
                raise OSError("worker launch cancelled")
            process = subprocess.Popen(*args, **kwargs)
            self.active.add(process)
            return process

    def discard(self, process):
        with self.lock:
            self.active.discard(process)

    def stop(self):
        with self.lock:
            self.stopped = True
            active = list(self.active)
        for process in active:
            process.terminate()
        deadline = time.monotonic() + 1
        for process in active:
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def run_module(module, expected, start, scratch, processes):
    with (
        tempfile.TemporaryDirectory(prefix="module-", dir=scratch) as directory,
        (Path(directory) / "output.log").open("wb") as capture,
    ):
        root = Path(directory)
        environment = os.environ.copy()
        for key in ("HOME", "CODEX_HOME", "TMPDIR"):
            path = root / key.lower()
            path.mkdir()
            environment[key] = str(path)
        destination = root / "result.json"
        try:
            process = processes.start(
                [sys.executable, str(Path(__file__).resolve()), "--start-directory", str(start),
                 "--module", module, "--result", str(destination)],
                env=environment, stdout=capture, stderr=subprocess.STDOUT,
            )
        except OSError as exc:
            return module, None, "", f"worker launch failed: {exc}"
        try:
            process.wait()
            output = (root / "output.log").read_bytes().decode("utf-8", errors="replace")
        finally:
            if process.poll() is not None:
                processes.discard(process)
        try:
            if process.returncode not in (0, 1):
                raise ValueError(f"worker crash (exit {process.returncode})")
            try:
                payload = json.loads(destination.read_text(encoding="utf-8"))
            except (OSError, ValueError, RecursionError) as exc:
                raise ValueError(f"missing or malformed result: {exc}") from exc
            payload = validate_result(payload, expected, module)
            failed = any(payload[key] for key in ("failures", "errors", "unexpected_successes"))
            if process.returncode != int(failed):
                raise ValueError(f"worker exit {process.returncode} disagrees with result")
            return module, payload, output, None
        except ValueError as exc:
            return module, None, output, str(exc)


def run(start, workers):
    started = time.monotonic()
    totals = dict.fromkeys(COUNTS, 0)
    failed = False
    try:
        modules = discover(start)
        parallel = [name for name in modules if name.rsplit(".", 1)[-1] not in SERIAL_MODULES]
        serial = [name for name in modules if name.rsplit(".", 1)[-1] in SERIAL_MODULES]
        with tempfile.TemporaryDirectory(prefix="unit-tests-") as scratch:
            processes = WorkerProcesses()

            def execute(name):
                return run_module(name, modules[name], start, scratch, processes)

            executor = ThreadPoolExecutor(max_workers=workers)
            try:
                results = list(executor.map(execute, parallel))
                results.extend(executor.submit(execute, name).result() for name in serial)
            finally:
                processes.stop()
                executor.shutdown(wait=True, cancel_futures=True)
        observed = []
        for module, payload, output, error in results:
            if payload is not None:
                observed.extend(payload["ids"])
                for key in COUNTS:
                    totals[key] += payload[key]
            if error or any(payload[key] for key in ("failures", "errors", "unexpected_successes")):
                failed = True
                print(f"=== {module} ===", file=sys.stderr)
                if error:
                    print(error, file=sys.stderr)
                print(output, end="" if output.endswith("\n") else "\n", file=sys.stderr)
        expected = [item for ids in modules.values() for item in ids]
        if Counter(observed) != Counter(expected):
            raise ValueError("discovery mismatch: aggregate test-ID multiset differs from serial discovery")
    except (ImportError, ValueError, OSError) as exc:
        print(f"unit tests: {exc}", file=sys.stderr)
        failed = True
    counts = ", ".join(f"{key}={value}" for key, value in totals.items())
    print(f"{'FAILED' if failed else 'OK'}: {counts}; wall time {time.monotonic() - started:.3f}s")
    return int(failed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-directory", default="tests", help="Unittest discovery directory (default: tests).")
    parser.add_argument("--module", help=argparse.SUPPRESS)
    parser.add_argument("--result", help=argparse.SUPPRESS)
    args = parser.parse_args()
    start = Path(args.start_directory).resolve()
    prepare_imports(start)
    if args.module:
        if not args.result:
            parser.error("a worker requires a result destination")
        try:
            return run_child(args.module, args.result)
        except (ValueError, OSError) as exc:
            print(f"unit tests: {exc}", file=sys.stderr)
            return 1
    value = os.environ.get("CODEX_SCIENCE_TEST_WORKERS", "1")
    try:
        if not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
            raise ValueError
        workers = int(value)
    except ValueError:
        parser.error("CODEX_SCIENCE_TEST_WORKERS must be an integer >= 1")

    def interrupt(signum, frame):
        raise KeyboardInterrupt(signum)

    previous = signal.signal(signal.SIGTERM, interrupt)
    try:
        return run(start, workers)
    except KeyboardInterrupt as exc:
        print("unit tests: interrupted", file=sys.stderr)
        return 128 + (exc.args[0] if exc.args else signal.SIGINT)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    sys.exit(main())
