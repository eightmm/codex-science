import copy
import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import codex_science.release as release_contract
from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, replay_snapshot, sha256_json
from codex_science.connector_sources import SOURCE_BY_KEY
from codex_science.connectors import ArxivConnector, PubMedConnector
from codex_science.mcp_server import CodexScienceMCP
from codex_science.release import (
    RELEASE_VERSION_RE,
    classify_release_path,
    plugin_version_advances,
    runtime_change_requires_bump,
    validate_release,
)
from codex_science.typed_connectors import (
    ArrayExpressConnector,
    BindingDBConnector,
    ClinVarConnector,
    ComplexPortalConnector,
    DBSNPConnector,
    EMDBConnector,
    ENCODEConnector,
    GEOConnector,
    GnomADConnector,
    IntActConnector,
    JASPARConnector,
    MetaboLightsConnector,
    OpenFDAConnector,
    UniBindConnector,
    VersionedSnapshotConnector,
)
from codex_science.version import (
    CACHE_NEUTRAL_FILES,
    CACHE_NEUTRAL_PREFIXES,
    MCP_VERSION,
    PACKAGE_VERSION,
    PLUGIN_VERSION,
    RUNTIME_AFFECTING_PREFIXES,
    RUNTIME_VERSION,
)


class ReleaseAndConnectorV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]

    def test_release_identities_are_synchronized(self) -> None:
        self.assertEqual([], validate_release(self.root))
        self.assertIsNotNone(RELEASE_VERSION_RE.fullmatch(PLUGIN_VERSION))
        runtime_match = RELEASE_VERSION_RE.fullmatch(RUNTIME_VERSION)
        self.assertIsNotNone(runtime_match)
        assert runtime_match is not None
        self.assertEqual(PACKAGE_VERSION, runtime_match.group("package"))
        self.assertEqual(PACKAGE_VERSION, MCP_VERSION)
        self.assertTrue(runtime_change_requires_bump(["src/codex_science/review.py"], "1.0.0+codex.20260101000000", "1.0.0+codex.20260101000000"))
        self.assertFalse(runtime_change_requires_bump(["tests/test_release.py"], "a", "a"))
        self.assertFalse(
            runtime_change_requires_bump(
                ["vendor/scientific-agent-skills"],
                "1.0.0+codex.20260101000000",
                "1.0.0+codex.20260101000001",
            )
        )
        self.assertTrue(
            runtime_change_requires_bump(
                ["pyproject.toml"],
                "1.0.0+codex.20260101000001",
                "1.0.0+codex.20260101000000",
            )
        )
        self.assertTrue(
            plugin_version_advances(
                "1.0.0+codex.20260101000009", "1.0.0+codex.20260101000010"
            )
        )
        self.assertFalse(
            plugin_version_advances(
                "1.0.0+codex.20260101000010", "1.0.0+codex.20260101000009"
            )
        )
        self.assertFalse(plugin_version_advances("1.0.0+codex.a", "1.0.0+codex.b"))

    def test_plugin_package_is_independent_but_runtime_embeds_package(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plugin_version = "9.4.0+codex.20260101000000"
            package_version = "1.2.3"
            runtime_version = "1.2.3+codex.20260102000000"
            plugin = root / ".codex-plugin" / "plugin.json"
            plugin.parent.mkdir(parents=True)
            plugin.write_text(
                json.dumps({"version": plugin_version}) + "\n", encoding="utf-8"
            )
            (root / "pyproject.toml").write_text(
                f'[project]\nname = "release-fixture"\nversion = "{package_version}"\n',
                encoding="utf-8",
            )
            manifest = root / "release" / "manifest.json"
            manifest.parent.mkdir()
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "package_version": package_version,
                        "plugin_version": plugin_version,
                        "runtime_version": runtime_version,
                        "mcp_version": package_version,
                        "runtime_affecting_prefixes": list(RUNTIME_AFFECTING_PREFIXES),
                        "cache_neutral_files": list(CACHE_NEUTRAL_FILES),
                        "cache_neutral_prefixes": list(CACHE_NEUTRAL_PREFIXES),
                        "bootstrap_affecting_files": list(
                            release_contract.BOOTSTRAP_AFFECTING_FILES
                        ),
                        "bootstrap_affecting_prefixes": list(
                            release_contract.BOOTSTRAP_AFFECTING_PREFIXES
                        ),
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with mock.patch.multiple(
                release_contract,
                PACKAGE_VERSION=package_version,
                PLUGIN_VERSION=plugin_version,
                RUNTIME_VERSION=runtime_version,
                MCP_VERSION=package_version,
            ):
                self.assertEqual([], release_contract.validate_release(root))

            invalid_plugin = "9.4.0+codex.2026010100000"
            plugin.write_text(
                json.dumps({"version": invalid_plugin}) + "\n", encoding="utf-8"
            )
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["plugin_version"] = invalid_plugin
            manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with mock.patch.multiple(
                release_contract,
                PACKAGE_VERSION=package_version,
                PLUGIN_VERSION=invalid_plugin,
                RUNTIME_VERSION=runtime_version,
                MCP_VERSION=package_version,
            ):
                self.assertIn(
                    "plugin version must match <semver>+codex.<14 digits>",
                    release_contract.validate_release(root),
                )

            invalid_runtime = "1.2.3+codex.2026010200000x"
            payload["runtime_version"] = invalid_runtime
            manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with mock.patch.multiple(
                release_contract,
                PACKAGE_VERSION=package_version,
                PLUGIN_VERSION=invalid_plugin,
                RUNTIME_VERSION=invalid_runtime,
                MCP_VERSION=package_version,
            ):
                self.assertIn(
                    "runtime version must match <semver>+codex.<14 digits>",
                    release_contract.validate_release(root),
                )

    def test_every_repository_path_has_exactly_one_release_classification(self) -> None:
        import subprocess

        result = subprocess.run(
            [
                "git",
                "-C",
                str(self.root),
                "ls-files",
                "--cached",
                "--others",
                "--exclude-standard",
                "-z",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        paths = [path for path in result.stdout.split("\0") if path]
        self.assertTrue(paths)
        unknown = [path for path in paths if classify_release_path(path) == "unknown"]
        overlaps = [
            path
            for path in paths
            if any(path.startswith(prefix) for prefix in RUNTIME_AFFECTING_PREFIXES)
            and (
                path in CACHE_NEUTRAL_FILES
                or any(path.startswith(prefix) for prefix in CACHE_NEUTRAL_PREFIXES)
            )
        ]
        self.assertEqual([], unknown)
        self.assertEqual([], overlaps)

    def test_query_request_receipt_replay_and_drift_are_deterministic(self) -> None:
        def fetch_json(_url: str) -> dict:
            return {"release": "2026-07", "nextCursor": "cursor-2", "esearchresult": {"idlist": ["123", "456"]}}

        request = QueryRequest("pubmed", "search", {"query": "protein folding"}, page_size=2, max_pages=2)
        result = execute_connector(PubMedConnector(fetch_json=fetch_json), request, include_snapshot=True, retrieved_at="2026-07-19T00:00:00Z")
        self.assertEqual("q-" + request.request_sha256[:24], result.receipt.query_id)
        self.assertEqual("2026-07", result.receipt.source_release)
        self.assertEqual("partial-next-cursor", result.receipt.completeness)
        snapshot = result.snapshot()
        replayed = replay_snapshot(snapshot)
        self.assertEqual(result.receipt.normalized_records_sha256, replayed.receipt.normalized_records_sha256)
        self.assertEqual(result.records, replayed.records)

        without_pages = execute_connector(
            PubMedConnector(fetch_json=fetch_json), request, include_snapshot=False,
            retrieved_at="2026-07-19T00:00:00Z",
        ).snapshot()
        self.assertEqual([], without_pages["pages"])
        self.assertEqual(1, len(without_pages["receipt"]["pages"]))
        self.assertEqual(result.records, replay_snapshot(without_pages).records)
        for previous, current in ((without_pages, without_pages), (without_pages, snapshot), (snapshot, without_pages)):
            with self.subTest(previous_has_pages=bool(previous["pages"]), current_has_pages=bool(current["pages"])):
                self.assertEqual("unchanged", classify_drift(previous, current)["status"])

        changed = copy.deepcopy(snapshot)
        changed["records"][0]["title"] = "changed"
        changed["receipt"]["normalized_records_sha256"] = __import__("hashlib").sha256(
            json.dumps(changed["records"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        report = classify_drift(snapshot, changed)
        self.assertIn("semantic-drift", report["drift_types"])

    def test_legacy_connector_rejects_unsupported_evidence_cutoff(self) -> None:
        request = QueryRequest(
            "pubmed",
            "search",
            {"query": "protein folding"},
            evidence_cutoff="2026-01-01",
        )
        connector = PubMedConnector(fetch_json=lambda _url: {"esearchresult": {"idlist": []}})
        with self.assertRaisesRegex(ValueError, "evidence_cutoff is not supported"):
            execute_connector(connector, request)

    def test_replay_cross_checks_receipt_facts_and_stored_requests(self) -> None:
        snapshot = execute_connector(
            PubMedConnector(fetch_json=lambda _: {"esearchresult": {"idlist": ["123"]}}),
            QueryRequest("pubmed", "search", {"query": "test"}), include_snapshot=True,
        ).snapshot()
        self.assertEqual(1, len(replay_snapshot(snapshot).records))
        for empty_pages in ([], ()):
            with self.subTest(empty_pages=empty_pages):
                self.assertEqual(1, len(replay_snapshot({**snapshot, "pages": empty_pages}).records))
        mutations = [
            (("receipt", "source"), "other", "receipt source mismatch"),
            (("receipt", "operation"), "fetch", "receipt operation mismatch"),
            (("receipt", "source_contract_version"), "3", "receipt source_contract_version mismatch"),
            (("receipt", "returned_record_ids"), [], "returned record IDs mismatch"),
            (("receipt", "returned_record_ids"), ["999"], "returned record IDs mismatch"),
            (("pages",), snapshot["pages"] * 2, "page count mismatch"),
            (("pages",), "malformed", "page count mismatch"),
            (("pages", 0), None, "page must be an object"),
            (("pages", 0, "method"), "POST", "request method mismatch"),
            (("pages", 0, "url"), "", "request URL mismatch"),
            (("pages", 0, "request"), {}, "request body hash mismatch"),
        ]
        for malformed in (None, False, 0, "", {}):
            mutations.append((("pages",), malformed, "page count mismatch"))
        for count in (0, -1, 2, True, "1", None):
            mutations.append((("receipt", "pages", 0, "record_count"), count, "record count mismatch"))
        for path, value, message in mutations:
            with self.subTest(path=path, value=value):
                changed = copy.deepcopy(snapshot)
                target = changed
                for component in path[:-1]:
                    target = target[component]
                target[path[-1]] = value
                with self.assertRaisesRegex(ValueError, message):
                    replay_snapshot(changed)

    def test_replay_accepts_empty_fallback_ids_and_post_request_hashes(self) -> None:
        normalized_only = execute_connector(
            mock.Mock(query_v2=mock.Mock(return_value=[]), spec=["query_v2"]),
            QueryRequest("fixture", "search", {}), include_snapshot=True,
        ).snapshot()
        self.assertEqual((), replay_snapshot(normalized_only).records)

        class FixtureConnector:
            def __init__(self, records):
                self.records = records
                self._post_json = lambda _url, _body: {"results": records}

            def query_v2(self, _request):
                return self._post_json("https://example.test/query", {"limit": 0})["results"]

        for records in ([], [{}, {"id": 0}, {"id": "123"}, {"id": "123"}]):
            with self.subTest(records=records):
                snapshot = execute_connector(
                    FixtureConnector(records), QueryRequest("fixture", "search", {}), include_snapshot=True,
                ).snapshot()
                self.assertEqual(tuple(records), replay_snapshot(snapshot).records)
                self.assertEqual(sha256_json({"limit": 0}), snapshot["receipt"]["pages"][0]["request_body_sha256"])
                altered = copy.deepcopy(snapshot)
                altered["pages"][0]["request"] = None
                with self.assertRaisesRegex(ValueError, "request body hash mismatch"):
                    replay_snapshot(altered)
                altered = copy.deepcopy(snapshot)
                altered["receipt"]["returned_record_ids"] = ["extra"]
                with self.assertRaisesRegex(ValueError, "returned record IDs mismatch"):
                    replay_snapshot(altered)
                del snapshot["pages"]
                self.assertEqual(tuple(records), replay_snapshot(snapshot).records)

    def test_stored_response_change_reports_response_drift_with_equal_hashes(self) -> None:
        snapshot = execute_connector(
            PubMedConnector(fetch_json=lambda _: {"esearchresult": {"idlist": ["123"]}}),
            QueryRequest("pubmed", "search", {"query": "test"}), include_snapshot=True,
        ).snapshot()
        self.assertEqual("unchanged", classify_drift(snapshot, snapshot)["status"])
        absent = copy.deepcopy(snapshot)
        del absent["pages"]
        for previous, current in ((absent, snapshot), (snapshot, absent), (absent, absent)):
            with self.subTest(previous_has_pages="pages" in previous, current_has_pages="pages" in current):
                self.assertEqual("unchanged", classify_drift(previous, current)["status"])
        changed_hash = copy.deepcopy(absent)
        changed_hash["receipt"]["pages"][0]["response_sha256"] = "0" * 64
        self.assertEqual(["response-drift"], classify_drift(snapshot, changed_hash)["drift_types"])
        for response in ({"esearchresult": {"idlist": ["999"]}}, {}, None, [], 0, "malformed"):
            with self.subTest(response=response):
                changed = copy.deepcopy(snapshot)
                changed["pages"][0]["response"] = response
                self.assertEqual(snapshot["receipt"], changed["receipt"])
                report = classify_drift(snapshot, changed)
                self.assertEqual("changed", report["status"])
                self.assertEqual(["response-drift"], report["drift_types"])
        numeric = copy.deepcopy(snapshot)
        numeric["pages"][0]["response"] = {"value": 0}
        boolean = copy.deepcopy(numeric)
        boolean["pages"][0]["response"] = {"value": False}
        self.assertEqual(["response-drift"], classify_drift(numeric, boolean)["drift_types"])

    def test_typed_source_registry_and_parsers_are_available(self) -> None:
        for key in ("clinvar", "dbsnp", "gnomad", "encode", "jaspar", "geo", "arrayexpress", "metabolights", "bindingdb", "openfda", "emdb", "complex_portal", "intact", "eqtl_catalogue"):
            self.assertIn(key, SOURCE_BY_KEY)
        clinvar = ClinVarConnector(fetch_json=lambda _url: {"esearchresult": {"idlist": ["42"]}})
        self.assertEqual("42", clinvar.search("BRCA1", limit=1)[0]["id"])
        gnomad = GnomADConnector(post_json=lambda _url, _body: {"data": {"variant": {"variant_id": "1-100-A-G", "exome": {"af": 0.1}, "genome": {"af": 0.2}}}})
        self.assertEqual("GRCh38", gnomad.search("1-100-A-G", limit=1)[0]["assembly"])

    def test_gnomad_preserves_zero_and_missing_frequencies(self) -> None:
        for frequency in (0.0, 0, 0.1, None, ""):
            with self.subTest(frequency=frequency):
                variant = {"exome": {"af": frequency}, "genome": {"af": frequency}}
                connector = GnomADConnector(post_json=lambda *_: {"data": {"variant": variant}})
                record = connector.search("1-100-A-G")[0]
                expected = "" if frequency is None else str(frequency)
                self.assertEqual(expected, record["exome_af"])
                self.assertEqual(expected, record["genome_af"])
        for variant in ({}, {"exome": None, "genome": None}):
            connector = GnomADConnector(post_json=lambda *_: {"data": {"variant": variant}})
            record = connector.search("1-100-A-G")[0]
            self.assertEqual("", record["exome_af"])
            self.assertEqual("", record["genome_af"])

    def test_gnomad_graphql_errors_are_never_negative_evidence(self) -> None:
        request = QueryRequest("gnomad", "search", {"query": "1-100-A-G"})
        for variant in (None, {}, {"variant_id": "1-100-A-G"}):
            payload = {"data": {"variant": variant}, "errors": [{"message": "Too many requests"}]}
            connector = GnomADConnector(post_json=lambda *_: payload)
            for search in (lambda: connector.search("1-100-A-G"), lambda: execute_connector(connector, request)):
                with self.subTest(variant=variant), self.assertRaisesRegex(ValueError, "GraphQL"):
                    search()
        for extra in ({}, {"errors": []}):
            connector = GnomADConnector(post_json=lambda *_: {"data": {"variant": None}, **extra})
            result = execute_connector(connector, request)
            self.assertEqual("negative", result.receipt.missingness)
            self.assertEqual("complete", result.receipt.completeness)

    def test_legacy_parameters_are_rejected_before_transport(self) -> None:
        post = mock.Mock(return_value={"data": {"variant": None}})
        connector = GnomADConnector(post_json=post)
        for extra in ({"dataset": "gnomad_r3"}, {"assembly": "GRCh37"}, {"dataset": None, "assembly": ""}, {"unknown": 0}, {"limit": 2, "assembly": "GRCh37"}):
            with self.subTest(extra=extra):
                request = QueryRequest("gnomad", "search", {"query": "1-100-A-G", **extra})
                with self.assertRaises(ValueError) as raised:
                    execute_connector(connector, request)
                for name in set(extra) - {"limit"}:
                    self.assertIn(name, str(raised.exception))
                post.assert_not_called()
        for limit in (0, -1, 11, True, False, 1.0, "2", "", None, [], {}):
            with self.subTest(limit=limit):
                request = QueryRequest("gnomad", "search", {"query": "1-100-A-G", "limit": limit})
                with self.assertRaisesRegex(ValueError, r"parameters.limit must be an integer between 1 and 10"):
                    execute_connector(connector, request)
                post.assert_not_called()
        self.assertEqual((), execute_connector(connector, QueryRequest("gnomad", "search", {"query": "1-100-A-G"})).records)
        post.assert_called_once()

    def test_receipt_marks_remaining_pages_and_declared_totals(self) -> None:
        request = QueryRequest("jaspar", "search", {"query": "gene"}, page_size=1)
        for metadata, completeness, cursor in (
            ({"next": "https://example.test/page/2"}, "partial-next-cursor", "https://example.test/page/2"),
            ({"count": 2}, "bounded", None),
            ({"total": 2}, "bounded", None),
            ({"total_count": "2"}, "bounded", None),
            ({"meta": {"results": {"total": 2}}}, "bounded", None),
        ):
            with self.subTest(metadata=metadata):
                connector = JASPARConnector(fetch_json=lambda _: {"results": [{"matrix_id": "MA1"}], **metadata})
                result = execute_connector(connector, request)
                self.assertEqual(completeness, result.receipt.completeness)
                self.assertEqual(cursor, result.receipt.pages[0].next_cursor)
                self.assertTrue(result.receipt.warnings)
        source_totals = (
            ("ols", ("response", "numFound"), ("response", "docs"),
             {"response": {"docs": [{"obo_id": "GO:0008150", "label": "biological_process"}]}}),
            ("clinical_trials", ("totalCount",), ("studies",),
             {"studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1"}}}]}),
            ("reactome", ("entriesCount",), ("results", 0, "entries"),
             {"results": [{"entries": [{"stId": "R-HSA-1", "name": "Pathway"}]}]}),
            ("biostudies", ("totalHits",), ("hits",),
             {"hits": [{"accession": "S-EPMC1"}]}),
            ("arrayexpress", ("totalHits",), ("hits",),
             {"hits": [{"accession": "E-MTAB-1"}]}),
            ("gtex", ("paging_info", "totalNumberOfItems"), ("data",),
             {"data": [{"gencodeId": "ENSG1.1"}]}),
            ("complex_portal", ("totalNumberOfElements",), ("elements",),
             {"elements": [{"complexAc": "CPX-1", "complexName": "Complex"}]}),
        )
        for source, total_path, records_path, template in source_totals:
            for total in (100, 1, "100", 0, "", None, "bad", True, -1, [], {}):
                with self.subTest(source=source, total=total):
                    payload = copy.deepcopy(template)
                    target = payload
                    for component in total_path[:-1]:
                        target = target.setdefault(component, {})
                    target[total_path[-1]] = total
                    if type(total) is int and total == 0:
                        target = payload
                        for component in records_path[:-1]:
                            target = target[component]
                        target[records_path[-1]] = []
                    connector = SOURCE_BY_KEY[source].factory()
                    connector._fetch_json = mock.Mock(return_value=payload)
                    result = execute_connector(connector, QueryRequest(source, "search", {"query": "biological process"}, page_size=1))
                    bounded = total in (100, "100")
                    self.assertEqual("bounded" if bounded else "complete", result.receipt.completeness)
                    self.assertEqual(bounded, bool(result.receipt.warnings))
                    self.assertEqual(0 if type(total) is int and total == 0 else 1, len(result.records))
        for count, ids, expected in ((0, [], "complete"), (1, ["1"], "complete"), (2, ["1"], "bounded"), ("2", ["1"], "bounded")):
            with self.subTest(count=count):
                connector = PubMedConnector(fetch_json=lambda _: {"esearchresult": {"count": count, "idlist": ids}})
                result = execute_connector(connector, QueryRequest("pubmed", "search", {"query": "gene"}, page_size=1))
                self.assertEqual(expected, result.receipt.completeness)
        for metadata in ({}, {"next": None}, {"next": ""}, {"next": 0}, {"next": []}, {"count": None}, {"count": "bad"}, {"count": True}, {"count": -1}):
            with self.subTest(metadata=metadata):
                result = execute_connector(JASPARConnector(fetch_json=lambda _: {"results": [], **metadata}), request)
                self.assertEqual("complete", result.receipt.completeness)

    def test_receipt_marks_legacy_request_caps(self) -> None:
        for limit, page_size, max_pages, expected in (
            (1, 1, 1, 1), (3, 5, 1, 3), (10, 2, 1, 2),
            (3, 2, 2, 3), (10, 2, 3, 6), (10, 20, 1, 10),
        ):
            with self.subTest(limit=limit, page_size=page_size, max_pages=max_pages):
                fetch = mock.Mock(return_value={"esearchresult": {"idlist": [str(i) for i in range(10)]}})
                request = QueryRequest("pubmed", "search", {"query": "gene", "limit": limit}, page_size=page_size, max_pages=max_pages)
                result = execute_connector(PubMedConnector(fetch_json=fetch), request, include_snapshot=True)
                sent = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0]).query)
                self.assertEqual([str(expected)], sent["retmax"])
                self.assertEqual(expected, len(result.records))
                self.assertEqual({"query": "gene", "limit": limit}, result.snapshot()["request"]["parameters"])
                self.assertEqual(request.request_sha256, result.receipt.canonical_request_sha256)
                self.assertEqual(result.records, replay_snapshot(result.snapshot()).records)
        for page_size in (1, 10, 11, 20, 100):
            with self.subTest(page_size=page_size):
                fetch = mock.Mock(return_value={"esearchresult": {"idlist": []}})
                result = execute_connector(PubMedConnector(fetch_json=fetch), QueryRequest("pubmed", "search", {"query": "gene"}, page_size=page_size))
                sent = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.call_args.args[0]).query)
                self.assertEqual([str(min(page_size, 10))], sent["retmax"])
                self.assertEqual("bounded" if page_size > 10 else "complete", result.receipt.completeness)
                self.assertEqual(page_size > 10, bool(result.receipt.warnings))
        for page_size in (0, "bad", None):
            with self.subTest(page_size=page_size):
                fetch = mock.Mock()
                with self.assertRaises((ValueError, TypeError)):
                    execute_connector(PubMedConnector(fetch_json=fetch), QueryRequest("pubmed", "search", {"query": "gene"}, page_size=page_size))
                fetch.assert_not_called()

    def test_receipt_marks_atom_totals_without_rejecting_empty_feeds(self) -> None:
        for total, entry, expected in (
            ("0", "", "complete"), ("", "", "complete"), ("bad", "", "complete"),
            ("1", "<entry><id>http://arxiv.org/abs/1234.5678</id></entry>", "complete"),
            ("2", "<entry><id>http://arxiv.org/abs/1234.5678</id></entry>", "bounded"),
        ):
            with self.subTest(total=total):
                atom = ('<feed xmlns="http://www.w3.org/2005/Atom" '
                        'xmlns:os="http://a9.com/-/spec/opensearch/1.1/">'
                        f'<os:totalResults>{total}</os:totalResults>{entry}</feed>')
                result = execute_connector(ArxivConnector(fetch_text=lambda _: atom), QueryRequest("arxiv", "search", {"query": "geometry"}, page_size=1))
                self.assertEqual(expected, result.receipt.completeness)

    def test_v2_arxiv_errors_do_not_create_negative_receipts(self) -> None:
        for response in (
            "<html><body>Too many requests</body></html>",
            '<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            '<id>http://arxiv.org/api/errors#unavailable</id><title>Error</title></entry></feed>',
        ):
            with self.subTest(response=response):
                fetch = mock.Mock(return_value=response)
                connector = ArxivConnector(fetch_text=fetch)
                with self.assertRaisesRegex(ValueError, "arXiv"):
                    execute_connector(connector, QueryRequest("arxiv", "search", {"query": "geometry"}))
                self.assertIs(fetch, connector._fetch_text)

    def test_replay_rejects_stored_response_digest_mismatches(self) -> None:
        for connector in (
            PubMedConnector(fetch_json=lambda _: {"esearchresult": {"idlist": []}}),
            GnomADConnector(post_json=lambda *_: {"data": {"variant": None}}),
            ArxivConnector(fetch_text=lambda _: '<feed xmlns="http://www.w3.org/2005/Atom"/>'),
        ):
            snapshot = execute_connector(connector, QueryRequest("fixture", "search", {"query": "1-100-A-G"}), include_snapshot=True).snapshot()
            self.assertEqual((), replay_snapshot(snapshot).records)
            for response in ({}, None, [], 0, "malformed"):
                with self.subTest(connector=type(connector).__name__, response=response):
                    changed = copy.deepcopy(snapshot)
                    changed["pages"][0]["response"] = response
                    with self.assertRaisesRegex(ValueError, "response hash mismatch"):
                        replay_snapshot(changed)
            changed = copy.deepcopy(snapshot)
            del changed["pages"][0]["response"]
            with self.assertRaisesRegex(ValueError, "response hash mismatch"):
                replay_snapshot(changed)

    def test_replay_verifies_every_response_and_accepts_canonical_json(self) -> None:
        class FixtureConnector:
            def __init__(self):
                self._fetch_json = lambda _: {"results": [], "total": 0}

            def query_v2(self, _request):
                self._fetch_json("https://example.test/page/1")
                return self._fetch_json("https://example.test/page/2")["results"]

        snapshot = execute_connector(FixtureConnector(), QueryRequest("fixture", "search", {}), include_snapshot=True).snapshot()
        for stored in snapshot["pages"]:
            stored["response"] = {"total": 0, "results": []}
        self.assertEqual((), replay_snapshot(snapshot).records)
        for index in (0, 1):
            changed = copy.deepcopy(snapshot)
            changed["pages"][index]["response"]["total"] = 1
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "response hash mismatch"):
                replay_snapshot(changed)

    def test_typed_connectors_validate_inputs_without_transport_or_state_changes(self) -> None:
        fetch = mock.Mock(return_value={})
        post = mock.Mock(return_value={})
        for connector in (ClinVarConnector(fetch_json=fetch), ENCODEConnector(fetch_json=fetch)):
            for query, limit, message in (("  ", 1, "query"), ("x" * 501, 1, "query"), ("valid", 0, "limit"), ("valid", 11, "limit"), ("valid", True, "limit")):
                before = (fetch.call_count, post.call_count)
                with self.assertRaisesRegex(ValueError, message):
                    connector.search(query, limit=limit)
                self.assertEqual(before, (fetch.call_count, post.call_count))

        gnomad = GnomADConnector(post_json=post)
        binding = BindingDBConnector(fetch_json=fetch)
        for connector, query, message in (
            (gnomad, "not-a-variant", "gnomAD query must be chr-pos-ref-alt"),
            (binding, "not-a-protein", "BindingDB query must be a UniProt accession"),
        ):
            before = (fetch.call_count, post.call_count)
            with self.assertRaisesRegex(ValueError, message):
                connector.search(query)
            self.assertEqual(before, (fetch.call_count, post.call_count))

    def test_typed_connectors_normalize_results_apply_limits_and_handle_empty_payloads(self) -> None:
        payloads = [
            {"esearchresult": {"idlist": ["a", "b", "c"]}},
            {"esearchresult": {"idlist": ["GSE1"]}},
            {"@graph": [{"accession": "ENC1", "title": "Experiment", "@type": ["Experiment"]}]},
            {"results": [{"matrix_id": "MA0001", "name": "Motif", "collection": "CORE"}]},
            [{"id": "ds1", "tf_name": "TF", "species": "human"}],
            {"hits": [{"accession": "E-MTAB-1", "title": "Study"}]},
            {"content": [{"studyIdentifier": " MTBLS1", "title": "Metabolome"}]},
            {"results": [{"openfda": {"spl_id": ["spl1"], "brand_name": ["Brand"], "product_type": ["HUMAN PRESCRIPTION DRUG"]}}]},
            {"affinities": [{"monomerid": "42", "ligand_name": "Ligand", "affinity_type": "Ki", "affinity": 3}]},
            {"results": [{"emdb_id": "EMD-1"}]},
            {"elements": [{"complexAc": "CPX-1", "complexName": "Complex"}]},
            {"content": [{"interactionAc": "INT-1", "description": "Interaction"}]},
        ]
        classes = (
            ClinVarConnector, GEOConnector, ENCODEConnector, JASPARConnector, UniBindConnector,
            ArrayExpressConnector, MetaboLightsConnector, OpenFDAConnector,
            BindingDBConnector, EMDBConnector, ComplexPortalConnector, IntActConnector,
        )
        for cls, payload in zip(classes, payloads):
            transport = mock.Mock(return_value=payload)
            connector = cls(fetch_json=transport)
            query = "A12345" if cls is BindingDBConnector else "gene"
            results = connector.search(query, limit=1)
            self.assertEqual(1, len(results), cls.__name__)
            self.assertTrue(results[0].get("id"), cls.__name__)
            self.assertTrue(results[0].get("title"), cls.__name__)
            self.assertEqual(1, transport.call_count)

        fetch = mock.Mock(return_value={"esearchresult": {"idlist": [str(i) for i in range(12)]}})
        records = DBSNPConnector(fetch_json=fetch).search("x" * 500, limit=10)
        self.assertEqual(10, len(records))
        self.assertEqual("snp", records[0]["database"])
        self.assertEqual("https://www.ncbi.nlm.nih.gov/snp/0", records[0]["url"])

        post = mock.Mock(return_value={"data": {"variant": {"variant_id": "1-100-A-G", "exome": {"af": 0.1}, "genome": {"af": 0.2}}}})
        self.assertEqual("0.1", GnomADConnector(post_json=post).search("chr1:100:a:g")[0]["exome_af"])
        self.assertEqual("", GnomADConnector(post_json=lambda *_: {"data": {"variant": {"variant_id": "1-1-A-G"}}}).search("1-1-A-G")[0]["genome_af"])
        self.assertEqual([], GnomADConnector(post_json=lambda *_: {"data": {"variant": None}}).search("1-1-A-G"))

    def test_simple_and_snapshot_connectors_skip_bad_records_and_match_case_insensitively(self) -> None:
        fetch = mock.Mock(return_value={"results": [None, {}, {"id": "7"}, {"id": "8", "title": "Named"}]})
        self.assertEqual(
            [
                {"id": "7", "title": "7", "url": "https://www.ebi.ac.uk/emdb/"},
                {"id": "8", "title": "Named", "url": "https://www.ebi.ac.uk/emdb/"},
            ],
            EMDBConnector(fetch_json=fetch).search("a/b", limit=4),
        )
        self.assertIn("a%2Fb", fetch.call_args.args[0])
        self.assertEqual([], IntActConnector(fetch_json=lambda _: {"results": "not-a-list"}).search("x"))

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "snap.json").write_text(json.dumps({"releases": [{"name": "Alpha"}, {"name": "Beta"}]}), encoding="utf-8")
            connector = VersionedSnapshotConnector("snap.json", root=root)
            self.assertEqual([{"name": "Alpha"}], connector.search("alpha"))
            self.assertEqual([], connector.search("absent"))

    def test_mcp_exposes_v2_and_preserves_legacy_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            inventory = Path(tempdir) / "inventory.json"
            inventory.write_text(json.dumps({"schema_version": 1, "source": {"commit": "abc"}, "summary": {"total": 0, "active": 0, "inactive": 0}, "skills": []}))
            server = CodexScienceMCP(inventory)
            response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            names = {item["name"] for item in response["result"]["tools"]}
            self.assertIn("science_query_source_v2", names)
            self.assertIn("science_list_source_contracts", names)
            self.assertIn("science_search_pubmed", names)
            initialized = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}})
            self.assertEqual(MCP_VERSION, initialized["result"]["serverInfo"]["version"])


if __name__ == "__main__":
    unittest.main()
