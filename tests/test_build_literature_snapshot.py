from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.literature import QUESTION_FRAMEWORKS, validate_review_snapshot
from codex_science.literature_snapshot_build import build_literature_snapshot

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/literature-review-reviewed-run"
CLI = ROOT / "scripts/build_literature_snapshot.py"


class BuildLiteratureSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "run"
        shutil.copytree(EXAMPLE, self.root)
        self.expected = json.loads((self.root / "snapshot.current.json").read_text(encoding="utf-8"))
        (self.root / "screening.json").unlink(missing_ok=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_snapshot_validates_and_matches_example_without_screening(self):
        result = build_literature_snapshot(self.root)
        snapshot = json.loads((self.root / "snapshot.current.json").read_text(encoding="utf-8"))
        validate_review_snapshot(snapshot)
        for field in ("schema_version", "protocol_id", "question", "question_framework", "evidence_cutoff", "studies", "claims"):
            self.assertEqual(self.expected[field], snapshot[field], field)
        shared_query_fields = {key: value for key, value in snapshot["queries"][0].items() if key in {"query_id", "source", "query"}}
        self.assertEqual(self.expected["queries"][0], shared_query_fields)
        self.assertEqual("complete", snapshot["queries"][0]["status"])
        self.assertEqual("2026-07-19T00:00:00Z", snapshot["queries"][0]["accessed_at"])
        self.assertEqual(hashlib.sha256((self.root / "protocol.json").read_bytes()).hexdigest(), result["inputs_sha256"]["protocol"])
        self.assertEqual(hashlib.sha256((self.root / "queries.jsonl").read_bytes()).hexdigest(), result["inputs_sha256"]["queries"])
        self.assertEqual({"queries": 1, "studies": 1, "claims": 1}, result["counts"])

    def test_excluded_study_requires_and_preserves_its_reason(self):
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["included"] = False
        studies["studies"][0]["record_id"] = "record-excluded-study"
        studies["studies"][0]["exclusion_reason"] = "wrong outcome: not reported"
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        (self.root / "screening.json").write_text(json.dumps({
            "schema": "screening-table-v1",
            "records": [{"record_id": "record-excluded-study", "title": "Example controlled study of the prespecified intervention",
                         "identifiers": ["doi:10.0000/example.primary.1"], "decision": "exclude",
                         "criterion": "wrong outcome", "rationale": "not reported"}],
        }), encoding="utf-8")

        build_literature_snapshot(self.root)
        snapshot_path = self.root / "snapshot.current.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        self.assertEqual(1, len(snapshot["studies"]))
        study = snapshot["studies"][0]
        self.assertEqual("exclude", study["eligibility"])
        self.assertEqual("wrong outcome: not reported", study["exclusion_reason"])
        before = snapshot_path.read_bytes()

        for invalid_reason in (None, ""):
            if invalid_reason is None:
                studies["studies"][0].pop("exclusion_reason", None)
            else:
                studies["studies"][0]["exclusion_reason"] = invalid_reason
            studies_path.write_text(json.dumps(studies), encoding="utf-8")
            with self.subTest(exclusion_reason=invalid_reason), self.assertRaisesRegex(
                ValueError, "study-example-1.*exclusion_reason"
            ):
                build_literature_snapshot(self.root)
            self.assertEqual(before, snapshot_path.read_bytes())

    def test_study_without_included_flag_defaults_to_include(self):
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        del studies["studies"][0]["included"]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")

        build_literature_snapshot(self.root)
        snapshot = json.loads((self.root / "snapshot.current.json").read_text(encoding="utf-8"))
        self.assertEqual("include", snapshot["studies"][0]["eligibility"])

    def test_excluded_and_awaiting_screening_records_are_included(self):
        screening = {
            "schema": "screening-table-v1",
            "records": [
                {"record_id": "record-excluded", "title": "Excluded title", "identifiers": ["pmid:123", "doi:10.1/excluded"],
                 "decision": "exclude", "criterion": "wrong population", "rationale": "population differs"},
                {"record_id": "record-awaiting", "title": "Awaiting title", "identifiers": ["pmcid:PMC123", "doi:10.1/wait"],
                 "decision": "awaiting-full-text", "criterion": "pending", "rationale": "full text unavailable"},
                {"record_id": "record-no-metadata", "title": "", "identifiers": [], "decision": "awaiting-full-text"},
            ],
        }
        (self.root / "screening.json").write_text(json.dumps(screening), encoding="utf-8")
        build_literature_snapshot(self.root)
        snapshot = json.loads((self.root / "snapshot.current.json").read_text(encoding="utf-8"))
        validate_review_snapshot(snapshot)
        rows = {row["study_id"]: row for row in snapshot["studies"]}
        self.assertEqual("doi:10.1/excluded", rows["record-excluded"]["persistent_id"])
        self.assertEqual("wrong population: population differs", rows["record-excluded"]["exclusion_reason"])
        self.assertEqual("awaiting-full-text", rows["record-awaiting"]["eligibility"])
        self.assertEqual("doi:10.1/wait", rows["record-awaiting"]["persistent_id"])
        self.assertEqual("untitled record record-no-metadata", rows["record-no-metadata"]["title"])

    def test_protocol_id_override_is_used_only_when_missing(self):
        protocol_path = self.root / "protocol.json"
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        del protocol["protocol_id"]
        protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
        output = self.root / "override-snapshot.json"
        missing = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", str(self.root), "--output", output.name],
            capture_output=True, text=True,
        )
        self.assertEqual(1, missing.returncode)
        self.assertIn("pass --protocol-id or add protocol_id to protocol.json", missing.stderr)
        self.assertIn("keep it stable across living updates", missing.stderr)
        self.assertFalse(output.exists())
        proc = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", str(self.root), "--protocol-id", "lnp-mrna-animal-rapid-v1", "--output", output.name],
            capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertEqual("lnp-mrna-animal-rapid-v1", json.loads(output.read_text())["protocol_id"])

        protocol["protocol_id"] = "recorded-protocol"
        protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
        output.write_bytes(b"unchanged")
        refused = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", str(self.root), "--protocol-id", "different-id", "--output", output.name],
            capture_output=True, text=True,
        )
        self.assertEqual(1, refused.returncode)
        self.assertIn("protocol_id", refused.stderr)
        self.assertEqual(b"unchanged", output.read_bytes())

    def test_screening_decisions_conflict_with_study_record_id_linkage(self):
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["record_id"] = "record-1"
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        screening_path = self.root / "screening.json"
        snapshot_path = self.root / "snapshot.current.json"
        before = snapshot_path.read_bytes()
        for decision in ("exclude", "awaiting-full-text"):
            screening_path.write_text(json.dumps({
                "schema": "screening-table-v1",
                "records": [{
                    "record_id": "record-1",
                    "title": "Example controlled study of the prespecified intervention",
                    "identifiers": ["doi:10.0000/example.primary.1"],
                    "decision": decision,
                    "criterion": "outside scope",
                    "rationale": "screening decision conflicts with extraction",
                }],
            }), encoding="utf-8")
            with self.subTest(decision=decision), self.assertRaisesRegex(
                ValueError,
                f"record record-1 is {decision} in screening.json but extracted as included study study-example-1",
            ):
                build_literature_snapshot(self.root)
            self.assertEqual(before, snapshot_path.read_bytes())

    def test_conflicting_duplicate_query_id_is_refused_without_output(self):
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"query_id": "q-pubmed-1", "source": "PubMed", "query": "different text"}) + "\n")
        output = self.root / "new-snapshot.json"
        with self.assertRaisesRegex(ValueError, "conflicting duplicate query_id: q-pubmed-1"):
            build_literature_snapshot(self.root, output.name)
        self.assertFalse(output.exists())

    def test_missing_protocol_field_and_other_problems_are_aggregated(self):
        protocol_path = self.root / "protocol.json"
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        del protocol["question"]
        protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        first = dict(studies["studies"][0])
        second = dict(studies["studies"][0], study_id="study-example-2")
        del first["title"]
        del second["persistent_id"]
        studies["studies"] = [first, second]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        with (self.root / "queries.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"query_id": "q-pubmed-1", "source": "Other", "query": "different text"}) + "\n")
        output = self.root / "new-snapshot.json"
        output.write_bytes(b"existing output must remain unchanged\n")
        before = output.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", str(self.root), "--output", output.name],
            capture_output=True, text=True,
        )
        self.assertEqual(1, proc.returncode)
        self.assertTrue(proc.stderr.startswith("error:"), proc.stderr)
        for problem in (
            "protocol.json missing required field: question",
            "study study-example-1 missing or blank title",
            "study study-example-2 missing or blank persistent_id",
            "conflicting duplicate query_id: q-pubmed-1",
        ):
            self.assertIn(problem, proc.stderr)
        self.assertEqual(before, output.read_bytes())

    def test_previous_snapshot_is_protected_and_unchanged(self):
        previous = self.root / "snapshot.previous.json"
        previous.write_text('{"immutable":true}\n', encoding="utf-8")
        before = previous.read_bytes()
        with self.assertRaisesRegex(ValueError, "snapshot.previous.json"):
            build_literature_snapshot(self.root, previous.name)
        self.assertEqual(before, previous.read_bytes())

    def test_cli_refuses_to_overwrite_a_validated_excerpt_source(self):
        source = self.root / "sources" / "example-excerpt.txt"
        source.parent.mkdir(exist_ok=True)
        excerpt_text = "This source excerpt is long enough to validate and protect."
        source.write_text(excerpt_text, encoding="utf-8")
        studies_path = self.root / "studies.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        studies["studies"][0]["support_excerpts"] = [{
            "claim_id": "claim-method-effect",
            "text": excerpt_text,
            "source_artifact": "sources/example-excerpt.txt",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }]
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        before = source.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "sources/example-excerpt.txt"],
            capture_output=True, text=True,
        )
        self.assertEqual(1, proc.returncode)
        self.assertIn("excerpt source", proc.stderr)
        self.assertEqual(before, source.read_bytes())

    def test_cli_fixed_registers_resolve_from_run_subdirectory(self):
        nested = self.root / "lanes"
        nested.mkdir(exist_ok=True)
        proc = subprocess.run(
            [sys.executable, str(CLI), "--run-dir", ".."],
            cwd=nested, capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertEqual("snapshot.current.json", json.loads(proc.stdout)["output"])

    def test_cli_help_names_required_protocol_fields(self):
        env = os.environ.copy()
        env.pop("PYTHONPATH", None)
        proc = subprocess.run([sys.executable, str(CLI), "--help"], capture_output=True, text=True, env=env)
        self.assertEqual(0, proc.returncode)
        for field in ("protocol_id", "question", "question_framework", "evidence_cutoff", *QUESTION_FRAMEWORKS):
            self.assertIn(field, proc.stdout)

    def test_cli_exit_codes_and_error_prefix(self):
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        good = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root)], capture_output=True, text=True, env=env)
        self.assertEqual(0, good.returncode, good.stderr)
        self.assertIn('"inputs_sha256"', good.stdout)
        bad = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root), "--output", "snapshot.previous.json"], capture_output=True, text=True, env=env)
        self.assertEqual(1, bad.returncode)
        self.assertTrue(bad.stderr.startswith("error:"))


if __name__ == "__main__":
    unittest.main()
