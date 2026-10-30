from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from concurrent.futures import ThreadPoolExecutor
import urllib.parse
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from unittest.mock import MagicMock, Mock

import codex_science.open_fulltext as open_fulltext
from codex_science.open_fulltext import _EuropePMCRedirectHandler, fetch_fulltext, identifiers_from_run
from codex_science.citation_trace import trace_citations
from codex_science.evidence import _validate_query_records
from test_transport_v3 import local_chunked_response, local_redirect_server


class OpenFulltextTests(unittest.TestCase):
    def test_final_request_time_exhaustion_reports_cap(self):
        for elapsed in (0.5, 1, 2):
            with self.subTest(elapsed=elapsed):
                result = fetch_fulltext(["pmid:12345"], self.run, execute=True, max_seconds=1,
                                        clock=Mock(side_effect=[0, 0, elapsed]),
                                        fetch=Mock(return_value=(200, b'{"resultList":{"result":[]}}')))
                self.assertEqual(elapsed >= 1, result["cap_reached"])
        for value in (0, -1, None, True, "1", float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "max_seconds"):
                fetch_fulltext([], self.run, execute=True, max_seconds=value)

    def test_slow_trailers_obey_fulltext_wall_budget(self):
        wall_budget = 0.5
        prompt_limit = wall_budget + 1.5
        # Fast hops need scheduling headroom; every drip lasts at least five seconds.
        slow_chunks = 500
        search_path = urllib.parse.urlsplit(open_fulltext.BASE + "/search").path
        for mode in ("opener", "http-error", "injected"):
            with self.subTest(mode=mode), local_chunked_response(
                status=503 if mode == "http-error" else 200, trailers=slow_chunks,
            ) as response:
                opener = Mock()
                if mode == "http-error":
                    opener.open.side_effect = urllib.error.HTTPError(
                        open_fulltext.BASE + "/search", 503, "Test", response.headers, response)
                else:
                    opener.open.return_value = response
                with patch.object(open_fulltext.urllib.request, "build_opener", return_value=opener):
                    started = time.monotonic()
                    result = fetch_fulltext(["pmid:12345"], self.run, execute=True, max_seconds=wall_budget,
                                            fetch=(lambda *_args, **_kwargs: response) if mode == "injected" else None)
                    elapsed = time.monotonic() - started
                self.assertTrue(result["cap_reached"])
                self.assertEqual("unavailable", result["results"][0]["status"])
                self.assertLess(elapsed, prompt_limit)
                self.assertTrue(response.isclosed())

        with local_redirect_server(trailers=slow_chunks) as (_url, seen, build_opener), patch.object(
            open_fulltext.urllib.request, "build_opener", side_effect=build_opener,
        ):
            started = time.monotonic()
            result = fetch_fulltext(["pmid:12345"], self.run, execute=True, max_seconds=wall_budget)
            elapsed = time.monotonic() - started
            self.assertTrue(result["cap_reached"])
            self.assertEqual("unavailable", result["results"][0]["status"])
            self.assertLess(elapsed, prompt_limit)
            self.assertEqual(1, len(seen))
            self.assertIn("/search?", seen[0])

        for hop in ("initial", "redirect", "target", "status", "tls"):
            with self.subTest(slow_headers=hop), local_redirect_server(
                trailers=0, slow_headers=hop, header_chunks=slow_chunks, single_header=True,
            ) as (
                _url, seen, build_opener,
            ), patch.object(open_fulltext.urllib.request, "build_opener", side_effect=build_opener):
                started = time.monotonic()
                result = fetch_fulltext(["pmid:12345"], self.run, execute=True, max_seconds=wall_budget)
                self.assertLess(time.monotonic() - started, prompt_limit)
                self.assertTrue(result["cap_reached"])
                self.assertEqual("unavailable", result["results"][0]["status"])
                self.assertEqual(
                    ["tls"] if hop == "tls" else [search_path] + (["/target"] if hop == "target" else []),
                    [urllib.parse.urlsplit(path).path for path in seen],
                )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _manifest(self, artifacts=None):
        (self.run / "manifest.json").write_text(json.dumps({"artifacts": artifacts or []}))

    def _study_table(self):
        (self.run / "studies.json").write_text('{"studies":[{"pmid":"12345"}]}')

    def test_fulltext_refuses_conflicting_identity_nonarticle_and_empty_text(self):
        self.assertEqual("", open_fulltext._plain_text(b"<article/>"))
        self.assertEqual("Metadata check", open_fulltext._plain_text(b"<html><p>Metadata check</p></html>"))
        for xml in (
            b'<article><front><article-meta><article-id pub-id-type="pmc">99999</article-id></article-meta></front><p>Wrong</p></article>',
            b'<article><front><article-meta><article-id pub-id-type="pmcid">PMC99999</article-id></article-meta></front><p>Wrong</p></article>',
            b'<article><front><article-meta><article-id pub-id-type="pmid">99999</article-id></article-meta></front><p>Wrong</p></article>',
            b'<article><article-meta><article-id pub-id-type="pmc">99999</article-id></article-meta><p>Wrong</p></article>',
            b'<html><body><p>Service error</p></body></html>',
            b'<article/>', b'<article><p> </p></article>',
        ):
            with self.subTest(xml=xml), tempfile.TemporaryDirectory() as temp:
                metadata = {"resultList": {"result": [{"pmid": "12345", "pmcid": "PMC12345",
                    "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}
                fetch = Mock(side_effect=[(200, json.dumps(metadata).encode()), (200, xml)])
                result = fetch_fulltext(["pmid:12345"], temp, execute=True, fetch=fetch)
                self.assertEqual("unavailable", result["results"][0]["status"])
                output = Path(temp) / "fulltext"
                self.assertFalse(list(output.glob("*.xml")))
                self.assertFalse(list(output.glob("*.txt")))
                rows = [json.loads(line) for line in (output / "fetch-ledger.jsonl").read_text().splitlines()]
                self.assertEqual(["complete", "unavailable"], [row["status"] for row in rows])
        for ids in (b'', b'<article-id pub-id-type="pmc">12345</article-id>',
                    b'<article-id pub-id-type="pmcid">pmc12345</article-id><article-id pub-id-type="pmid">12345</article-id>'):
            with self.subTest(ids=ids):
                xml = b'<article xmlns="urn:jats"><front><article-meta>' + ids + b'</article-meta></front><p>Text</p><ref-list><article-id pub-id-type="pmc">99999</article-id></ref-list></article>'
                fetch = Mock(side_effect=[(200, json.dumps(metadata).encode()), (200, xml)])
                result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
                self.assertEqual("fetched", result["results"][0]["status"])

    def test_http_fetch_rejects_declared_body_shortfall(self):
        for headers, body, refused in (
            ({"Content-Length": "3"}, b"{}", True),
            ({"Content-Length": "1"}, b"", True),
            ({"Content-Length": "bad"}, b"{}", True),
            ({"Content-Length": "-1"}, b"{}", True),
            ({"Content-Length": ""}, b"{}", True),
            ({"Content-Length": "0"}, b"", False),
            ({"Content-Length": "2"}, b"{}", False),
            ({}, b"{}", False),
            ({"Transfer-Encoding": "chunked", "Content-Length": "3"}, b"{}", False),
        ):
            with self.subTest(headers=headers):
                response = MagicMock()
                response.__enter__.return_value = response
                response.status, response.headers = 200, headers
                response.read.return_value = body
                opener = Mock()
                opener.open.return_value = response
                with patch.object(open_fulltext.urllib.request, "build_opener", return_value=opener):
                    if refused:
                        with self.assertRaises(ValueError):
                            open_fulltext._http_fetch(open_fulltext.BASE + "/search", timeout=1, max_body_bytes=10)
                        result = fetch_fulltext(["pmid:12345"], self.run, execute=True)
                        self.assertEqual("unavailable", result["results"][0]["status"])
                    else:
                        self.assertEqual((200, body), open_fulltext._http_fetch(
                            open_fulltext.BASE + "/search", timeout=1, max_body_bytes=10))

    def test_fetch_ledger_preserves_row_boundary_without_final_newline(self):
        output = self.run / "fulltext"
        output.mkdir()
        ledger = output / "fetch-ledger.jsonl"
        prior = {"query_id": "prior", "status": "complete"}
        for suffix in ("", "\n"):
            with self.subTest(suffix=suffix):
                original = json.dumps(prior) + suffix
                ledger.write_text(original)
                for _ in range(2):
                    fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                   fetch=Mock(return_value=(200, b'{"resultList":{"result":[]}}')))
                content = ledger.read_text()
                self.assertTrue(content.startswith(json.dumps(prior) + "\n"))
                self.assertEqual(prior, json.loads(content.splitlines()[0]))
                self.assertEqual(3, len([json.loads(line) for line in content.splitlines()]))
        ledger.write_bytes(b"")
        fetch_fulltext(["pmid:12345"], self.run, execute=True,
                       fetch=Mock(return_value=(200, b'{"resultList":{"result":[]}}')))
        self.assertEqual(1, len(ledger.read_text().splitlines()))
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(fetch_fulltext, ["pmid:12345"], self.run, execute=True,
                                   fetch=Mock(return_value=(200, b'{"resultList":{"result":[]}}')))
                       for _ in range(4)]
            for future in futures:
                result = future.result(timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                self.assertEqual(1, result["requests_recorded"])
        self.assertEqual(5, len([json.loads(line) for line in ledger.read_text().splitlines()]))

    def test_only_explicit_open_licenses_allow_retention(self):
        for license_value, expected in (
            ("All rights reserved", "not-open-access"), ("publisher-specific", "not-open-access"),
            ("not CC BY", "not-open-access"), ("cc by permission only", "not-open-access"),
            ("https://creativecommons.org.example/licenses/by/4.0/", "not-open-access"),
            ("https://creativecommons.org:bad/licenses/by/4.0/", "not-open-access"),
            ("https://[bad", "not-open-access"),
            ("https://creativecommons.org:444/licenses/by/4.0/", "not-open-access"),
            ("https://reader@creativecommons.org/licenses/by/4.0/", "not-open-access"),
            ("ftp://creativecommons.org/licenses/by/4.0/", "not-open-access"),
            ("", "license-unknown"), (None, "license-unknown"), (True, "license-unknown"),
            ("cc by", "fetched"), ("cc by-nc", "fetched"), ("cc by-nc-nd", "fetched"),
            ("cc-by", "fetched"), ("CC BY 4.0", "fetched"), ("CC0", "fetched"),
            ("Creative Commons Attribution 4.0 International", "fetched"),
            ("Creative Commons CC-BY 4.0", "fetched"),
            ("Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International", "fetched"),
            ("https://creativecommons.org/licenses/by/4.0/", "fetched"),
            ("http://creativecommons.org/publicdomain/zero/1.0/", "fetched"),
            ("public-domain", "fetched"),
        ):
            with self.subTest(license_value=license_value), tempfile.TemporaryDirectory() as temp:
                metadata = {"resultList": {"result": [{"pmid": "12345", "pmcid": "PMC12345",
                    "source": "MED", "isOpenAccess": "Y", "license": license_value}]}}
                fetch = Mock(side_effect=[(200, json.dumps(metadata).encode()), (200, b"<article><p>Text</p></article>")])
                result = fetch_fulltext(["pmid:12345"], temp, execute=True, fetch=fetch)
                self.assertEqual(expected, result["results"][0]["status"])
                self.assertEqual(2 if expected == "fetched" else 1, fetch.call_count)
                self.assertEqual(expected == "fetched", (Path(temp) / "fulltext/PMC12345.xml").exists())

    def test_open_access_writes_xml_text_and_request_ledger(self):
        xml = b"<article><title>A title</title><body><sec><title>Methods</title><p>Useful text.</p></sec></body></article>"
        requests = []
        def fetch(url, *, timeout, max_body_bytes):
            requests.append(url)
            if "search?" in url:
                return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
            return 200, xml
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
        self.assertEqual("fetched", result["results"][0]["status"])
        self.assertEqual(2, len(requests))
        self.assertEqual(xml, (self.run / "fulltext/PMC12345.xml").read_bytes())
        self.assertIn("Useful text.", (self.run / "fulltext/PMC12345.txt").read_text())
        ledger = [json.loads(line) for line in (self.run / "fulltext/fetch-ledger.jsonl").read_text().splitlines()]
        self.assertEqual([None, "CC BY"], [entry["license"] for entry in ledger])
        self.assertEqual(hashlib.sha256(xml).hexdigest(), ledger[1]["response_sha256"])
        self.assertEqual("PMC12345", ledger[1]["fulltext_pmcid"])
        self.assertNotIn("pmcid", ledger[1])
        self.assertTrue(all(entry["url"].startswith("https://www.ebi.ac.uk/") for entry in ledger))
        self.assertTrue(all(entry["source"] == "europepmc" and entry["query"] and entry["accessed_at"]
                            and entry["status"] == "complete" for entry in ledger))
        _validate_query_records(ledger)

    def _article_fetch(self, xml):
        metadata = b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
        return Mock(side_effect=[(200, metadata), (200, xml)])

    def test_concurrent_fulltext_publications_keep_pair_and_ledger_order(self):
        output = self.run / "fulltext"
        output.mkdir()
        timeout = float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120"))
        responses_ready = threading.Barrier(2, timeout=timeout)
        first_xml = threading.Event()
        second_finished_or_blocked = threading.Event()
        worker = threading.local()
        original_write = Path.write_bytes
        original_replace = os.replace
        original_flock = open_fulltext.fcntl.flock

        def after_xml():
            if worker.label == "First":
                first_xml.set()
                self.assertTrue(second_finished_or_blocked.wait(timeout))

        def write_bytes(path, data):
            result = original_write(path, data)
            if path.name == "PMC12345.xml":
                after_xml()
            return result

        def replace(source, destination):
            result = original_replace(source, destination)
            if Path(destination).name == "PMC12345.xml":
                after_xml()
            return result

        def flock(descriptor, operation):
            if getattr(worker, "label", None) == "Second" and operation == open_fulltext.fcntl.LOCK_EX:
                try:
                    return original_flock(descriptor, operation | open_fulltext.fcntl.LOCK_NB)
                except BlockingIOError:
                    second_finished_or_blocked.set()
            return original_flock(descriptor, operation)

        def run(label):
            worker.label = label
            xml = f"<article><p>{label} response</p></article>".encode()
            transport = self._article_fetch(xml)

            def fetch(url, **kwargs):
                response = transport(url, **kwargs)
                if "search?" not in url:
                    responses_ready.wait()
                    if label == "Second":
                        self.assertTrue(first_xml.wait(timeout))
                return response

            try:
                return fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
            finally:
                if label == "Second":
                    second_finished_or_blocked.set()

        with patch.object(Path, "write_bytes", write_bytes), patch.object(
            os, "replace", replace,
        ), patch.object(open_fulltext.fcntl, "flock", flock), ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run, label) for label in ("First", "Second")]
            results = [future.result(timeout=timeout) for future in futures]
        for result in results:
            self.assertEqual("fetched", result["results"][0]["status"])
            self.assertEqual(2, result["requests_recorded"])
        xml = (output / "PMC12345.xml").read_bytes()
        self.assertEqual(open_fulltext._plain_text(xml), (output / "PMC12345.txt").read_text())
        rows = [json.loads(line) for line in (output / "fetch-ledger.jsonl").read_text().splitlines()]
        fulltext_rows = [row for row in rows if row["fulltext_pmcid"] is not None]
        self.assertEqual(2, len(fulltext_rows))
        self.assertEqual(hashlib.sha256(xml).hexdigest(), fulltext_rows[-1]["response_sha256"])
        self.assertEqual({row["response_sha256"] for row in fulltext_rows},
                         {result["results"][0]["response_sha256"] for result in results})
        self.assertEqual({"fetch-ledger.jsonl", "PMC12345.xml", "PMC12345.txt"},
                         {path.name for path in output.iterdir()})

    def test_fulltext_staging_failures_preserve_existing_pair_and_remove_temporaries(self):
        original_bytes = Path.write_bytes
        original_text = Path.write_text
        original_sync = os.fsync
        original_replace = os.replace
        original_flock = open_fulltext.fcntl.flock
        original_open = Path.open
        original_mkstemp = tempfile.mkstemp
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        for prior in (None, b"", b"<article><p>Old response</p></article>"):
            for failure in ("xml-create", "text-create", "xml-write", "text-write", "xml-sync",
                            "text-sync", "replace", "lock", "ledger", "initial-ledger", "initial-lock",
                            "initial-ledger-missing", "initial-lock-missing"):
                with self.subTest(prior=prior, failure=failure), tempfile.TemporaryDirectory() as temp:
                    output = Path(temp) / "fulltext"
                    output.mkdir()
                    initial_failure = failure.startswith("initial-")
                    if initial_failure and not failure.endswith("-missing"):
                        (output / "fetch-ledger.jsonl").write_bytes(b"")
                    xml_path, text_path = output / "PMC12345.xml", output / "PMC12345.txt"
                    old_text = open_fulltext._plain_text(prior) if prior else ""
                    if prior is not None:
                        xml_path.write_bytes(prior)
                        text_path.write_text(old_text)
                    sync_count = 0
                    create_count = 0
                    response_received = False

                    def mkstemp(**kwargs):
                        nonlocal create_count
                        create_count += 1
                        self.assertEqual(output, kwargs["dir"])
                        self.assertTrue(kwargs["prefix"].startswith("."))
                        if (failure, create_count) in (("xml-create", 1), ("text-create", 2)):
                            raise OSError("fixture temporary creation failure")
                        return original_mkstemp(**kwargs)

                    def flock(descriptor, operation):
                        if failure.startswith("initial-lock") or (failure == "lock" and response_received):
                            raise OSError("fixture lock failure")
                        return original_flock(descriptor, operation)

                    def open_file(path, *args, **kwargs):
                        if path.name == "fetch-ledger.jsonl" and (
                            failure.startswith("initial-ledger") or (failure == "ledger" and response_received)
                        ):
                            raise OSError("fixture ledger failure")
                        return original_open(path, *args, **kwargs)

                    def write_bytes(path, data):
                        if failure == "xml-write" and path.suffix == ".xml":
                            original_bytes(path, b"partial")
                            raise OSError("fixture XML write failure")
                        return original_bytes(path, data)

                    def write_text(path, text, **kwargs):
                        if failure == "text-write" and path.suffix == ".txt":
                            original_text(path, "partial", **kwargs)
                            raise OSError("fixture text write failure")
                        return original_text(path, text, **kwargs)

                    def fsync(descriptor):
                        nonlocal sync_count
                        sync_count += 1
                        if (failure, sync_count) in (("xml-sync", 1), ("text-sync", 2)):
                            raise OSError("fixture sync failure")
                        return original_sync(descriptor)

                    def replace(source, destination):
                        if failure == "replace":
                            raise OSError("fixture replacement failure")
                        return original_replace(source, destination)

                    with patch.object(Path, "write_bytes", write_bytes), patch.object(
                        Path, "write_text", write_text,
                    ), patch.object(os, "fsync", fsync), patch.object(
                        os, "replace", replace,
                    ), patch.object(open_fulltext.fcntl, "flock", flock), patch.object(
                        Path, "open", open_file,
                    ), patch.object(tempfile, "mkstemp", mkstemp):
                        xml = b"<article><p>New response</p></article>"
                        transport = self._article_fetch(xml)

                        def fetch(url, **kwargs):
                            nonlocal response_received
                            response_received = "search?" not in url
                            return transport(url, **kwargs)

                        ids = ["pmid:12345", "pmid:67890"] if initial_failure or failure in {"lock", "ledger"} else ["pmid:12345"]
                        if initial_failure:
                            stdout = io.StringIO()
                            with patch.object(open_fulltext, "_http_fetch", fetch), redirect_stdout(stdout):
                                code = cli.main(["--run-dir", temp, "--id", ids[0], "--id", ids[1], "--execute"])
                            self.assertEqual(0, code)
                            result = json.loads(stdout.getvalue())
                            self.assertEqual("open-fulltext-v1", result["schema"])
                            self.assertEqual([{"identifier": identifier, "status": "write-failed"} for identifier in ids],
                                             result["results"])
                        else:
                            result = fetch_fulltext(ids, temp, execute=True, fetch=fetch)
                    self.assertEqual("write-failed", result["results"][0]["status"])
                    self.assertEqual(prior is not None, xml_path.exists())
                    self.assertEqual(prior is not None, text_path.exists())
                    if prior is not None:
                        self.assertEqual(prior, xml_path.read_bytes())
                        self.assertEqual(old_text, text_path.read_text())
                    names = {"fetch-ledger.jsonl"}
                    if failure == "initial-ledger-missing":
                        names.clear()
                    if prior is not None:
                        names.update({"PMC12345.xml", "PMC12345.txt"})
                    self.assertEqual(names, {path.name for path in output.iterdir()})
                    ledger = output / "fetch-ledger.jsonl"
                    rows = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
                    expected_requests = 0 if initial_failure else (1 if failure in {"lock", "ledger"} else 2)
                    self.assertEqual(expected_requests, result["requests_recorded"])
                    self.assertEqual(expected_requests, len(rows))
                    if initial_failure or failure in {"lock", "ledger"}:
                        self.assertEqual(1 if initial_failure else 2, transport.call_count)
                        self.assertEqual(["write-failed", "write-failed"],
                                         [row["status"] for row in result["results"]])
                    if expected_requests == 2:
                        self.assertEqual(hashlib.sha256(xml).hexdigest(), rows[-1]["response_sha256"])

    def test_fulltext_ledger_lock_is_stable_across_retries_without_extra_files(self):
        output = self.run / "fulltext"
        ledger = output / "fetch-ledger.jsonl"
        raw = self.run / "raw"
        raw.mkdir()
        xml = b"<article><p>Response</p></article>"
        original_replace = os.replace

        def replace(source, destination):
            with ledger.open("a+b") as contender:
                with self.assertRaises(BlockingIOError):
                    open_fulltext.fcntl.flock(contender.fileno(), open_fulltext.fcntl.LOCK_EX | open_fulltext.fcntl.LOCK_NB)
            return original_replace(source, destination)

        with patch.object(os, "replace", side_effect=replace) as replacements:
            first = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=self._article_fetch(xml))
        self.assertEqual("fetched", first["results"][0]["status"])
        self.assertEqual(2, replacements.call_count)
        inode = ledger.stat().st_ino
        with patch.object(os, "replace", side_effect=replace) as replacements:
            second = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=self._article_fetch(xml))
        self.assertEqual("fetched", second["results"][0]["status"])
        self.assertEqual(2, replacements.call_count)
        self.assertEqual(inode, ledger.stat().st_ino)
        self.assertEqual(4, len(ledger.read_text().splitlines()))
        self.assertEqual({"fetch-ledger.jsonl", "PMC12345.xml", "PMC12345.txt"},
                         {path.name for path in output.iterdir()})
        self.assertEqual([], list(raw.iterdir()))
        self.assertEqual([output / "PMC12345.xml"], list(output.glob("PMC*.xml")))
        self.assertEqual([output / "PMC12345.txt"], list(output.glob("PMC*.txt")))
        for kind in ("directory", "fifo", "symlink"):
            with self.subTest(lock=kind), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp) / "fulltext"
                directory.mkdir()
                unsafe_lock = directory / "fetch-ledger.jsonl"
                if kind == "directory":
                    unsafe_lock.mkdir()
                elif kind == "fifo":
                    os.mkfifo(unsafe_lock)
                else:
                    unsafe_lock.symlink_to("missing")
                fetch = Mock()
                with self.assertRaises(ValueError):
                    fetch_fulltext(["pmid:12345"], temp, execute=True, fetch=fetch)
                fetch.assert_not_called()

    def test_fulltext_retry_removes_only_abandoned_publication_temporaries(self):
        output = self.run / "fulltext"
        output.mkdir()
        abandoned = [output / (".fulltext-" + "0" * 32 + "-deadbeef" + suffix)
                     for suffix in (".xml", ".txt")]
        unrelated = [output / name for name in (
            ".fulltext-user-notes.xml", ".fulltext-" + "0" * 31 + "-deadbeef.xml",
            ".fulltext-" + "0" * 33 + "-deadbeef.xml", ".fulltext-" + "g" * 32 + "-deadbeef.xml",
            ".fulltext-" + "0" * 32 + "-.txt",
        )]
        for path in unrelated:
            path.write_bytes(b"keep")
        xml = b"<article><p>Response</p></article>"
        for during_fetch in (False, True):
            with self.subTest(during_fetch=during_fetch):
                if not during_fetch:
                    for path in abandoned:
                        path.write_bytes(b"partial")
                transport = self._article_fetch(xml)

                def fetch(url, **kwargs):
                    if during_fetch and "search?" not in url:
                        for path in abandoned:
                            path.write_bytes(b"partial")
                    return transport(url, **kwargs)

                result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
                self.assertEqual("fetched", result["results"][0]["status"])
                self.assertTrue(all(not path.exists() for path in abandoned))
                self.assertTrue(all(path.read_bytes() == b"keep" for path in unrelated))
                expected = {"fetch-ledger.jsonl", "PMC12345.xml", "PMC12345.txt"}
                self.assertEqual(expected | {path.name for path in unrelated},
                                 {path.name for path in output.iterdir()})

    def test_structured_jats_rendering_preserves_order_without_nested_duplicates(self):
        xml = b"""<article><front><article-meta><title-group><article-title>Article title</article-title></title-group><abstract><p>Abstract text.</p></abstract></article-meta></front><body><sec><title>Methods</title><p>First paragraph.</p><sec><title>Nested section</title><p>Nested paragraph.</p><fig><label>Figure 1</label><caption><p>Figure caption text.</p></caption></fig><table-wrap><label>Table 1</label><caption><p>Table caption text.</p></caption><table><thead><tr><th>Outcome</th><th>Count</th></tr></thead><tbody><tr><td>Positive</td><td>12</td></tr></tbody></table></table-wrap></sec></sec><ref-list><title>References</title><ref><p>Reference text must be omitted.</p></ref></ref-list><supplementary-material><label>Supplement</label><caption><p>Supplement caption.</p></caption><p>Supplement body must be omitted.</p></supplementary-material></body></article>"""
        rendered = open_fulltext._plain_text(xml)
        blocks = rendered.split("\n\n")
        self.assertEqual([
            "Article title", "Abstract text.", "Methods", "First paragraph.",
            "Nested section", "Nested paragraph.", "Figure 1 Figure caption text.",
            "Table 1 Table caption text.", "Outcome | Count", "Positive | 12",
            "Supplement Supplement caption.",
        ], blocks)
        self.assertEqual(1, rendered.count("Figure caption text."))
        self.assertNotIn("Reference text", rendered)
        self.assertNotIn("Supplement body", rendered)

    def test_jats_external_doctypes_are_removed_before_parsing(self):
        public = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                  b'<!DOCTYPE article\n PUBLIC "-//NLM//DTD JATS 1.4//EN" '
                  b'"JATS-archivearticle1-4.dtd">\n'
                  b'<article><body><p>JATS text.</p></body></article>')
        system = b"<!DOCTYPE article SYSTEM 'article.dtd'><article><p>System text.</p></article>"
        comment_prolog = (b'<!-- generated from <article> -->'
                          b'<!DOCTYPE article SYSTEM "article.dtd">'
                          b'<?source after doctype?>'
                          b'<article><p>Comment prolog text.</p></article>')
        pi_prolog = (b'<?source generated from <article>?>'
                     b'<!DOCTYPE article SYSTEM "article.dtd">'
                     b'<!-- after doctype -->'
                     b'<article><p>PI prolog text.</p></article>')
        self.assertEqual("JATS text.", open_fulltext._plain_text(public))
        self.assertEqual("JATS text.", open_fulltext._plain_text(b"\xef\xbb\xbf" + public))
        self.assertEqual("System text.", open_fulltext._plain_text(system))
        self.assertEqual("Comment prolog text.", open_fulltext._plain_text(comment_prolog))
        self.assertEqual("PI prolog text.", open_fulltext._plain_text(pi_prolog))

    def test_doctype_refusal_checks_are_bounded_for_long_prologs(self):
        comments_without_root = b"<!-- comment -->" * 3000
        unterminated_doctype = b'<!DOCTYPE article SYSTEM "' + comments_without_root
        for body in (
            b'<!DOCTYPE article SYSTEM "article.dtd">' + comments_without_root,
            unterminated_doctype,
        ):
            started = time.perf_counter()
            with self.subTest(size=len(body)), self.assertRaises(ValueError):
                open_fulltext._plain_text(body)
            self.assertLess(time.perf_counter() - started, 0.5)

    def test_external_doctype_refusal_cases(self):
        cases = (
            b'<!DOCTYPE article [<!ELEMENT article ANY>]><article/>',
            b'<!DOCTYPE article [<!ENTITY x "payload">]><article>&x;</article>',
            (b'<!DOCTYPE article [<!ENTITY a "ha"><!ENTITY b "&a;&a;">]'
             b'<article>&b;&b;&b;&b;&b;&b;&b;&b;</article>'),
            b'<!DOCTYPE article SYSTEM "a.dtd"><!DOCTYPE article SYSTEM "b.dtd"><article/>',
            b'<!-- unterminated comment <!DOCTYPE article SYSTEM "a.dtd"><article/>',
            b'<?unterminated PI <!DOCTYPE article SYSTEM "a.dtd"><article/>',
            '<!DOCTYPE article><article/>'.encode("utf-16"),
        )
        for xml in cases:
            with self.subTest(xml=xml[:60]), self.assertRaises(ValueError):
                open_fulltext._plain_text(xml)
        with self.assertRaises(open_fulltext.ET.ParseError):
            open_fulltext._plain_text(b'<article/><!DOCTYPE article SYSTEM "a.dtd">')

    def test_utf16_entity_declarations_are_refused_with_or_without_bom(self):
        xml = '<!DOCTYPE article [<!ENTITY e "expanded">]><article><p>&e;</p></article>'
        payloads = []
        for encoding, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            encoded = xml.encode(encoding)
            payloads.extend((encoded, bom + encoded))
        for payload in payloads:
            with self.subTest(prefix=payload[:8]), self.assertRaises(ValueError):
                open_fulltext._plain_text(payload)

    def test_non_utf8_xml_encoding_declaration_is_refused(self):
        xml = b'<?xml version="1.0" encoding="ISO-8859-1"?><article><p>Text</p></article>'
        with self.assertRaises(ValueError):
            open_fulltext._plain_text(xml)

    def test_xml_refusal_results_include_machine_readable_reason(self):
        def fetch(url, **kwargs):
            if "search?" in url:
                return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
            return 200, b'<!DOCTYPE article [<!ENTITY x "payload">]><article>&x;</article>'
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
        self.assertEqual("unavailable", result["results"][0]["status"])
        self.assertEqual("xml-declaration-refused", result["results"][0]["reason"])

    def test_unavailable_http_and_malformed_search_results_include_reason(self):
        http = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                              fetch=lambda *args, **kwargs: (503, b"unavailable"))
        malformed = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                   fetch=lambda *args, **kwargs: (200, b"not-json"))
        self.assertEqual("http-503", http["results"][0]["reason"])
        self.assertEqual("search-response-malformed", malformed["results"][0]["reason"])

    def test_unavailable_pmcid_and_xml_parse_results_include_reason(self):
        no_pmcid = fetch_fulltext(
            ["pmid:12345"], self.run, execute=True,
            fetch=lambda *args, **kwargs: (200, b'{"resultList":{"result":[{"pmid":"12345","source":"MED"}]}}'),
        )
        self.assertEqual("no-pmcid", no_pmcid["results"][0]["reason"])

        def malformed_xml_fetch(url, **kwargs):
            if "search?" in url:
                return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
            return 200, b"<article>"
        malformed_xml = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=malformed_xml_fetch)
        self.assertEqual("xml-parse-error", malformed_xml["results"][0]["reason"])

        def failed_fulltext_fetch(url, **kwargs):
            if "search?" in url:
                return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
            return 502, b"bad gateway"
        failed_fulltext = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=failed_fulltext_fetch)
        self.assertEqual("http-502", failed_fulltext["results"][0]["reason"])

    def test_cli_with_explicit_id_does_not_require_manifest(self):
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_no_manifest", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run), "--id", "pmid:12345"])
        self.assertEqual(0, code)
        self.assertEqual("planned", json.loads(stdout.getvalue())["results"][0]["status"])

    def test_study_table_without_manifest_provides_fallback_identifiers(self):
        (self.run / "studies.json").write_text(
            '{"studies":[{"pmid":"12345"},{"doi":"10.1234/example"},'
            '{"pmid":"54321","excluded":true},{"doi":" 10.1234/ABC"}]}'
        )
        self.assertEqual(["doi:10.1234/abc", "doi:10.1234/example", "pmid:12345"], identifiers_from_run(self.run))

    def test_study_pmcid_replaces_pmid_and_doi_and_skips_lookup(self):
        (self.run / "studies.json").write_text(
            '{"studies":[{"identifiers":["pmid:25203112","pmcid:PMC4159349","doi:10.1234/a"]},{"pmid":"54321"},'
            '{"persistent_id":"pmid:12345","related_articles":[{"pmcid":"PMC67890"}]},'
            '{"pmid":"22222","pmcid":"N/A"},'
            '{"pmid":"33333","identifiers":{"related_articles":[{"pmcid":"PMC11111"}]}},'
            '{"pmid":"44444","pmcid":"PMC44444","identifiers":[{"pmid":"44444"}]}]}')
        self.assertEqual(["pmcid:N/A", "pmcid:PMC11111", "pmcid:PMC4159349", "pmcid:PMC44444", "pmcid:PMC67890",
                          "pmid:12345", "pmid:22222", "pmid:33333", "pmid:54321"], identifiers_from_run(self.run))
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            if "search?" in url:
                return 200, json.dumps({"resultList": {"result": [
                    {"pmcid": "PMC4159349", "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}).encode()
            return 200, b"<article><p>text</p></article>"
        fetch_fulltext(["pmcid:PMC4159349"], self.run, execute=True, fetch=fetch)
        self.assertFalse(any("EXT_ID" in urllib.parse.unquote(url) for url in calls))

    def test_manifest_branch_maps_cited_pmid_to_study_pmcid(self):
        (self.run / "studies.json").write_text(
            '{"studies":[{"identifiers":["pmid:25203112","pmcid:PMC4159349"]},{"pmid":"54321"},'
            '{"pmid":"67890","pmcid":"PMC1","excluded":true},'
            '{"persistent_id":"pmid:12345","related_articles":[{"pmcid":"PMC67890"}]},'
            '{"pmid":"22222","pmcid":"N/A"},'
            '{"pmid":"33333","identifiers":{"related_articles":[{"pmcid":"PMC11111"}]}},'
            '{"pmid":"44444","pmcid":"PMC44444","identifiers":[{"pmid":"44444"}]}]}')
        (self.run / "report.md").write_text(
            "Cites PMID:25203112, PMID:54321, PMID:67890, PMID:12345, PMID:22222, PMID:33333 and PMID:44444.")
        self._manifest([{"kind": "report", "path": "report.md"}])
        self.assertEqual(["pmcid:PMC4159349", "pmcid:PMC44444", "pmid:12345", "pmid:22222", "pmid:33333",
                          "pmid:54321"],
                         identifiers_from_run(self.run))

    def test_manifest_symlink_is_still_rejected(self):
        outside = Path(self.temp.name) / "outside-manifest.json"
        outside.write_text('{"artifacts":[]}')
        (self.run / "manifest.json").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink in run path"):
            identifiers_from_run(self.run)

    def test_cli_without_any_identifiers_gives_actionable_error(self):
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_no_ids", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        for args in (["--run-dir", str(self.run)], []):
            stdout = io.StringIO()
            with self.subTest(args=args), redirect_stdout(stdout):
                code = cli.main(args)
            output = json.loads(stdout.getvalue())
            self.assertEqual(2, code)
            self.assertEqual("invalid_request", output["error"]["code"])
            self.assertIn("--id", output["error"]["message"])
            self.assertIn("study table", output["error"]["message"])

    def test_structured_blocks_keep_boundaries_and_inline_text_stays_joined(self):
        xml = b"""<article><front><article-meta><abstract><sec><title>Background</title><p>B text.</p></sec><sec><title>Results</title><p>R text.</p></sec></abstract></article-meta></front><body><p>CO<sub>2</sub> and 10<sup>-3</sup><table-wrap><label>Nested</label><caption><title>Caption title</title><p>Caption text.</p></caption><table><tr><td>Measure</td><td>8</td></tr></table></table-wrap> tail.</p><p><italic>No significant </italic>difference.</p><p>Before.<fig><label>Figure 2</label><caption><p>Caption.</p></caption></fig>After.</p><p>Prior.<supplementary-material><label>Supplement 2</label><caption><p>Supplement caption.</p></caption><p>Hidden supplementary body.</p></supplementary-material>Following.</p><list><list-item>Item <italic>one</italic><p>Detail.</p><table><tr><td>A</td><td>B</td></tr></table></list-item></list><fig><label>Figure</label><caption><title>Figure title</title><p>Figure text.</p></caption></fig><supplementary-material><label>Supplement 1</label><caption><title>Supplement title</title><p>Supplement text.</p></caption><p>Omitted body.</p></supplementary-material><ack><title>Acknowledgments</title><p>Thanks.</p></ack><app><title>Appendix A</title><p>Appendix text.</p></app><boxed-text><title>Box 1</title><p>Box text.</p></boxed-text></body></article>"""
        self.assertEqual([
            "Background", "B text.", "Results", "R text.", "CO2 and 10-3",
            "Nested Caption title Caption text.", "Measure | 8", "tail.", "No significant difference.",
            "Before.", "Figure 2 Caption.", "After.", "Prior.",
            "Supplement 2 Supplement caption.", "Following.",
            "Item one", "Detail.", "A | B", "Figure Figure title Figure text.",
            "Supplement 1 Supplement title Supplement text.", "Acknowledgments",
            "Thanks.", "Appendix A", "Appendix text.", "Box 1", "Box text.",
        ], open_fulltext._plain_text(xml).split("\n\n"))
        wrapped = b"""<article><body><p>Before.<fig-group><fig><label>Figure 3</label><caption><p>Grouped.</p></caption></fig></fig-group>Middle.<boxed-text><supplementary-material><label>S3</label><caption><p>Boxed supplement.</p></caption><p>Hidden body.</p></supplementary-material></boxed-text>After.</p></body></article>"""
        self.assertEqual(["Before.", "Figure 3 Grouped.", "Middle.", "S3 Boxed supplement.", "After."],
                         open_fulltext._plain_text(wrapped).split("\n\n"))

    def test_identifier_queries_are_type_specific(self):
        cases = (
            ("doi:10.1371/journal.pone.0029797", 'DOI:"10.1371/journal.pone.0029797"'),
            ("pmcid:PMC3256195", "PMCID:PMC3256195"),
            ("pmid:22253785", "EXT_ID:22253785 AND SRC:MED"),
        )
        for identifier, expected in cases:
            with self.subTest(identifier=identifier):
                urls = []
                def fetch(url, **kwargs):
                    urls.append(url)
                    record = {"pmcid": "PMC3256195", "doi": "10.1371/journal.pone.0029797",
                              "pmid": "22253785", "source": "MED", "isOpenAccess": "N"}
                    return 200, json.dumps({"resultList": {"result": [record]}}).encode()
                result = fetch_fulltext([identifier], self.run, execute=True, fetch=fetch)
                actual = urllib.parse.parse_qs(urllib.parse.urlsplit(urls[0]).query)["query"][0]
                self.assertEqual(expected, actual)
                self.assertEqual("not-open-access", result["results"][0]["status"])

    def test_empty_and_mismatched_records_are_not_found(self):
        responses = (b'{"resultList":{"result":[]}}',
                     b'{"resultList":{"result":[{"pmcid":"PMC99999","doi":"10.9999/other","pmid":"99999","source":"MED"}]}}')
        for response in responses:
            with self.subTest(response=response):
                result = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                        fetch=lambda *args, **kwargs: (200, response))
                self.assertEqual("not-found", result["results"][0]["status"])

    def test_quoted_doi_is_rejected_and_non_200_success_status_is_unavailable(self):
        fetch = Mock(return_value=(200, b"{}"))
        with self.assertRaisesRegex(ValueError, "malformed DOI"):
            fetch_fulltext(['doi:10.1234/a"b'], self.run, execute=True, fetch=fetch)
        fetch.assert_not_called()
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                fetch=lambda *args, **kwargs: (201, b'{"resultList":{"result":[]}}'))
        self.assertEqual("unavailable", result["results"][0]["status"])
        malformed = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                   fetch=lambda *args, **kwargs: (200, b"not-json"))
        self.assertEqual("unavailable", malformed["results"][0]["status"])

    def test_response_body_cap_returns_unavailable(self):
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True, max_body_bytes=2,
                                fetch=lambda *args, **kwargs: (200, b"{}x"))
        self.assertEqual("unavailable", result["results"][0]["status"])

    def test_unsafe_output_path_fails_before_any_fetch(self):
        self._manifest()
        self._study_table()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.run / "fulltext").symlink_to(outside, target_is_directory=True)
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        fetch = Mock()

        def snapshot(root):
            return {path.relative_to(root).as_posix(): (
                ("symlink", os.readlink(path)) if path.is_symlink() else
                ("directory", None) if path.is_dir() else ("file", path.read_bytes())
            ) for path in root.rglob("*")}

        before = snapshot(self.run)
        stdout = io.StringIO()
        with patch.object(open_fulltext, "_http_fetch", fetch), redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run), "--id", "pmid:12345", "--execute"])
        self.assertEqual(2, code)
        self.assertEqual("open-fulltext-error-v1", json.loads(stdout.getvalue())["schema"])
        fetch.assert_not_called()
        self.assertEqual(before, snapshot(self.run))
        for kind in ("symlink", "directory"):
            with self.subTest(entry=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                output = root / "fulltext"
                output.mkdir()
                (output / "keep.xml").write_bytes(b"unchanged")
                entry = output / "unsafe"
                if kind == "symlink":
                    entry.symlink_to("missing")
                else:
                    entry.mkdir()
                    (entry / "keep.txt").write_bytes(b"unchanged")
                before = snapshot(root)
                stdout = io.StringIO()
                with patch.object(open_fulltext, "_http_fetch", fetch), redirect_stdout(stdout):
                    code = cli.main(["--run-dir", temp, "--id", "pmid:12345", "--execute"])
                self.assertEqual(2, code)
                self.assertEqual("invalid_request", json.loads(stdout.getvalue())["error"]["code"])
                self.assertEqual(before, snapshot(root))
                fetch.assert_not_called()

    def test_fulltext_preparation_tolerates_only_vanished_publication_temporaries(self):
        prefix = ".fulltext-" + "0" * 32
        for name, allowed in ((None, True), (prefix + "-deadbeef.xml", True),
                              (prefix + "-deadbeef.txt", True), (prefix + "-.xml", False),
                              ("ordinary.xml", False)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                output = root / "fulltext"
                output.mkdir()
                disappearing = output / name if name is not None else None
                if disappearing is not None:
                    disappearing.write_bytes(b"partial")
                original_lstat = Path.lstat

                def lstat(path, *args, **kwargs):
                    if path == disappearing:
                        path.unlink(missing_ok=True)
                        raise FileNotFoundError("fixture concurrent replacement")
                    return original_lstat(path, *args, **kwargs)

                with patch.object(Path, "lstat", lstat):
                    if allowed:
                        prepared, ledger = open_fulltext._prepare_output_paths(root, [])
                        self.assertEqual(output, prepared)
                        self.assertEqual(output / "fetch-ledger.jsonl", ledger)
                    else:
                        with self.assertRaisesRegex(ValueError, "fulltext output path is unsafe"):
                            open_fulltext._prepare_output_paths(root, [])
                self.assertFalse((output / "fetch-ledger.jsonl").exists())

    def test_fetch_ledger_is_appended_before_later_artifact_write_failure(self):
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            if "search?" in url:
                return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":"CC BY"}]}}'
            return 200, b"<article><p>Body</p></article>"
        original = Path.write_bytes
        def fail_xml(path, data):
            if path.name.endswith(".xml"):
                raise OSError("fixture write failure")
            return original(path, data)
        with patch.object(Path, "write_bytes", fail_xml):
            result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
        self.assertEqual("write-failed", result["results"][0]["status"])
        self.assertEqual(2, len(calls))
        ledger = [json.loads(line) for line in (self.run / "fulltext/fetch-ledger.jsonl").read_text().splitlines()]
        self.assertEqual(2, len(ledger))

    def test_declared_query_ledger_is_untouched_and_fetch_ledger_is_separate(self):
        ledger_path = self.run / "records/queries.jsonl"
        ledger_path.parent.mkdir()
        original = '{"query_id":"prior","source":"fixture","query":"q","accessed_at":"now","status":"complete","response_sha256":null}\n'
        ledger_path.write_text(original)
        self._manifest([{"kind": "query-ledger", "path": "records/queries.jsonl"}])
        fetch = lambda url, **kwargs: ((200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"N"}]}}'))
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True, fetch=fetch)
        self.assertEqual(original, ledger_path.read_text())
        self.assertEqual("fulltext/fetch-ledger.jsonl", result["fetch_ledger"])
        self.assertNotIn("manifest_refresh_required", result)
        self.assertEqual(1, len((self.run / "fulltext/fetch-ledger.jsonl").read_text().splitlines()))

    def test_queries_jsonl_fallback_is_untouched(self):
        self._manifest()
        ledger_path = self.run / "queries.jsonl"
        ledger_path.write_text("")
        result = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                fetch=lambda *args, **kwargs: (200, b'{"resultList":{"result":[]}'))
        self.assertEqual("fulltext/fetch-ledger.jsonl", result["fetch_ledger"])
        self.assertEqual("", ledger_path.read_text())
        self.assertEqual(1, len((self.run / "fulltext/fetch-ledger.jsonl").read_text().splitlines()))

    def test_run_without_study_table_or_explicit_ids_has_actionable_error(self):
        self._manifest()
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_empty", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run)])
        self.assertEqual(2, code)
        message = json.loads(stdout.getvalue())["error"]["message"]
        self.assertIn("--id", message)
        self.assertIn("study table", message)

    def test_manifest_declared_study_table_is_used(self):
        custom = self.run / "records/study.json"
        custom.parent.mkdir()
        custom.write_text('{"studies":[{"doi":"10.1234/custom"}]}')
        (self.run / "studies.json").write_text('{"studies":[{"doi":"10.1234/fallback"}]}')
        (self.run / "report.md").write_text("Cites DOI:10.1234/custom and DOI:10.1234/fallback.")
        self._manifest([{"kind": "study-table", "path": "records/study.json"},
                        {"kind": "report", "path": "report.md"}])
        self.assertEqual(["doi:10.1234/custom"], identifiers_from_run(self.run))

    def test_json_study_fields_are_walked_and_only_report_citations_are_candidates(self):
        self._study_table()
        (self.run / "studies.json").write_text(
            '{"studies":[{"pmid":"12345"},{"pmid":"54321"},{"pmid":"67890","excluded":true}]}')
        (self.run / "report.md").write_text("Cites PMID:12345 and PMID:67890.")
        self._manifest([{"kind": "report", "path": "report.md"}])
        self.assertEqual(["pmid:12345"], identifiers_from_run(self.run))
        (self.run / "studies.json").write_text('{"studies":[{"doi":" 10.1234/ABC"}]}')
        (self.run / "report.md").write_text("Cites DOI:10.1234/ABC.")
        self.assertEqual(["doi:10.1234/abc"], identifiers_from_run(self.run))

    def test_many_candidates_are_truncated_to_default_with_success_exit(self):
        rows = [{"pmid": str(10000 + index)} for index in range(51)]
        (self.run / "studies.json").write_text(json.dumps({"studies": rows}))
        (self.run / "report.md").write_text(" ".join(f"PMID:{10000 + index}" for index in range(51)))
        self._manifest([{"kind": "report", "path": "report.md"}])
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_many", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run)])
        result = json.loads(stdout.getvalue())
        self.assertEqual(0, code)
        self.assertTrue(result["truncated"])
        self.assertEqual(21, result["dropped_count"])
        self.assertEqual(30, len(result["results"]))

    def test_non_oa_does_not_request_full_text(self):
        urls = []
        def fetch(url, **kwargs):
            urls.append(url)
            return 200, b'{"resultList":{"result":[{"pmcid":"PMC12345","doi":"10.1234/a","isOpenAccess":"N","license":"CC BY"}]}}'
        result = fetch_fulltext(["doi:10.1234/a"], self.run, execute=True, fetch=fetch)
        self.assertEqual("not-open-access", result["results"][0]["status"])
        self.assertEqual(1, len(urls))
        self.assertNotIn("fullTextXML", urls[0])

    def test_unknown_license_and_metadata_http_error_never_fetch_full_text(self):
        for response, expected in (
            ((200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y"}]}}'), "license-unknown"),
            ((200, b'{"resultList":{"result":[{"pmcid":"PMC12345","pmid":"12345","source":"MED","isOpenAccess":"Y","license":null}]}}'), "license-unknown"),
            ((503, b"temporarily unavailable"), "unavailable"),
        ):
            with self.subTest(expected=expected):
                urls = []
                result = fetch_fulltext(["pmid:12345"], self.run, execute=True,
                                        fetch=lambda url, **kwargs: (urls.append(url) or response))
                self.assertEqual(expected, result["results"][0]["status"])
                self.assertEqual(1, len(urls))
                self.assertNotIn("fullTextXML", urls[0])

    def test_caps_and_xml_declarations(self):
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            if "search?" in url:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                pmid = query.split(":", 1)[1].split()[0]
                return 200, json.dumps({"resultList": {"result": [{"pmcid": "PMC" + pmid, "pmid": pmid,
                    "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}).encode()
            return 200, b'<!DOCTYPE article><article/>'
        result = fetch_fulltext([f"pmid:{10000+i}" for i in range(12)], self.run,
                                execute=True, fetch=fetch, max_fetches=10)
        self.assertEqual("unavailable", result["results"][0]["status"])
        self.assertTrue(all(item["status"] == "unavailable" for item in result["results"][:10]))
        self.assertTrue(all(item["status"] == "skipped-cap" for item in result["results"][10:]))
        self.assertEqual(20, len(calls))
        hidden = '<!DOCTYPE a [<!ENTITY e "boom">]><a>&e;</a>'.encode("utf-16")
        with self.assertRaisesRegex(ValueError, "declarations"):
            open_fulltext._plain_text(hidden)

    def test_elapsed_wall_cap_marks_remaining_skipped(self):
        for xml, expected in ((b"<article><p>Text</p></article>", "fetched"),
                              (b"<article/>", "unavailable")):
            with self.subTest(xml=xml):
                times = iter([0, 0, 0, 0, 2])
                calls = []
                def fetch(url, **kwargs):
                    calls.append(url)
                    if "search?" in url:
                        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                        pmid = query.split(":", 1)[1].split()[0]
                        return 200, json.dumps({"resultList": {"result": [{"pmcid": "PMC12345", "pmid": pmid,
                            "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}).encode()
                    return 200, xml
                result = fetch_fulltext(["pmid:12345", "pmid:12346"], self.run, execute=True,
                                        fetch=fetch, max_seconds=1, clock=lambda: next(times))
                self.assertEqual([expected, "skipped-cap"], [item["status"] for item in result["results"]])
                if expected == "unavailable":
                    self.assertEqual("xml-parse-error", result["results"][0]["reason"])
                self.assertEqual(2, len(calls))

    def test_exactly_ten_fetches_without_remaining_candidate_does_not_report_cap_reached(self):
        def fetch(url, **kwargs):
            if "search?" in url:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                pmid = query.split(":", 1)[1].split()[0]
                return 200, json.dumps({"resultList": {"result": [{"pmcid": "PMC" + pmid, "pmid": pmid,
                    "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}).encode()
            return 200, b"<article><p>text</p></article>"
        result = fetch_fulltext([f"pmid:{10000+i}" for i in range(10)], self.run,
                                execute=True, fetch=fetch, max_fetches=10)
        self.assertEqual(10, sum(item["status"] == "fetched" for item in result["results"]))
        self.assertFalse(result["cap_reached"])

    def test_multiple_identifiers_for_one_pmcid_fetch_once(self):
        record = {"pmcid": "PMC12345", "doi": "10.1234/article", "pmid": "12345",
                  "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}
        fulltext_calls = []
        def fetch(url, **kwargs):
            if "search?" in url:
                return 200, json.dumps({"resultList": {"result": [record]}}).encode()
            fulltext_calls.append(url)
            return 200, b"<article><p>text</p></article>"
        result = fetch_fulltext(["doi:10.1234/article", "pmid:12345", "pmcid:PMC12345"], self.run,
                                execute=True, fetch=fetch)
        self.assertEqual(1, len(fulltext_calls))
        self.assertEqual(1, sum(item["status"] == "fetched" for item in result["results"]))
        self.assertEqual(2, sum(item["status"] == "duplicate-of:PMC12345" for item in result["results"]))

    def test_executed_retrieval_does_not_trace_an_orphan_citation(self):
        (self.run / "studies.json").write_text('{"studies":[]}')
        (self.run / "report.md").write_text("Cites PMCID:PMC7654321.")
        (self.run / "queries.jsonl").write_text("")
        self._manifest([{"kind": "study-table", "path": "studies.json"},
                        {"kind": "query-ledger", "path": "queries.jsonl"},
                        {"kind": "report", "path": "report.md"}])
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_orphan", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        record = {"pmcid": "PMC7654321", "isOpenAccess": "N", "license": "CC BY"}
        with patch.object(open_fulltext, "_http_fetch",
                          lambda url, **kwargs: (200, json.dumps({"resultList": {"result": [record]}}).encode())):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = cli.main(["--run-dir", str(self.run), "--id", "pmcid:PMC7654321", "--execute"])
        self.assertEqual(0, code)
        self.assertEqual(["pmcid:PMC7654321"], [row["identifier"] for row in trace_citations(self.run)["orphans"]])
        self.assertEqual("", (self.run / "queries.jsonl").read_text())
        fetch_rows = [json.loads(line) for line in (self.run / "fulltext/fetch-ledger.jsonl").read_text().splitlines()]
        for field in ("pmcid", "pmid", "doi", "persistent_id", "persistent_ids", "arxiv",
                      "returned_record_ids", "included_records"):
            self.assertNotIn(field, fetch_rows[0])

    def test_id_only_plan_ignores_malformed_cwd_manifest(self):
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        (self.run / "manifest.json").write_text("not-json")
        result = __import__("subprocess").run(["python3", str(script), "--id", "pmid:12345"],
                                              cwd=self.run, capture_output=True, text=True)
        self.assertEqual(0, result.returncode)
        self.assertEqual("planned", json.loads(result.stdout)["results"][0]["status"])

    def test_redirect_host_is_restricted(self):
        request = urllib.request.Request("https://www.ebi.ac.uk/europepmc/webservices/rest/search")
        with self.assertRaisesRegex(ValueError, "redirect"):
            _EuropePMCRedirectHandler().redirect_request(request, None, 302, "Found", {}, "https://example.org/x")

    def test_plan_mode_makes_no_fetch_calls(self):
        fetch = Mock()
        result = fetch_fulltext(["pmcid:PMC12345"], self.run, fetch=fetch)
        fetch.assert_not_called()
        self.assertEqual("planned", result["results"][0]["status"])

    def test_bad_run_directory_is_json_exit_two(self):
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        result = __import__("subprocess").run(["python3", str(script), "--run-dir", str(self.run)],
                                              capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertEqual("open-fulltext-error-v1", json.loads(result.stdout)["schema"])


if __name__ == "__main__":
    unittest.main()
