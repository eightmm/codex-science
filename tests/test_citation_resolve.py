import json
import http.client
import importlib.util
import subprocess
import sys
import tempfile
import urllib.request
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import Mock

from codex_science.citation_resolve import (EVIDENCE_BOUNDARY, normalize_identifiers, resolve_identifiers,
                                            supported_identifiers_from_text)
from codex_science.citation_resolve import _CitationRedirectHandler, _normalized_text


class CitationResolveTests(unittest.TestCase):
    def test_cli_offline_arxiv_fixture_preserves_xml_body(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = Path(tmp)
            fixture = fixtures / "arxiv_2401.00001.json"
            feed = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                    '<id>https://arxiv.org/abs/2401.00001</id><title>Paper</title></entry></feed>')
            for body, status in ((feed, "resolved"), ("", "unavailable"), ("<bad", "unavailable")):
                with self.subTest(body=body):
                    fixture.write_text(json.dumps({"http_status": 200, "body": body}), encoding="utf-8")
                    result = subprocess.run([sys.executable, str(script), "--ids", "arxiv:2401.00001",
                                             "--offline-fixture", str(fixtures)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stderr)
                    record = json.loads(result.stdout)["results"][0]
                    self.assertEqual(status, record["status"])
                    if status == "resolved":
                        self.assertEqual("Paper", record["title"])

    def test_arxiv_requires_atom_feed_before_establishing_absence(self):
        for body, status in (
            (b"<error>Service down</error>", "unavailable"),
            (b"<html><body>Service down</body></html>", "unavailable"),
            (b"<feed/>", "unavailable"),
            (b'<feed xmlns="urn:other"/>', "unavailable"),
            (b"", "unavailable"), (b"<bad", "unavailable"),
            (b'<feed xmlns="http://www.w3.org/2005/Atom"/>', "not_found"),
        ):
            with self.subTest(body=body):
                record = resolve_identifiers(["arxiv:2401.00001"],
                    fetch=lambda *a, **k: (200, body), delay=lambda _: None)["results"][0]
                self.assertEqual(status, record["status"])

    def test_pubmed_rejects_contradictory_record_uid(self):
        for uid in ("54321", "", None, 0, [], {}):
            with self.subTest(uid=uid):
                payload = {"result": {"uids": ["12345"], "12345": {
                    "uid": uid, "title": "Other paper", "pubdate": "2020 Jan"}}}
                record = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (
                    200, json.dumps(payload).encode()), delay=lambda _: None)["results"][0]
                self.assertEqual("unavailable", record["status"])
                self.assertNotIn("title", record)
        for identity in ({}, {"uid": "12345"}, {"uid": 12345}):
            with self.subTest(identity=identity):
                payload = {"result": {"uids": ["12345"], "12345": {
                    **identity, "title": "Paper", "pubdate": "2020 Jan"}}}
                record = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (
                    200, json.dumps(payload).encode()), delay=lambda _: None)["results"][0]
                self.assertEqual("resolved", record["status"])

    def test_response_identity_must_match_requested_identifier(self):
        for returned, status in (("10.1234/other", "unavailable"), ("10.1234/EXPECTED", "resolved"),
                                 ("", "unavailable"), (None, "unavailable"), (0, "unavailable")):
            with self.subTest(doi=returned):
                result = resolve_identifiers(["doi:10.1234/expected"], fetch=lambda *a, **k: (
                    200, json.dumps({"message": {"DOI": returned, "title": ["Other work"]}}).encode()))["results"][0]
                self.assertEqual(status, result["status"])
                if status == "unavailable":
                    self.assertNotIn("title", result)
        for returned, status in (("2401.00002", "unavailable"), ("2401.00001v2", "resolved"),
                                 ("", "unavailable"), ("garbage", "unavailable")):
            with self.subTest(arxiv=returned):
                feed = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                        f'<id>https://arxiv.org/abs/{returned}</id><title>Paper</title></entry></feed>')
                result = resolve_identifiers(["arxiv:2401.00001v1"], fetch=lambda *a, **k: (200, feed.encode()))["results"][0]
                self.assertEqual(status, result["status"])

    def test_cli_offline_fixture_identity_prevents_colliding_names(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        with tempfile.TemporaryDirectory() as tmp:
            fixtures = Path(tmp)
            (fixtures / "doi_10.1234_a_b.json").write_text(json.dumps({"http_status": 200,
                "body": {"message": {"DOI": "10.1234/a/b", "title": ["Paper"]}}}))
            result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/a/b", "doi:10.1234/a_b",
                                     "--offline-fixture", str(fixtures)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            rows = {r["identifier"]: r for r in json.loads(result.stdout)["results"]}
            self.assertEqual("resolved", rows["doi:10.1234/a/b"]["status"])
            self.assertEqual("unavailable", rows["doi:10.1234/a_b"]["status"])
            (fixtures / "doi_10.1234_a_b.json").write_text(json.dumps({"http_status": 200,
                "body": {"message": {"title": ["Unidentified paper"]}}}))
            result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/a_b",
                                     "--offline-fixture", str(fixtures)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("unavailable", json.loads(result.stdout)["results"][0]["status"])

            for body, status in (
                (json.dumps({"message": {"DOI": "10.1234/a_b", "title": ["Paper"]}}), "resolved"),
                (json.dumps({"message": {"DOI": "10.1234/a/b", "title": ["Other paper"]}}), "unavailable"),
                (json.dumps({"message": {"title": ["Unidentified paper"]}}), "unavailable"),
                (json.dumps({"message": {}}), "unavailable"),
                (json.dumps({"message": 0}), "unavailable"),
                (json.dumps({"message": []}), "unavailable"),
                ("{}", "unavailable"), ("0", "unavailable"), ("[]", "unavailable"),
                ("null", "unavailable"), ("", "unavailable"), ("{bad", "unavailable"),
                ("<error>Service down</error>", "unavailable"),
            ):
                with self.subTest(body=body):
                    (fixtures / "doi_10.1234_a_b.json").write_text(
                        json.dumps({"http_status": 200, "body": body}), encoding="utf-8")
                    result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/a_b",
                                             "--offline-fixture", str(fixtures)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    record = json.loads(result.stdout)["results"][0]
                    self.assertEqual(status, record["status"])
                    if status == "resolved":
                        self.assertEqual("Paper", record["title"])
                    else:
                        self.assertNotIn("title", record)

    def test_duplicate_expected_metadata_is_order_independent(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest.json").write_text(json.dumps({"artifacts": []}))
            (root / "doi_10.1234_a.json").write_text(json.dumps({"http_status": 200, "body": {"message": {
                "DOI": "10.1234/a", "title": ["Correct record"], "issued": {"date-parts": [[2020]]}}}}))
            correct = {"persistent_id": "doi:10.1234/a", "title": "Correct record", "year": 2020}
            wrong = {"persistent_id": "DOI:10.1234/A", "title": "Completely unrelated incorrect study", "year": 1990}
            cases = (([wrong, correct], "mismatch"), ([correct, wrong], "mismatch"),
                     ([correct, correct], "match"), ([correct], "match"), ([], "unverified"),
                     ([correct, {"persistent_id": "doi:10.1234/a", "year": "2020"}], "match"))
            for rows, expected in cases:
                with self.subTest(rows=rows):
                    (root / "studies.json").write_text(json.dumps({"studies": rows}))
                    result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/a",
                        "--offline-fixture", str(root), "--run-dir", str(root)], capture_output=True, text=True)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertEqual(expected, json.loads(result.stdout)["results"][0]["metadata_check"])
                    self.assertIn(f"metadata mismatches: {int(expected == 'mismatch')}", result.stderr)

    def test_redirect_handler_allows_https_lookup_host(self):
        request = urllib.request.Request("https://api.crossref.org/works/10.1234/example")
        redirected = _CitationRedirectHandler().redirect_request(
            request, None, 302, "Found", {}, "https://api.crossref.org/works/10.1234/other"
        )
        self.assertEqual(redirected.full_url, "https://api.crossref.org/works/10.1234/other")

    def test_redirect_handler_refuses_downgrade_and_unlisted_host(self):
        request = urllib.request.Request("https://api.crossref.org/works/10.1234/example")
        handler = _CitationRedirectHandler()
        for target in ("http://api.crossref.org/works/10.1234/other",
                       "https://example.com/works/10.1234/other"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "redirect"):
                handler.redirect_request(request, None, 302, "Found", {}, target)

    def test_arxiv_xml_declarations_are_unavailable(self):
        for declaration in ("<!DOCTYPE feed><feed/>", "<!ENTITY x 'y'><feed/>",
                            "<!doctype feed><feed/>", "<!entity x 'y'><feed/>"):
            with self.subTest(declaration=declaration):
                result = resolve_identifiers(
                    ["arxiv:2301.12345"],
                    fetch=lambda *args, **kwargs: (200, declaration.encode()),
                    delay=lambda _: None,
                )["results"][0]
                self.assertEqual("unavailable", result["status"])

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

        def checked(body, expected):
            return resolve_identifiers(
                ["doi:10.1234/example"],
                fetch=lambda *a, **k: (200, json.dumps({"message": body}).encode()),
                delay=lambda _: None,
                expected_metadata={"doi:10.1234/example": expected},
            )["results"][0]

        record = {"title": ["An unrelated clinical trial"], "issued": {"date-parts": [[2020]]}}
        self.assertEqual("mismatch", checked(record, {"title": "A paper", "year": 2020})["metadata_check"])
        record = {"title": ["Café: A STUDY!"], "issued": {"date-parts": [[2021]]}}
        self.assertEqual("match", checked(record, {"title": "Cafe a study", "year": 2020})["metadata_check"])
        self.assertEqual("match", checked(record, {"title": "Cafe a study", "year": "2021"})["metadata_check"])
        with_author = {**record, "author": [{"family": "Van der Meer"}]}
        author_result = checked(with_author, {"title": "Cafe a study", "first_author": "Van der Meer"})
        self.assertEqual("Van der Meer", author_result["first_author"])
        self.assertEqual("match", author_result["metadata_check"])
        non_latin = checked({"title": ["中文题目"]}, {"title": "中文题目"})
        self.assertIn(non_latin["metadata_check"], {"uncertain", "unverified"})
        group_author = checked({**record, "author": [{"family": "World Health Organization"}]},
                               {"title": "Cafe a study", "first_author": "World Health Organization"})
        self.assertEqual("uncertain", group_author["metadata_check"])
        self.assertEqual("unverified", resolve_identifiers(
            ["doi:10.1234/example"], fetch=lambda *a, **k: (200, json.dumps({"message": record}).encode()),
            delay=lambda _: None)["results"][0]["metadata_check"])
        self.assertEqual("uncertain", resolve_identifiers(
            ["doi:10.1234/example"], fetch=lambda *a, **k: (200, json.dumps({"message": record}).encode()),
            delay=lambda _: None, expected_metadata={"doi:10.1234/example": {"title": "Cafe a study", "year": "2020a"}})["results"][0]["metadata_check"])
        self.assertEqual("unverified", resolve_identifiers(
            ["doi:10.1234/example"], fetch=lambda *a, **k: (503, b""), delay=lambda _: None,
            expected_metadata={"doi:10.1234/example": {"title": "Cafe a study"}})["results"][0]["metadata_check"])

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

    def test_spaced_labels_preserve_valid_identifiers_and_cap(self):
        for text, expected in (
            ("", []), ("PMID : 12345", ["pmid:12345"]),
            ("arXiv : 2401.00001", ["arxiv:2401.00001"]),
            ("DOI : 10.1234/example", ["doi:10.1234/example"]),
            ("PMID : 12345 PMID:12345 pmid : 12345.", ["pmid:12345"]),
        ):
            with self.subTest(text=text):
                self.assertEqual((expected, []), supported_identifiers_from_text(text))
        for count in (0, 1, 50, 51):
            with self.subTest(count=count):
                ids = [f"pmid:{10000 + index}" for index in range(count)]
                text = " ".join(f"PMID : {identifier.split(':')[1]}" for identifier in reversed(ids))
                expected_skipped = [{"identifier": identifier, "reason": "over_cap"} for identifier in ids[50:]]
                self.assertEqual((ids[:50], expected_skipped), supported_identifiers_from_text(text))
        self.assertEqual(([], [{"identifier": "pmid:0", "reason": "malformed"},
                               {"identifier": "pmid:abc", "reason": "malformed"}]),
                         supported_identifiers_from_text("PMID : 0 PMID : abc"))

    def test_cli_plan_includes_spaced_labels(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        result = subprocess.run([sys.executable, str(script), "--input", "-"],
                                input="PMID : 12345 arXiv : 2401.00001", capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(["arxiv:2401.00001", "pmid:12345"], payload["plan"]["identifiers"])
        self.assertEqual([], payload["skipped_identifiers"])

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
        class Opener:
            def open(self, request, *, timeout): return Response()
        with unittest.mock.patch.object(citation_resolve.urllib.request, "build_opener", return_value=Opener()):
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

    def test_cli_run_dir_uses_study_table_first_author_and_rejects_malformed_files(self):
        script = Path(__file__).resolve().parents[1] / "scripts/resolve_citations.py"
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            run_dir, fixtures = root / "run", root / "fixtures"
            run_dir.mkdir()
            fixtures.mkdir()
            (run_dir / "manifest.json").write_text(json.dumps({"artifacts": [
                {"kind": "study-table", "path": "studies.json"},
                {"kind": "study-table", "path": "alternate.json"},
            ]}))
            (run_dir / "studies.json").write_text(json.dumps({"studies": [{
                "persistent_id": "doi:10.1234/example", "title": "Fixture paper", "year": 2021,
                "first_author": "Jones",
            }]}))
            (run_dir / "alternate.json").write_text(json.dumps({"studies": [{
                "persistent_id": "doi:10.1234/example", "title": "Fixture article", "year": 2021,
                "first_author": "Smith",
            }]}))
            (fixtures / "doi_10.1234_example.json").write_text(json.dumps({"http_status": 200, "body": {"message": {
                "title": ["Fixture article"], "issued": {"date-parts": [[2021]]}, "author": [{"family": "Smith"}],
            }}}))
            result = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/example",
                                     "--offline-fixture", str(fixtures), "--run-dir", str(run_dir)], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("mismatch", json.loads(result.stdout)["results"][0]["metadata_check"])
            self.assertIn("metadata mismatches: 1", result.stderr)
            without_run_dir = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/example",
                                              "--offline-fixture", str(fixtures)], capture_output=True, text=True)
            self.assertEqual(0, without_run_dir.returncode, without_run_dir.stdout + without_run_dir.stderr)
            self.assertEqual("", without_run_dir.stderr)
            study = {"studies": [{"persistent_id": "doi:10.1234/example", "title": "Unrelated work",
                                  "year": 2021, "first_author": "Smith"}]}
            (run_dir / "studies.json").write_text(json.dumps(study))
            mismatch = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/example",
                                       "--offline-fixture", str(fixtures), "--run-dir", str(run_dir)],
                                      capture_output=True, text=True)
            self.assertEqual(0, mismatch.returncode, mismatch.stdout + mismatch.stderr)
            self.assertEqual("mismatch", json.loads(mismatch.stdout)["results"][0]["metadata_check"])
            self.assertIn("metadata mismatches: 1", mismatch.stderr)

            malformed = [
                ([], {"studies": []}),
                ({"artifacts": "bad"}, {"studies": []}),
                ({"artifacts": []}, []),
                ({"artifacts": []}, {"studies": "bad"}),
                ({"artifacts": []}, {"studies": ["bad"]}),
            ]
            for index, (manifest, table) in enumerate(malformed):
                with self.subTest(case=index):
                    case_dir = root / f"bad-{index}"
                    case_dir.mkdir()
                    (case_dir / "manifest.json").write_text(json.dumps(manifest))
                    (case_dir / "studies.json").write_text(json.dumps(table))
                    failed = subprocess.run([sys.executable, str(script), "--ids", "doi:10.1234/example",
                                             "--run-dir", str(case_dir)], capture_output=True, text=True)
                    self.assertEqual(2, failed.returncode)
                    self.assertEqual("citation-resolution-error-v1", json.loads(failed.stdout)["schema"])
                    self.assertNotIn("Traceback", failed.stderr)

    def test_pubmed_error_and_uid_absence_are_not_found(self):
        payload = {"result": {
            "uids": ["12345"],
            "12345": {"uid": "12345", "error": "not found"},
            "23456": {"uid": "23456", "title": "Should not resolve", "pubdate": "2022 Jan"},
        }}
        got = resolve_identifiers(["pmid:12345", "pmid:23456"],
                                  fetch=lambda *a, **k: (200, json.dumps(payload).encode()), delay=lambda _: None)
        self.assertEqual([entry["status"] for entry in got["results"]], ["not_found", "not_found"])

    def test_pubmed_malformed_responses_do_not_establish_absence(self):
        for payload in (
            {}, {"result": {}}, {"result": []}, {"result": None}, {"result": 0},
            *({"result": {"uids": uids}} for uids in (None, "12345", {}, 0, [None], [True], [0], ["0"], [""], [-1], [1.5], ["１２３４５"], ["bad"])),
            {"result": {"uids": ["12345"]}},
            *({"result": {"uids": ["12345"], "12345": item}} for item in ([], "", None, 0)),
            {"error": "service down", "result": {"uids": []}},
            {"result": {"error": "service down", "uids": []}},
        ):
            with self.subTest(payload=payload):
                record = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (
                    200, json.dumps(payload)), delay=lambda _: None)["results"][0]
                self.assertEqual("unavailable", record["status"])
                self.assertNotIn("title", record)
        for uids in ([], ["23456"], [23456]):
            with self.subTest(absent_from=uids):
                record = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (
                    200, json.dumps({"result": {"uids": uids}})), delay=lambda _: None)["results"][0]
                self.assertEqual("not_found", record["status"])

    def test_title_comparison_preserves_unicode_without_digit_only_matches(self):
        self.assertEqual("2024年癌症治疗", _normalized_text("2024年癌症治疗"))
        for actual, expected in (
            ("2024年癌症治疗", "2024年气候变化"), ("2024", "2024"),
            ("2024", "X2024"), ("X2024", "2024"),
            ("0", "0"), ("!!!", "!!!"), ("", ""),
        ):
            with self.subTest(actual=actual, expected=expected):
                record = resolve_identifiers(["doi:10.1234/example"], fetch=lambda *a, **k: (
                    200, json.dumps({"message": {"title": [actual]}})), delay=lambda _: None,
                    expected_metadata={"doi:10.1234/example": {"title": expected}})["results"][0]
                self.assertNotEqual("match", record["metadata_check"])

    def test_pubmed_resolves_only_uid_in_uids_without_error(self):
        payload = {"result": {"uids": ["12345"], "12345": {"uid": "12345", "title": "A present study", "pubdate": "2022 Jan", "authors": [{"name": "Van der Meer J"}]}}}
        got = resolve_identifiers(["pmid:12345"], fetch=lambda *a, **k: (200, json.dumps(payload).encode()), delay=lambda _: None,
                                  expected_metadata={"pmid:12345": {"title": "A present study", "year": 2022, "first_author": "Meer"}})
        self.assertEqual(got["results"][0]["status"], "resolved")
        self.assertEqual(got["results"][0]["first_author"], "Van der Meer")
        self.assertEqual(got["results"][0]["metadata_check"], "match")

        feed = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
                b'<title>A present study</title><published>2022-01-01T00:00:00Z</published>'
                b'<author><name>Jane Smith Jr.</name></author></entry></feed>')
        arxiv = resolve_identifiers(["arxiv:2301.12345"], fetch=lambda *a, **k: (200, feed), delay=lambda _: None,
                                    expected_metadata={"arxiv:2301.12345": {"title": "A present study", "year": 2022,
                                                                            "first_author": "Smith"}})["results"][0]
        self.assertEqual("Smith", arxiv["first_author"])
        self.assertNotEqual("mismatch", arxiv["metadata_check"])

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
