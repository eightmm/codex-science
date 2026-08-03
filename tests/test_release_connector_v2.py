import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import codex_science.release as release_contract
from codex_science.connector_contract import QueryRequest, classify_drift, execute_connector, replay_snapshot
from codex_science.connector_sources import SOURCE_BY_KEY
from codex_science.connectors import PubMedConnector
from codex_science.mcp_server import CodexScienceMCP
from codex_science.release import (
    RELEASE_VERSION_RE,
    classify_release_path,
    plugin_version_advances,
    runtime_change_requires_bump,
    validate_release,
)
from codex_science.typed_connectors import ClinVarConnector, GnomADConnector
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

    def test_typed_source_registry_and_parsers_are_available(self) -> None:
        for key in ("clinvar", "dbsnp", "gnomad", "encode", "jaspar", "geo", "arrayexpress", "metabolights", "bindingdb", "openfda", "emdb", "complex_portal", "intact", "eqtl_catalogue"):
            self.assertIn(key, SOURCE_BY_KEY)
        clinvar = ClinVarConnector(fetch_json=lambda _url: {"esearchresult": {"idlist": ["42"]}})
        self.assertEqual("42", clinvar.search("BRCA1", limit=1)[0]["id"])
        gnomad = GnomADConnector(post_json=lambda _url, _body: {"data": {"variant": {"variant_id": "1-100-A-G", "exome": {"af": 0.1}, "genome": {"af": 0.2}}}})
        self.assertEqual("GRCh38", gnomad.search("1-100-A-G", limit=1)[0]["assembly"])

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
