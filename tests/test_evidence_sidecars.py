import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_science.artifact_index import render_markdown
from codex_science.artifacts import validate_bundle
from codex_science.commitment_ledger import resolve_target_ids
from codex_science.evidence import _validate_study_table, review_sidecars, validate_sidecars
from codex_science.literature import (
    diff_review_snapshots,
    normalize_persistent_id,
    study_key,
    validate_review_snapshot,
)
from codex_science.reference_contract import validate_reference_use_receipt
from codex_science.review import review_manifest
from codex_science.reviewer_runtime import build_review_packet


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
        self.assertIn("quote only the verbatim claim-bearing sentences, not the whole abstract", message)
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

    def test_persistent_ids_and_study_keys_normalize_with_fallback(self) -> None:
        self.assertEqual(
            "10.1234/example",
            normalize_persistent_id(" HTTPS://DOI.ORG/10.1234/Example. "),
        )
        self.assertEqual("12345", normalize_persistent_id("PMID:12345/"))
        self.assertEqual(
            "10.1000/a",
            study_key({"persistent_ids": ["doi:10.1000/z", "https://doi.org/10.1000/A"]}),
        )
        self.assertEqual("legacy-id", study_key({"persistent_ids": "ignored", "persistent_id": "doi:Legacy-ID."}))
        fallback = study_key({"title": "  A Study ", "year": 2024, "first_author": " Smith "})
        self.assertTrue(fallback.startswith("fallback:"))
        self.assertEqual(fallback, study_key({"title": "a study", "year": 2024, "first_author": "smith"}))

    def test_snapshot_validation_reports_bad_values_without_mutating_input(self) -> None:
        valid = json.loads((self.example / "snapshot.current.json").read_text())
        cases = [
            (None, "must be an object"),
            ({**valid, "schema_version": 2}, "schema version"),
            ({**valid, "question_framework": "NOPE"}, "framework"),
            ({**valid, "question": True}, "question"),
            ({**valid, "question": "  "}, "question"),
            ({**valid, "queries": "not a list"}, "queries must be a list"),
            ({**valid, "queries": [None]}, "query 0 must be an object"),
            ({**valid, "queries": [valid["queries"][0], valid["queries"][0]]}, "Duplicate literature query id"),
            ({**valid, "queries": [{**valid["queries"][0], "source": ""}]}, "source"),
            ({**valid, "studies": [None]}, "study 0 must be an object"),
            ({**valid, "studies": [valid["studies"][0], valid["studies"][0]]}, "Duplicate literature study id"),
            ({**valid, "studies": [{**valid["studies"][0], "eligibility": "maybe"}]}, "Invalid eligibility"),
            ({**valid, "studies": [{**valid["studies"][0], "eligibility": "exclude", "exclusion_reason": " "}]}, "exclusion_reason"),
            ({**valid, "claims": [None]}, "claim 0 must be an object"),
            ({**valid, "claims": [valid["claims"][0], valid["claims"][0]]}, "Duplicate literature claim id"),
            ({**valid, "claims": [{**valid["claims"][0], "status": None}]}, "status"),
        ]
        for broken, message in cases:
            with self.subTest(message=message):
                before = copy.deepcopy(broken)
                with self.assertRaisesRegex(ValueError, message):
                    validate_review_snapshot(broken)
                self.assertEqual(before, broken)

    def test_snapshot_validation_accepts_empty_collections_and_integer_text(self) -> None:
        snapshot = {
            "schema_version": 1, "protocol_id": 7, "evidence_cutoff": 20261027,
            "question_framework": "custom", "question": "Question",
            "queries": [], "studies": [], "claims": [],
        }
        self.assertIsNone(validate_review_snapshot(snapshot))

    def test_diff_refuses_protocol_change_without_mutating_snapshots(self) -> None:
        previous = json.loads((self.example / "snapshot.previous.json").read_text())
        current = json.loads((self.example / "snapshot.current.json").read_text())
        current["protocol_id"] = "different-protocol"
        before = (copy.deepcopy(previous), copy.deepcopy(current))
        with self.assertRaisesRegex(ValueError, "different protocol IDs"):
            diff_review_snapshots(previous, current)
        self.assertEqual(before, (previous, current))

    def test_diff_reports_sorted_additions_removals_and_changes(self) -> None:
        previous = {
            "schema_version": 1, "protocol_id": "p", "evidence_cutoff": "old",
            "question_framework": "PICO", "question": "Q",
            "queries": [{"query_id": "q-z", "source": "db", "query": "old"},
                        {"query_id": "q-remove", "source": "db", "query": "x"}],
            "studies": [{"study_id": "s-a", "title": "Old", "eligibility": "include"}],
            "claims": [{"id": "c-z", "status": "old"}, {"id": "c-remove", "status": "old"}],
        }
        current = {
            **previous, "evidence_cutoff": "new",
            "queries": [{"query_id": "q-z", "source": "db", "query": "new"},
                        {"query_id": "q-add", "source": "db", "query": "x"}],
            "studies": [{"study_id": "s-add", "title": "New", "eligibility": "awaiting-full-text"}],
            "claims": [{"id": "c-z", "status": "new"}, {"id": "c-add", "status": "new"}],
        }
        diff = diff_review_snapshots(previous, current)
        self.assertEqual({"schema_version": 1, "protocol_id": "p", "previous_cutoff": "old", "current_cutoff": "new"},
                         {key: diff[key] for key in ("schema_version", "protocol_id", "previous_cutoff", "current_cutoff")})
        self.assertEqual({"added": ["q-add"], "removed": ["q-remove"],
                          "changed": [{"id": "q-z", "before": previous["queries"][0], "after": current["queries"][0]}]},
                         diff["queries"])
        self.assertEqual({"added": ["s-add"], "removed": ["s-a"], "changed": []}, diff["studies"])
        self.assertEqual(["c-add"], diff["claims"]["added"])
        self.assertEqual(["c-remove"], diff["claims"]["removed"])
        self.assertEqual("c-z", diff["claims"]["changed"][0]["id"])

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


    @staticmethod
    def _ledger_procedure():
        return {
            "id": "test-procedure",
            "procedure": "One reference pass per included study",
            "target_set": {"unit": "study", "source_artifact": "studies.json", "selection": "included"},
            "target_ids": ["study-example-1"],
            "denominator": 1,
            "completed": [{"target_id": "study-example-1", "evidence_artifact": "studies.json"}],
            "completed_count": 1,
        }

    def _write_ledger(self, manifest, run_dir, ledger):
        protocol_path = run_dir / "protocol.json"
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        protocol["commitment_ledger"] = ledger
        protocol_path.write_text(json.dumps(protocol) + "\n", encoding="utf-8")
        self._rehash(manifest, run_dir, "protocol.json")

    def _write_screening(self, manifest, run_dir, records):
        payload = {"schema": "screening-table-v1", "records": records}
        path = run_dir / "screening.json"
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        manifest["artifacts"].append({
            "kind": "screening-table", "path": "screening.json",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })

    def test_commitment_ledger_complete_passes_and_reaches_reviewer_packet(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            procedure = self._ledger_procedure()
            field = "api_" + "key"
            procedure["target_set"][field] = "fixture-value"
            procedure["target_set"]["producer_rationale"] = "producer-only"
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            sidecars = validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            self.assertEqual(sidecars["protocol_commitment_context"]["procedures"][0]["id"], "test-procedure")
            packet = build_review_packet(run_dir / "manifest.json", review_modes=["record"])
            target_set = packet["protocol_commitment_context"]["procedures"][0]["target_set"]
            self.assertEqual(target_set[field], "[REDACTED]")
            self.assertNotIn("producer_rationale", target_set)
            self.assertEqual(sidecars["protocol_commitment_context"]["procedures"][0]["target_set"][field], "fixture-value")

    def test_commitment_ledger_shortfall_without_deviation_fails(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            procedure = self._ledger_procedure()
            procedure.update(id="test-shortfall", completed=[], completed_count=0)
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            with self.assertRaises(ValueError) as raised:
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            msg = str(raised.exception)
            self.assertIn("test-shortfall", msg)
            self.assertIn("study-example-1", msg)
            self.assertIn("deviation", msg)

    def test_commitment_ledger_valid_deviation_passes_and_reaches_packet(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            limitation = "Backward reference screening covered 0 of 1 included studies."
            (run_dir / "report.md").write_text(limitation + "\n", encoding="utf-8")
            self._rehash(manifest, run_dir, "report.md")
            procedure = self._ledger_procedure()
            procedure.update(completed=[], completed_count=0, deviation={
                "reason": "The reference list was unavailable.",
                "affected_claims": [{"claim_id": "claim-method-effect", "limitation": limitation}],
            })
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            sidecars = validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            self.assertEqual([], review_sidecars(sidecars))
            packet = build_review_packet(run_dir / "manifest.json", review_modes=["record"])
            self.assertEqual(packet["protocol_commitment_context"], sidecars["protocol_commitment_context"])
            self.assertEqual(1, sum(item["path"] == "report.md" for item in manifest["artifacts"]))
            manifest["artifacts"] = [item for item in manifest["artifacts"] if item["kind"] not in {"report", "lane-receipt"}]
            with self.assertRaisesRegex(ValueError, "test-procedure.*report.md"):
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_legacy_fixture_unchanged_has_no_ledger_context(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            protocol_path = run_dir / "protocol.json"
            original = protocol_path.read_text(encoding="utf-8")
            for contents in (original, "[]", '"legacy protocol"', "null", "0", "false", "{", ""):
                with self.subTest(contents=contents):
                    protocol_path.write_text(contents, encoding="utf-8")
                    self._rehash(manifest, run_dir, "protocol.json")
                    sidecars = validate_bundle(manifest, run_dir)
                    self.assertNotIn("protocol_commitment_context", sidecars)

    def test_unknown_target_set_refused(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            protocol_path = run_dir / "protocol.json"
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
            protocol["commitment_ledger"] = {
                "schema_version": 1,
                "procedures": [
                    {
                        "id":"bad-target",
                        "target_set":{"unit":"study","source_artifact":"bad.json","selection":"included"},
                        "target_ids":["S1"],
                        "denominator":1,
                        "completed":[{"target_id":"S1","evidence_artifact":"studies.json"}],
                        "completed_count":1
                    }
                ]
            }
            protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self._rehash(manifest, run_dir, "protocol.json")
            with self.assertRaises(ValueError) as raised:
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            self.assertIn("unsupported target_set", str(raised.exception))

    def test_bool_count_refused(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            protocol_path = run_dir / "protocol.json"
            protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
            protocol["commitment_ledger"] = {
                "schema_version": 1,
                "procedures": [
                    {
                        "id":"bool-count",
                        "target_set":{"unit":"study","source_artifact":"studies.json","selection":"included"},
                        "target_ids":["study-example-1"],
                        "denominator":True,
                        "completed":[{"target_id":"study-example-1","evidence_artifact":"studies.json"}],
                        "completed_count":1
                    }
                ]
            }
            protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self._rehash(manifest, run_dir, "protocol.json")
            with self.assertRaises(ValueError) as raised:
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            msg = str(raised.exception)
            self.assertIn("bool-count", msg)
            self.assertIn("bool", msg)

    def test_unextracted_included_record_blocks_exact_study_denominator(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            self._write_screening(manifest, run_dir, [{"record_id": "R1", "decision": "include"}])
            procedure = self._ledger_procedure()
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            with self.assertRaisesRegex(ValueError, "test-procedure.*unextracted.*screening.json.*R1"):
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            studies_path = run_dir / "studies.json"
            studies = json.loads(studies_path.read_text(encoding="utf-8"))
            studies["studies"][0]["record_id"] = "R1"
            studies_path.write_text(json.dumps(studies), encoding="utf-8")
            self._rehash(manifest, run_dir, "studies.json")
            validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_requires_registered_source_artifact(self):
        for unit, source, kind in (("record", "screening.json", "screening-table"),
                                   ("study", "studies.json", "study-table")):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                manifest["artifacts"] = [item for item in manifest["artifacts"] if item["kind"] not in {kind, "lane-receipt"}]
                procedure = self._ledger_procedure()
                procedure.update(target_set={"unit": unit, "source_artifact": source, "selection": "included"},
                                 target_ids=[], denominator=0, completed=[], completed_count=0)
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                with self.assertRaisesRegex(ValueError, "test-procedure.*missing source_artifact.*" + source):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_rejects_malformed_json(self):
        for relative, contents in (("protocol.json", '{"commitment_ledger":'),
                                   ("protocol.json", '["commitment_ledger"]'),
                                   ("protocol.json", '"commitment_ledger"'),
                                   ("screening.json", "{"), ("screening.json", "[]"),
                                   ("studies.json", "{")):
            with self.subTest(relative=relative, contents=contents), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_screening(manifest, run_dir, [])
                procedure = self._ledger_procedure()
                procedure.update(target_set={"unit": "record", "source_artifact": "screening.json", "selection": "all"},
                                 target_ids=[], denominator=0, completed=[], completed_count=0)
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                (run_dir / relative).write_text(contents, encoding="utf-8")
                self._rehash(manifest, run_dir, relative)
                with self.assertRaisesRegex(ValueError, relative):
                    validate_bundle(manifest, run_dir)

    def test_commitment_ledger_namespace_shape_and_empty_procedures(self):
        for ledger in (None, [], False, 0, "", {}, {"schema_version": 1},
                       {"schema_version": 1, "procedures": None},
                       {"schema_version": 1, "procedures": {}},
                       {"schema_version": 1, "procedures": [None]},
                       {"schema_version": 2, "procedures": []}):
            with self.subTest(ledger=ledger), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_ledger(manifest, run_dir, ledger)
                with self.assertRaisesRegex(ValueError, "commitment_ledger|procedure"):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": []})
            sidecars = validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            self.assertNotIn("protocol_commitment_context", sidecars)

    def test_commitment_ledger_study_membership_requires_explicit_true(self):
        studies = [{"study_id": "included", "included": True}, {"study_id": "missing"}]
        studies.extend({"study_id": str(index), "included": value}
                       for index, value in enumerate((False, None, 0, 1, "true")))
        self.assertEqual(["included"], resolve_target_ids(
            {"unit": "study", "source_artifact": "studies.json", "selection": "included"},
            {"studies": studies}, None,
        ))

    def test_commitment_ledger_record_membership_reuses_loaded_payloads(self):
        from codex_science import evidence
        for records, selection, targets in (([], "included", []), ([], "all", []),
                ([{"record_id": "R1", "decision": "include"}, {"record_id": "R2", "decision": "exclude"}], "included", ["R1"]),
                ([{"record_id": "R1", "decision": "include"}, {"record_id": "R2", "decision": "exclude"}], "all", ["R1", "R2"])):
            with self.subTest(selection=selection, targets=targets), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_screening(manifest, run_dir, records)
                procedure = self._ledger_procedure()
                procedure.update(target_set={"unit": "record", "source_artifact": "screening.json", "selection": selection},
                                 target_ids=targets, denominator=len(targets), completed_count=len(targets),
                                 completed=[{"target_id": item, "evidence_artifact": "screening.json"} for item in targets])
                other = copy.deepcopy(procedure)
                other["id"] = "second-procedure"
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure, other]})
                with patch.object(evidence, "_load_json", wraps=evidence._load_json) as load:
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                names = [call.args[0].name for call in load.call_args_list]
                self.assertEqual(1, names.count("screening.json"))
                self.assertEqual(1, names.count("studies.json"))

    def test_commitment_ledger_rejects_malformed_screening(self):
        for payload in ({}, {"schema": "other", "records": []},
                {"schema": "screening-table-v1", "records": None},
                {"schema": "screening-table-v1", "records": [None]},
                {"schema": "screening-table-v1", "records": [{"record_id": "", "decision": "include"}]},
                {"schema": "screening-table-v1", "records": [{"record_id": "R1", "decision": "bad"}]},
                {"schema": "screening-table-v1", "records": [{"record_id": "R1", "decision": "include"}] * 2}):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_screening(manifest, run_dir, [])
                (run_dir / "screening.json").write_text(json.dumps(payload), encoding="utf-8")
                self._rehash(manifest, run_dir, "screening.json")
                procedure = self._ledger_procedure()
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                with self.assertRaisesRegex(ValueError, "screening.json"):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_rejects_invalid_closure_fields(self):
        cases = [({"target_ids": ["study-example-1", None]}, "target_ids"),
                 ({"target_ids": ["study-example-1", "study-example-1"]}, "target_ids"),
                 ({"target_set": {"unit": [], "source_artifact": "studies.json", "selection": "included"}}, "target_set")]
        for field in ("denominator", "completed_count"):
            cases.extend(({field: value}, field) for value in (None, True, -1, 0, 1.5, "1"))
        for update, message in cases:
            with self.subTest(update=update), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                procedure = self._ledger_procedure()
                procedure.update(update)
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                with self.assertRaisesRegex(ValueError, message):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_deviation_needs_claim_register_or_no_impact(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            limitation = "No reference lists were screened."
            (run_dir / "report.md").write_text(limitation, encoding="utf-8")
            self._rehash(manifest, run_dir, "report.md")
            procedure = self._ledger_procedure()
            procedure.update(completed=[], completed_count=0, deviation={
                "reason": "References unavailable.",
                "affected_claims": [{"claim_id": "claim-method-effect", "limitation": limitation}],
            })
            manifest["artifacts"] = [item for item in manifest["artifacts"] if item["kind"] != "claim-register"]
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            procedure["deviation"]["affected_claims"][0]["claim_id"] = "unknown-claim"
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            with self.assertRaisesRegex(ValueError, "unknown-claim.*claims.json"):
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            for reason in (None, "", "No material claim depends on this procedure."):
                with self.subTest(reason=reason):
                    procedure["deviation"] = {"reason": "References unavailable.", "no_claim_impact_reason": reason}
                    self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                    if reason:
                        validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                    else:
                        with self.assertRaisesRegex(ValueError, "no_claim_impact_reason"):
                            validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_ignores_markdown_protocols(self):
        for with_json in (False, True):
            with self.subTest(with_json=with_json), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                record = next(item for item in manifest["artifacts"] if item["kind"] == "protocol")
                record["path"] = "protocol.md"
                (run_dir / "protocol.md").write_text("# Frozen protocol\nMarkdown remains supported.\n", encoding="utf-8")
                self._rehash(manifest, run_dir, "protocol.md")
                if with_json:
                    manifest["artifacts"].append({"kind": "protocol", "path": "protocol.json", "sha256": "0" * 64})
                    self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [self._ledger_procedure()]})
                sidecars = validate_bundle(manifest, run_dir)
                self.assertEqual(with_json, "protocol_commitment_context" in sidecars)

    def test_commitment_ledger_source_ids_require_strings(self):
        for kind, relative, field in (("record", "screening.json", "record_id"),
                                      ("study", "studies.json", "study_id")):
            for value in (0, 5, None, ["x"]):
                with self.subTest(kind=kind, value=value), tempfile.TemporaryDirectory() as tempdir:
                    run_dir, manifest = self._copy_example(Path(tempdir))
                    omitted = []
                    if kind == "record":
                        self._write_screening(manifest, run_dir, [{"record_id": value, "decision": "include"}])
                    else:
                        payload = json.loads((run_dir / relative).read_text(encoding="utf-8"))
                        payload["studies"][0][field] = value
                        (run_dir / relative).write_text(json.dumps(payload), encoding="utf-8")
                        self._rehash(manifest, run_dir, relative)
                        omitted = [item for item in manifest["artifacts"] if item["kind"] in {"evidence-graph", "lane-receipt"}]
                        manifest["artifacts"] = [item for item in manifest["artifacts"] if item not in omitted]
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                    manifest["artifacts"].extend(omitted)
                    procedure = self._ledger_procedure()
                    procedure["target_set"] = {"unit": kind, "source_artifact": relative, "selection": "included"}
                    self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                    with self.assertRaises(ValueError) as raised:
                        validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                    message = str(raised.exception)
                    for detail in ("test-procedure", field, "expected: string", repr(value)):
                        self.assertIn(detail, message)

        for unit, field in (("record", "record_id"), ("study", "study_id")):
            for value in ("", "   "):
                with self.subTest(unit=unit, empty=value):
                    row = {field: value, "decision": "include", "included": True}
                    with self.assertRaisesRegex(ValueError, "empty-source.*" + field + ".*expected: string"):
                        resolve_target_ids(
                            {"unit": unit, "selection": "included"},
                            {"studies": [row]}, {"records": [row]}, procedure_id="empty-source",
                        )

    def test_commitment_ledger_empty_procedures_require_schema_one(self):
        for version in (None, 0, 2, "1", {}, []):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_ledger(manifest, run_dir, {"schema_version": version, "procedures": []})
                with self.assertRaisesRegex(ValueError, "commitment_ledger.*schema_version.*1"):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_completed_ids_are_trimmed(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            procedure = self._ledger_procedure()
            procedure["target_ids"] = [" study-example-1 "]
            procedure["completed"][0]["target_id"] = "  study-example-1\t"
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            procedure["completed"].append({"target_id": "study-example-1", "evidence_artifact": "studies.json"})
            procedure["completed_count"] = 2
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            with self.assertRaisesRegex(ValueError, "duplicate target_id"):
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
            for value in ("", "   ", None, 5):
                with self.subTest(value=value):
                    procedure["completed"] = [{"target_id": value, "evidence_artifact": "studies.json"}]
                    procedure["completed_count"] = 1
                    self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                    with self.assertRaisesRegex(ValueError, "target_id.*non-empty string"):
                        validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_requires_unambiguous_source_artifacts(self):
        for kind in ("screening-table", "report"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                procedure = self._ledger_procedure()
                if kind == "screening-table":
                    self._write_screening(manifest, run_dir, [])
                    procedure.update(target_set={"unit": "record", "source_artifact": "screening.json", "selection": "all"},
                                     target_ids=[], denominator=0, completed=[], completed_count=0)
                    original, extra = "screening.json", "screening-extra.json"
                else:
                    limitation = "Reference screening was unavailable."
                    (run_dir / "report.md").write_text(limitation, encoding="utf-8")
                    self._rehash(manifest, run_dir, "report.md")
                    procedure.update(completed=[], completed_count=0, deviation={
                        "reason": "References unavailable.",
                        "affected_claims": [{"claim_id": "claim-method-effect", "limitation": limitation}],
                    })
                    original, extra = "report.md", "report-extra.md"
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                (run_dir / extra).write_bytes((run_dir / original).read_bytes())
                manifest["artifacts"].append({"kind": kind, "path": extra,
                    "sha256": hashlib.sha256((run_dir / extra).read_bytes()).hexdigest()})
                with self.assertRaisesRegex(ValueError, kind):
                    validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))
                if kind == "report":
                    procedure["deviation"] = {"reason": "No coverage.", "no_claim_impact_reason": "No material claim depends on it."}
                    procedures = [procedure]
                else:
                    procedures = []
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": procedures})
                validate_sidecars(manifest, run_dir, self._verified(manifest, run_dir))

    def test_commitment_ledger_protocol_revisions_are_order_independent(self):
        with tempfile.TemporaryDirectory() as tempdir:
            run_dir, manifest = self._copy_example(Path(tempdir))
            procedure = self._ledger_procedure()
            procedure.update(completed=[], completed_count=0)
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            with self.assertRaisesRegex(ValueError, "deviation is required.*study-example-1") as raised:
                validate_bundle(manifest, run_dir)
            shortfall = str(raised.exception)
            original = next(item for item in manifest["artifacts"] if item["kind"] == "protocol")
            extra = {"kind": "protocol", "path": "protocol-extra.json"}
            manifest["artifacts"].append(extra)
            for contents in ("{}", "[]", "{"):
                (run_dir / extra["path"]).write_text(contents, encoding="utf-8")
                self._rehash(manifest, run_dir, extra["path"])
                for ledger_first in (False, True):
                    with self.subTest(contents=contents, ledger_first=ledger_first):
                        protocols = [original, extra] if ledger_first else [extra, original]
                        manifest["artifacts"] = protocols + [
                            item for item in manifest["artifacts"] if item["kind"] != "protocol"
                        ]
                        with self.assertRaises(ValueError) as raised:
                            validate_bundle(manifest, run_dir)
                        self.assertEqual(shortfall, str(raised.exception))
            procedure["completed"] = self._ledger_procedure()["completed"]
            procedure["completed_count"] = 1
            self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": [procedure]})
            for protocols in ([extra, original], [original, extra]):
                with self.subTest(paths=[item["path"] for item in protocols]):
                    manifest["artifacts"] = protocols + [
                        item for item in manifest["artifacts"] if item["kind"] != "protocol"
                    ]
                    sidecars = validate_bundle(manifest, run_dir)
                    self.assertEqual("test-procedure", sidecars["protocol_commitment_context"]["procedures"][0]["id"])

    def test_commitment_ledger_requires_exactly_one_declaring_protocol(self):
        for count in (2, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as tempdir:
                run_dir, manifest = self._copy_example(Path(tempdir))
                self._write_ledger(manifest, run_dir, {"schema_version": 1, "procedures": []})
                paths = ["protocol.json"]
                for index in range(1, count):
                    relative = f"protocol-revision-{index}.json"
                    paths.append(relative)
                    (run_dir / relative).write_bytes((run_dir / "protocol.json").read_bytes())
                    manifest["artifacts"].append({"kind": "protocol", "path": relative})
                    self._rehash(manifest, run_dir, relative)
                for reverse in (False, True):
                    with self.subTest(reverse=reverse):
                        manifest["artifacts"].reverse()
                        with self.assertRaisesRegex(ValueError, f"commitment_ledger is declared in {count} protocol artifacts") as raised:
                            validate_bundle(manifest, run_dir)
                        message = str(raised.exception)
                        self.assertIn("must be declared in exactly one", message)
                        for relative in paths:
                            self.assertIn(relative, message)

    def _verified(self, manifest, run_dir):
        from codex_science.artifacts import verify_bundle_artifacts
        return verify_bundle_artifacts(manifest, run_dir)

if __name__ == "__main__":
    unittest.main()
