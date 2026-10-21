import json
import http.client
import importlib.util
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from codex_science.citation_resolve import (EVIDENCE_BOUNDARY, normalize_identifiers, resolve_identifiers,
                                            supported_identifiers_from_text)


class CitationResolveTests(unittest.TestCase):
    def test_statuses_and_metadata(self):
        replies = [
            (200, json.dumps({"message": {"title": ["A paper"], "published-print": {"date-parts": [[2020]]}}})),
            (404, "{}"), (503, "{}"), (200, "not json"),
        ]
        def fetch(url, *, timeout):
            status, body = replies.pop(0)
            if isinstance(body, str):
                body = body.encode()
            return status, body
        got = resolve_identifiers(["doi:10.1234/example", "doi:10.1234/missing", "doi:10.1234/down", "doi:10.1234/bad"], fetch=fetch, delay=lambda _: None)
        self.assertEqual([r["status"] for r in got["results"]], ["resolved", "not_found", "unavailable", "unavailable"])
        self.assertEqual(got["results"][0]["title"], "A paper")
        self.assertEqual(got["results"][0]["year"], 2020)
        self.assertEqual(got["evidence_boundary"], EVIDENCE_BOUNDARY)

    def test_cap_and_determinism(self):
        fetch = lambda *a, **k: (404, b"{}")
        first = resolve_identifiers(["doi:10.1234/z", "doi:10.1234/a"], fetch=fetch, delay=lambda _: None)
        second = resolve_identifiers(["doi:10.1234/a", "doi:10.1234/z"], fetch=fetch, delay=lambda _: None)
        self.assertEqual(first, second)
        with self.assertRaises(ValueError):
            resolve_identifiers([f"doi:10.1234/{i}" for i in range(51)], fetch=lambda *a, **k: None)

    def test_identifier_patterns_refuse_malformed_ids_before_fetch(self):
        fetch = Mock()
        for identifier in ("pmid:abc", "doi:FOO", "arxiv:../x", "arxiv:a..b/1234567",
                           "arxiv:math./0309136"):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "malformed"):
                resolve_identifiers([identifier], fetch=fetch)
        fetch.assert_not_called()
        self.assertEqual(["doi:10.1234/foo"], normalize_identifiers(["DOI:10.1234/FOO", "doi:10.1234/foo"]))

    def test_old_style_arxiv_identifier_is_supported(self):
        identifier = "arxiv:hep-th/9901001"
        self.assertEqual([identifier], normalize_identifiers([identifier]))
        self.assertEqual(([identifier], []), supported_identifiers_from_text("arXiv:hep-th/9901001"))

    def test_dotted_old_style_arxiv_text_uses_canonical_api_id(self):
        identifiers, skipped = supported_identifiers_from_text("Cites arXiv:math.GT/0309136.")
        self.assertEqual(["arxiv:math/0309136"], identifiers)
        self.assertEqual([], skipped)
        requested = []
        feed = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                b'<title>Regular points in affine Springer fibers</title>'
                b'<published>2003-09-17T00:00:00Z</published>'
                b'</entry></feed>')
        result = resolve_identifiers(
            identifiers,
            fetch=lambda url, **kwargs: (requested.append(url) or (200, feed)),
            delay=lambda _: None,
        )
        self.assertEqual("resolved", result["results"][0]["status"])
        self.assertEqual("arxiv:math/0309136", result["results"][0]["identifier"])
        self.assertEqual(1, len(requested))
        self.assertIn("id_list=math%2F0309136", requested[0])

    def test_labelled_scan_reports_malformed_without_adding_lookups(self):
        identifiers, skipped = supported_identifiers_from_text("(doi:10.1234/foo). PMID: 1234")
        self.assertEqual(["doi:10.1234/foo"], identifiers)
        self.assertEqual([{"identifier": "pmid:1234", "reason": "malformed"}], skipped)
        fetched = []
        resolve_identifiers(identifiers, fetch=lambda url, **kwargs: (fetched.append(url) or (404, b"{}")),
                            delay=lambda _: None)
        self.assertEqual(1, len(fetched))

    def test_labelled_scan_uses_identifier_span_overlap_and_keeps_only_malformed(self):
        for text, identifiers in (
            ("DOI: https://doi.org/10.1038/nature12373", ["doi:10.1038/nature12373"]),
            ("arXiv: arXiv:2101.00001", ["arxiv:2101.00001"]),
        ):
            with self.subTest(text=text):
                got_ids, skipped = supported_identifiers_from_text(text)
                self.assertEqual(identifiers, got_ids)
                self.assertEqual([], skipped)
        self.assertEqual(([], [{"identifier": "doi:garbage", "reason": "malformed"}]),
                         supported_identifiers_from_text("doi:garbage"))

    def test_skipped_identifiers_deduplicate_case_insensitively_in_first_order(self):
        _, skipped = supported_identifiers_from_text("PMID: AbC pmid: abc")
        self.assertEqual([{"identifier": "pmid:AbC", "reason": "malformed"}], skipped)

    def test_text_input_skips_malformed_and_over_cap_in_sorted_order(self):
        text = " ".join([f"doi:10.1234/{i:02}" for i in reversed(range(52))] +
                        ["pmid:abc", "arxiv:../x"])
        identifiers, skipped = supported_identifiers_from_text(text)
        self.assertEqual([f"doi:10.1234/{i:02}" for i in range(50)], identifiers)
        self.assertEqual({"over_cap", "malformed"}, {item["reason"] for item in skipped})
        over_cap = [item["identifier"] for item in skipped if item["reason"] == "over_cap"]
        self.assertEqual(["doi:10.1234/50", "doi:10.1234/51"], over_cap)

    def test_crossref_malformed_optional_date_still_resolves_without_year(self):
        for key in ("published-print", "issued"):
            result = resolve_identifiers(["doi:10.1234/example"], fetch=lambda *a, **k: (
                200, json.dumps({"message": {key: "not a date"}}).encode()), delay=lambda _: None)["results"][0]
            self.assertEqual("resolved", result["status"])
            self.assertNotIn("year", result)

    def test_oversized_http_body_is_unavailable(self):
        from codex_science import citation_resolve
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b"x" * size
        with unittest.mock.patch.object(citation_resolve.urllib.request, "urlopen", return_value=Response()):
            self.assertEqual("unavailable", resolve_identifiers(["doi:10.1234/example"])["results"][0]["status"])

    def test_recorded_fixture_shape(self):
        fixture = Path(__file__).parent / "fixtures/citation_resolve/doi_10.1234_example.json"
        payload = json.loads(fixture.read_text())
        got = resolve_identifiers(["doi:10.1234/example"], fetch=lambda *a, **k: (payload["http_status"], json.dumps(payload["body"]).encode()), delay=lambda _: None)
        self.assertEqual(got["results"][0]["title"], "Fixture paper")
        self.assertEqual(got["results"][0]["year"], 2021)

    def test_cli_plan_without_network(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        result = subprocess.run([sys.executable, str(script), "--ids", "DOI:10.1234/EXAMPLE", "https://doi.org/10.1234/example"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["plan"]["network"])
        self.assertEqual(payload["plan"]["identifiers"], ["doi:10.1234/example"])
        self.assertIn("evidence_boundary", payload)

    def test_pubmed_error_and_uid_absence_are_not_found(self):
        payload = {"result": {
            "uids": ["12345"],
            "12345": {"uid": "12345", "error": "not found"},
            "23456": {"uid": "23456", "title": "Should not resolve", "pubdate": "2022 Jan"},
        }}
        got = resolve_identifiers(["pmid:12345", "pmid:23456"],
                                  fetch=lambda *a, **k: (200, json.dumps(payload).encode()), delay=lambda _: None)
        self.assertEqual([entry["status"] for entry in got["results"]], ["not_found", "not_found"])

    def test_pubmed_resolves_only_uid_in_uids_without_error(self):
        payload = {"result": {"uids": ["12345"], "12345": {"uid": "12345", "title": "Present", "pubdate": "2022 Jan"}}}
        got = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (200, json.dumps(payload).encode()), delay=lambda _: None)
        self.assertEqual(got["results"][0]["status"], "resolved")

    def test_transport_xml_and_arxiv_not_found_cases(self):
        def interrupted(*args, **kwargs):
            raise http.client.IncompleteRead(b"partial", 10)
        timeout = resolve_identifiers(["doi:10.1234/timeout"], fetch=lambda *a, **k: (_ for _ in ()).throw(TimeoutError()), delay=lambda _: None)
        interrupted_result = resolve_identifiers(["doi:10.1234/interrupted"], fetch=interrupted, delay=lambda _: None)
        malformed = resolve_identifiers(["arxiv:2301.12345"], fetch=lambda *a, **k: (200, b"<bad"), delay=lambda _: None)
        empty_feed = resolve_identifiers(["arxiv:2301.12345"], fetch=lambda *a, **k: (200, b'<feed xmlns="http://www.w3.org/2005/Atom"/>'), delay=lambda _: None)
        error_feed = resolve_identifiers(["arxiv:2301.12345"], fetch=lambda *a, **k: (200, b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Error</title></entry></feed>'), delay=lambda _: None)
        self.assertEqual(timeout["results"][0]["status"], "unavailable")
        self.assertEqual(interrupted_result["results"][0]["status"], "unavailable")
        self.assertEqual(malformed["results"][0]["status"], "unavailable")
        self.assertEqual(empty_feed["results"][0]["status"], "not_found")
        self.assertEqual(error_feed["results"][0]["status"], "not_found")

    def test_crossref_empty_optional_fields_still_resolve(self):
        payload = {"message": {"title": [], "published-print": {"date-parts": []}}}
        result = resolve_identifiers(["doi:10.1234/no-metadata"], fetch=lambda *a, **k: (200, json.dumps(payload).encode()), delay=lambda _: None)["results"][0]
        self.assertEqual(result["status"], "resolved")
        self.assertNotIn("title", result)
        self.assertNotIn("year", result)

    def test_unsupported_explicit_ids_fail_before_fetch_and_input_skips(self):
        fetch = Mock()
        with self.assertRaisesRegex(ValueError, "unsupported identifier kind"):
            resolve_identifiers(["pmcid:PMC123456"], fetch=fetch, delay=lambda _: None)
        fetch.assert_not_called()
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        spec = importlib.util.spec_from_file_location("resolve_citations_cli", script)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        request = Mock()
        cli.resolve_identifiers = request
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main(["--ids", "pmcid:PMC123456", "--network"])
        self.assertEqual(exit_code, 2)
        self.assertEqual(json.loads(stdout.getvalue())["error"]["code"], "invalid_request")
        request.assert_not_called()
        result = subprocess.run([sys.executable, str(script), "--input", "-"], input="PMCID PMC123456", capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["skipped_identifiers"], [{"identifier": "pmcid:PMC123456", "reason": "unsupported_kind"}])

    def test_network_and_plan_share_normalization_and_delay_is_injected(self):
        aliases = ["DOI:10.1234/EXAMPLE", "https://doi.org/10.1234/example"]
        normalized = normalize_identifiers(aliases)
        self.assertEqual(normalized, ["doi:10.1234/example"])
        alias_calls = []
        alias_result = resolve_identifiers(aliases, fetch=lambda url, **kwargs: (alias_calls.append(url) or (404, b"{}")), delay=lambda _: None)
        self.assertEqual(len(alias_result["results"]), 1)
        self.assertEqual(len(alias_calls), 1)
        delays = []
        calls = []
        def fetch(url, *, timeout):
            calls.append((url, timeout))
            return 404, b"{}"
        result = resolve_identifiers(["doi:10.1234/first", "doi:10.1234/second"], fetch=fetch, delay=delays.append)
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(delays, [0.1])
        self.assertEqual([timeout for _, timeout in calls], [10.0, 10.0])

    def test_cli_rejects_both_input_modes_with_invalid_request(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/example", "--input", "-"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["error"]["code"], "invalid_request")
        self.assertIn("evidence_boundary", payload)


if __name__ == "__main__":
    unittest.main()
