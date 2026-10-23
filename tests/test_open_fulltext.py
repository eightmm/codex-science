from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from contextlib import redirect_stdout
import urllib.parse
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch
from unittest.mock import Mock

import codex_science.open_fulltext as open_fulltext
from codex_science.open_fulltext import _EuropePMCRedirectHandler, fetch_fulltext, identifiers_from_run
from codex_science.citation_trace import trace_citations
from codex_science.evidence import _validate_query_records


class OpenFulltextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _manifest(self, artifacts=None):
        (self.run / "manifest.json").write_text(json.dumps({"artifacts": artifacts or []}))

    def _study_table(self):
        (self.run / "studies.json").write_text('{"studies":[{"pmid":"12345"}]}')

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
        stdout = io.StringIO()
        with patch.object(open_fulltext, "_http_fetch", fetch), redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run), "--id", "pmid:12345", "--execute"])
        self.assertEqual(2, code)
        self.assertEqual("open-fulltext-error-v1", json.loads(stdout.getvalue())["schema"])
        fetch.assert_not_called()

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

    def test_run_without_study_table_has_zero_candidates_and_succeeds(self):
        self._manifest()
        script = Path(__file__).resolve().parents[1] / "scripts/fetch_open_fulltext.py"
        spec = importlib.util.spec_from_file_location("fetch_open_fulltext_cli_empty", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main(["--run-dir", str(self.run)])
        self.assertEqual(0, code)
        self.assertEqual([], json.loads(stdout.getvalue())["results"])

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
        times = iter([0, 0, 0, 0, 2])
        calls = []
        def fetch(url, **kwargs):
            calls.append(url)
            if "search?" in url:
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
                pmid = query.split(":", 1)[1].split()[0]
                return 200, json.dumps({"resultList": {"result": [{"pmcid": "PMC12345", "pmid": pmid,
                    "source": "MED", "isOpenAccess": "Y", "license": "CC BY"}]}}).encode()
            return 200, b"<article/>"
        result = fetch_fulltext(["pmid:12345", "pmid:12346"], self.run, execute=True,
                                fetch=fetch, max_seconds=1, clock=lambda: next(times))
        self.assertEqual(["fetched", "skipped-cap"], [item["status"] for item in result["results"]])
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
