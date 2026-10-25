import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_index import render_markdown
from codex_science.artifacts import validate_bundle
from codex_science.evidence import _validate_study_table, review_sidecars, validate_sidecars
from codex_science.literature import diff_review_snapshots
from codex_science.reference_contract import validate_reference_use_receipt
from codex_science.review import review_manifest


class EvidenceSidecarTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository_root = Path(__file__).resolve().parents[1]
        self.example = self.repository_root / "examples" / "literature-review-reviewed-run"

    def test_checked_in_literature_bundle_validates_reviews_and_renders(self) -> None:
        manifest = json.loads((self.example / "manifest.json").read_text(encoding="utf-8"))
        sidecars = validate_bundle(manifest, self.example)
        review = review_manifest(manifest, self.example, sidecars=sidecars)

        self.assertEqual("passed", review["status"])
        self.assertEqual([], review["findings"])
        self.assertEqual({"claim-method-effect"}, set(sidecars["claim_by_id"]))
        self.assertEqual({"literature-search-pubmed"}, set(sidecars["lane_by_id"]))
        rendered = render_markdown(manifest, self.example)
        self.assertIn("### Evidence graph", rendered)
        self.assertIn("### Evidence and execution lanes", rendered)
        self.assertIn("### Query ledger", rendered)
        self.assertIn("claim-method-effect", rendered)
        self.assertIn("✅ Passed", rendered)
        self.assertIn("**Inference boundary:**", rendered)
        self.assertIn("**Limitation or uncertainty:**", rendered)
        self.assertIn("**Report:** [report.md](report.md)", rendered)
        self.assertNotIn("status=supported", rendered)
        self.assertNotIn("SHA-256 `", rendered)

    def test_bundle_reports_base_and_advanced_sidecar_errors_together(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"][0]["type"] = "source"
            graph_path.write_text(json.dumps(graph), encoding="utf-8")
            self._rehash(manifest, run_dir, "evidence_graph.json")
            ledger_path = run_dir / "invalid-ledger.json"
            ledger_path.write_text(json.dumps({"schema_version": 1, "skill": "science-review", "uses": []}))
            manifest["artifacts"].append({
                "kind": "reference-use-ledger", "path": "invalid-ledger.json",
                "sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            })
            with self.assertRaises(ValueError) as raised:
                validate_bundle(manifest, run_dir)
            self.assertIn("Invalid evidence node type", str(raised.exception))
            self.assertIn("reference use ledger requires a non-empty uses list", str(raised.exception))

    def test_validation_message_details_preserve_prefix_and_quote_values(self) -> None:
        from codex_science.evidence import _validate_lane_receipt

        lane = {
            "schema_version": 1,
            "lane_id": "L1",
            "lane_type": "search",
            "normalized_inputs": {},
            **{field: [] for field in (
                "claim_ids", "sources", "queries", "included_records", "excluded_records",
                "outputs", "supported_claim_ids", "contradicted_claim_ids", "dependencies",
                "limitations",
            )},
            "confidence": "moderate for bounded endpoints\nextra",
            "next_action": "review",
        }
        with self.assertRaises(ValueError) as raised:
            _validate_lane_receipt(lane)
        message = str(raised.exception)
        self.assertTrue(message.startswith("Invalid lane confidence for L1:"))
        self.assertIn("allowed: ", message)
        self.assertIn(repr(lane["confidence"]), message)
        self.assertNotIn("\n", message)

    def test_oversized_excerpt_error_uses_a_bounded_preview(self) -> None:
        payload = {
            "schema_version": 1,
            "studies": [{
                "study_id": "S1",
                "persistent_id": "doi:1",
                "title": "Study",
                "evidence_type": "primary",
                "included": True,
                "supports_claim_ids": ["C3"],
                "support_excerpts": [{"claim_id": "C3", "text": "x" * 2001}],
            }],
        }
        with self.assertRaises(ValueError) as raised:
            _validate_study_table(payload)
        message = str(raised.exception)
        self.assertTrue(
            message.startswith("Study S1 claim C3 excerpt text length must be 20..2000 characters")
        )
        self.assertIn("2001 characters; preview:", message)
        self.assertLess(len(message), 300)
        self.assertNotIn("\n", message)

    def test_differential_sidecar_and_reference_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            graph = root / "graph.json"
            graph.write_text(json.dumps({"schema_version": 1, "nodes": [], "edges": []}))
            studies = root / "studies.json"
            studies.write_text(json.dumps({"schema_version": 1, "studies": [{
                "study_id": "S1", "persistent_id": "doi:1", "title": "T",
                "evidence_type": "primary", "included": True,
            }]}))
            manifest = {"claims": [], "artifacts": [
                {"kind": "evidence-graph", "path": "graph.json"},
                {"kind": "study-table", "path": "studies.json"},
            ]}
            valid_base = {
                "schema_version": 1, "skill": "x", "path": "references/a.md",
                "sha256": "a" * 64, "read_reason": "why", "loaded_at": "now",
                "used_for": [], "sections": [], "search_terms": [],
            }

            def observed(call):
                try:
                    call()
                except Exception as error:
                    return "reject", type(error)
                return "accept", None

            cases = [
                ("empty graph with unlinked study", lambda: validate_sidecars(
                    manifest, root, {"graph.json": graph, "studies.json": studies}), ("accept", None)),
                ("receipt missing reference_id", lambda: validate_reference_use_receipt(valid_base), ("accept", None)),
                ("path with leading whitespace", lambda: validate_reference_use_receipt(
                    {**valid_base, "reference_id": "r", "path": " references/a.md"}), ("reject", ValueError)),
                ("reference_id=7", lambda: validate_reference_use_receipt(
                    {**valid_base, "reference_id": 7}), ("accept", None)),
            ]
            for label, call, expected in cases:
                with self.subTest(case=label):
                    self.assertEqual(expected, observed(call))

    def test_markdown_relationship_counts_use_readable_pluralized_phrases(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"].append(
                {"id": "study-example-2", "label": "Second study", "type": "study"}
            )
            graph["edges"].extend(
                [
                    {
                        "independence_group": "cohort-example-b",
                        "relation": "supports",
                        "source": "study-example-2",
                        "target": "claim-method-effect",
                    },
                    {
                        "independence_group": "cohort-example-c",
                        "relation": "contradicts",
                        "source": "study-example-3",
                        "target": "claim-method-effect",
                    },
                ]
            )
            graph["nodes"].append(
                {"id": "study-example-3", "label": "Contrary study", "type": "study"}
            )
            graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "evidence_graph.json")
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            studies["studies"].extend(
                [
                    {
                        "cohort_id": "cohort-example-b",
                        "contradicts_claim_ids": [],
                        "evidence_type": "primary",
                        "included": True,
                        "persistent_id": "doi:10.0000/example.primary.2",
                        "study_id": "study-example-2",
                        "supports_claim_ids": ["claim-method-effect"],
                        "title": "Second study",
                    },
                    {
                        "cohort_id": "cohort-example-c",
                        "contradicts_claim_ids": ["claim-method-effect"],
                        "evidence_type": "primary",
                        "included": True,
                        "persistent_id": "doi:10.0000/example.primary.3",
                        "study_id": "study-example-3",
                        "supports_claim_ids": [],
                        "title": "Contrary study",
                    },
                ]
            )
            studies_path.write_text(json.dumps(studies, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "studies.json")

            rendered = render_markdown(manifest, run_dir)

            self.assertIn("Supported by 2 links", rendered)
            self.assertIn("Contradicted by 1 link", rendered)
            self.assertIn("Supports: 2 links", rendered)
            self.assertNotIn("2 sources", rendered)

    def _copy_example(self, root: Path) -> tuple[Path, dict]:
        destination = root / "run"
        destination.mkdir()
        for source in self.example.rglob("*"):
            if source.is_dir():
                continue
            relative = source.relative_to(self.example)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        manifest_path = destination / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return destination, manifest

    @staticmethod
    def _rehash(manifest: dict, run_dir: Path, relative: str) -> None:
        digest = hashlib.sha256((run_dir / relative).read_bytes()).hexdigest()
        record = next(item for item in manifest["artifacts"] if item["path"] == relative)
        record["sha256"] = digest
        (run_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def test_seeded_duplicate_study_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            duplicate = copy.deepcopy(studies["studies"][0])
            duplicate["study_id"] = "study-example-duplicate"
            studies["studies"].append(duplicate)
            studies_path.write_text(json.dumps(studies, indent=2, sort_keys=True) + "\n")

            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["nodes"].append(
                {"id": "study-example-duplicate", "label": "Duplicate portal record", "type": "study"}
            )
            graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "studies.json")
            self._rehash(manifest, run_dir, "evidence_graph.json")

            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("duplicate-study", codes)

    def test_replicated_claim_with_null_cohorts_has_independent_studies(self) -> None:
        sidecars = {
            "claim_by_id": {"claim-1": {"status": "replicated"}},
            "study_by_id": {
                "study-1": {"persistent_id": "doi:10.1/one", "cohort_id": None},
                "study-2": {"persistent_id": "doi:10.1/two", "cohort_id": None},
            },
            "edges": [
                {"source": study_id, "target": "claim-1", "relation": "supports"}
                for study_id in ("study-1", "study-2")
            ],
        }

        findings = review_sidecars(sidecars)

        self.assertNotIn("dependent-evidence", {item["code"] for item in findings})

    def test_seeded_citation_mismatch_and_unsupported_claim_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            studies["studies"][0]["supports_claim_ids"] = []
            studies_path.write_text(json.dumps(studies, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "studies.json")
            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("citation-mismatch", codes)

            graph_path = run_dir / "evidence_graph.json"
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            graph["edges"] = []
            graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
            self._rehash(manifest, run_dir, "evidence_graph.json")
            sidecars = validate_bundle(manifest, run_dir)
            codes = {
                item["code"]
                for item in review_manifest(manifest, run_dir, sidecars=sidecars)["findings"]
            }
            self.assertIn("unsupported-conclusion", codes)

    def test_living_review_update_is_a_structured_diff(self) -> None:
        previous = json.loads((self.example / "snapshot.previous.json").read_text())
        current = json.loads((self.example / "snapshot.current.json").read_text())
        diff = diff_review_snapshots(previous, current)

        self.assertEqual("2026-06-30", diff["previous_cutoff"])
        self.assertEqual("2026-07-19", diff["current_cutoff"])
        self.assertEqual(["study-example-1"], diff["studies"]["added"])
        self.assertEqual("claim-method-effect", diff["claims"]["changed"][0]["id"])

    def test_snapshot_missing_required_field_is_rejected(self) -> None:
        current = json.loads((self.example / "snapshot.current.json").read_text())
        for field in ("protocol_id", "evidence_cutoff"):
            broken = {key: value for key, value in current.items() if key != field}
            with self.assertRaisesRegex(ValueError, field):
                diff_review_snapshots(current, broken)
            with self.assertRaisesRegex(ValueError, field):
                diff_review_snapshots(broken, current)

    def test_diff_cli_reports_invalid_snapshot_without_traceback(self) -> None:
        current = json.loads((self.example / "snapshot.current.json").read_text())
        broken = {key: value for key, value in current.items() if key != "protocol_id"}
        script = Path(__file__).resolve().parents[1] / "scripts" / "diff_literature_review.py"
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "baseline.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            missing = Path(tempdir) / "absent.json"
            for args, expected in (
                ((path, self.example / "snapshot.current.json"), "protocol_id"),
                ((missing, path), "absent.json"),
            ):
                result = subprocess.run(
                    [sys.executable, str(script), *map(str, args)],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(1, result.returncode)
                self.assertTrue(result.stderr.startswith("error:"), result.stderr)
                self.assertIn(expected, result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
