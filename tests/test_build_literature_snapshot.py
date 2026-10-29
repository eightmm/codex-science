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

        before = (self.root / "snapshot.current.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "claim-method-effect.*supported.*0.*1 required"):
            build_literature_snapshot(self.root)
        self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        claims_path = self.root / "claims.json"
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        claims["claims"][0]["status"] = "unsupported"
        claims_path.write_text(json.dumps(claims), encoding="utf-8")

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

    def test_claim_status_requires_declared_included_study_support(self):
        studies_path = self.root / "studies.json"
        claims_path = self.root / "claims.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        claim = claims["claims"][0]
        claim.pop("required_support")
        study = studies["studies"][0]
        output = self.root / "new-snapshot.json"
        before = (self.root / "snapshot.current.json").read_bytes()
        statuses = ("supported", "replicated", "suggestive", " supported ", "\treplicated\n", "\u2003suggestive\u2003")
        for status in statuses:
            claim["status"] = status
            claims_path.write_text(json.dumps(claims), encoding="utf-8")
            for rows in (
                [],
                [{**study, "supports_claim_ids": [], "contradicts_claim_ids": [claim["id"]]}],
                [{**study, "included": False, "exclusion_reason": "outside scope"}],
            ):
                with self.subTest(status=status, studies=rows):
                    studies_path.write_text(json.dumps({**studies, "studies": rows}), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, f"{claim['id']}.*{status.strip()}.*0.*1 required"):
                        build_literature_snapshot(self.root, output.name)
                    self.assertFalse(output.exists())
                    self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        for status in statuses:
            with self.subTest(status=status, count=1):
                claim["status"] = status
                claims_path.write_text(json.dumps(claims), encoding="utf-8")
                self.assertEqual(1, build_literature_snapshot(self.root, output.name)["counts"]["studies"])
                self.assertEqual(status, json.loads(output.read_text())["claims"][0]["status"])
        claim["status"] = "supported"
        collision = {**claim, "id": study["study_id"], "status": "planned"}
        claims_path.write_text(json.dumps({**claims, "claims": [claim, collision]}), encoding="utf-8")
        self.assertEqual({"queries": 1, "studies": 1, "claims": 2}, build_literature_snapshot(self.root, output.name)["counts"])
        padded_claim = {**claim, "id": f"\t{claim['id']} "}
        padded_study = {**study, "study_id": f" {study['study_id']} ",
                        "supports_claim_ids": [f" {claim['id']}\t", claim["id"]]}
        claims_path.write_text(json.dumps({**claims, "claims": [padded_claim]}), encoding="utf-8")
        studies_path.write_text(json.dumps({**studies, "studies": [padded_study]}), encoding="utf-8")
        self.assertEqual(1, build_literature_snapshot(self.root, output.name)["counts"]["studies"])
        self.assertEqual([{"id": claim["id"], "status": "supported"}], json.loads(output.read_text())["claims"])
        output_before = output.read_bytes()
        for invalid in ("", " ", "SUPPORTED", "Replicated", None, 0, []):
            with self.subTest(status=invalid):
                padded_claim["status"] = invalid
                claims_path.write_text(json.dumps({**claims, "claims": [padded_claim]}), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "claims:"):
                    build_literature_snapshot(self.root, output.name)
                self.assertEqual(output_before, output.read_bytes())
        studies_path.write_text(json.dumps({**studies, "studies": []}), encoding="utf-8")
        for status in ("conflicting", "unsupported", "planned", "withdrawn", "unavailable"):
            with self.subTest(status=status):
                claim["status"] = status
                claims_path.write_text(json.dumps(claims), encoding="utf-8")
                result = build_literature_snapshot(self.root, output.name)
                self.assertEqual(0, result["counts"]["studies"])
                self.assertEqual([{"id": claim["id"], "status": status}], json.loads(output.read_text())["claims"])
        claims_path.write_text(json.dumps({**claims, "claims": []}), encoding="utf-8")
        self.assertEqual(0, build_literature_snapshot(self.root, output.name)["counts"]["claims"])

    def test_required_support_threshold_and_validation(self):
        studies_path = self.root / "studies.json"
        claims_path = self.root / "claims.json"
        studies = json.loads(studies_path.read_text(encoding="utf-8"))
        claims = json.loads(claims_path.read_text(encoding="utf-8"))
        claim = claims["claims"][0]
        study = studies["studies"][0]
        study["supports_claim_ids"] *= 2
        claim["required_support"] = 2
        claims_path.write_text(json.dumps(claims), encoding="utf-8")
        studies_path.write_text(json.dumps(studies), encoding="utf-8")
        output = self.root / "snapshot.current.json"
        before = output.read_bytes()
        with self.assertRaisesRegex(ValueError, "claim-method-effect.*supported.*1.*2 required"):
            build_literature_snapshot(self.root)
        self.assertEqual(before, output.read_bytes())
        failed = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, failed.returncode)
        self.assertIn("1 supporting edge(s); 2 required", failed.stderr)
        self.assertEqual(before, output.read_bytes())
        for required, rows in ((0, []), (1, [study]), (2, [study, {**study, "study_id": "study-example-2"}])):
            with self.subTest(required_support=required, count=len(rows)):
                claim["required_support"] = required
                claims_path.write_text(json.dumps(claims), encoding="utf-8")
                studies_path.write_text(json.dumps({**studies, "studies": rows}), encoding="utf-8")
                result = build_literature_snapshot(self.root)
                self.assertEqual(len(rows), result["counts"]["studies"])
        before = output.read_bytes()
        for invalid in (None, "", "2", True, -1, 1.5, [], {}):
            with self.subTest(required_support=invalid):
                claim["required_support"] = invalid
                claims_path.write_text(json.dumps(claims), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "required_support must be a non-negative integer"):
                    build_literature_snapshot(self.root)
                self.assertEqual(before, output.read_bytes())

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

    def test_duplicate_query_metadata_must_match_including_presence(self):
        queries = self.root / "queries.jsonl"
        original = queries.read_text(encoding="utf-8")
        record = json.loads(original.splitlines()[0])
        output = self.root / "new-snapshot.json"
        before = (self.root / "snapshot.current.json").read_bytes()
        for field, replacement in (
            ("status", "failed"), ("accessed_at", "2026-07-20T00:00:00Z"),
            ("status", ""), ("status", 0), ("status", {}),
            ("accessed_at", ""), ("accessed_at", 0), ("accessed_at", {}),
            ("status", None), ("accessed_at", None),
        ):
            for reverse in (False, True):
                with self.subTest(field=field, replacement=replacement, reverse=reverse):
                    duplicate = dict(record)
                    if replacement is None:
                        duplicate.pop(field)
                    else:
                        duplicate[field] = replacement
                    rows = [record, duplicate]
                    if reverse:
                        rows.reverse()
                    queries.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "conflicting duplicate query_id: q-pubmed-1"):
                        build_literature_snapshot(self.root, output.name)
                    self.assertFalse(output.exists())
                    self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        for field in ("status", "accessed_at"):
            for first, second in ((0, False), (False, 0), (0, 0.0), (0.0, 0), (1, True), (True, 1)):
                with self.subTest(field=field, first=first, second=second):
                    output.unlink(missing_ok=True)
                    rows = [{**record, field: first}, {**record, field: second}]
                    queries.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "conflicting duplicate query_id: q-pubmed-1"):
                        build_literature_snapshot(self.root, output.name)
                    self.assertFalse(output.exists())
                    self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        queries.write_text(original + original, encoding="utf-8")
        result = build_literature_snapshot(self.root, output.name)
        self.assertEqual(1, result["counts"]["queries"])
        self.assertEqual(record["status"], json.loads(output.read_text())["queries"][0]["status"])

    def test_duplicate_query_response_identity_must_match(self):
        queries = self.root / "queries.jsonl"
        record = json.loads(queries.read_text(encoding="utf-8").splitlines()[0])
        record.pop("response_sha256")
        output = self.root / "new-snapshot.json"
        before = (self.root / "snapshot.current.json").read_bytes()
        for first, second in (("1" * 64, "f" * 64), ("a" * 64, "B" * 64),
                              (None, "a" * 64), ("", None), ([], {}), (0, False)):
            for reverse in (False, True):
                with self.subTest(first=first, second=second, reverse=reverse):
                    rows = [{**record, "response_sha256": first}, {**record, "response_sha256": second}]
                    if reverse:
                        rows.reverse()
                    queries.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "conflicting duplicate query_id: q-pubmed-1"):
                        build_literature_snapshot(self.root, output.name)
                    self.assertFalse(output.exists())
                    self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        failed = subprocess.run([sys.executable, str(CLI), "--run-dir", str(self.root)], capture_output=True, text=True)
        self.assertEqual(1, failed.returncode)
        self.assertIn("conflicting duplicate query_id: q-pubmed-1", failed.stderr)
        self.assertEqual(before, (self.root / "snapshot.current.json").read_bytes())
        expected = {key: value for key, value in record.items() if key in {"query_id", "source", "query", "status", "accessed_at"}}
        for rows in ([record, record], [record, {**record, "response_sha256": None}],
                     [{**record, "response_sha256": None}, record],
                     [{**record, "response_sha256": None}] * 2,
                     [{**record, "response_sha256": "a" * 64}] * 2,
                     [{**record, "response_sha256": "a" * 64}, {**record, "response_sha256": "A" * 64}],
                     [{**record, "response_sha256": ""}] * 2):
            with self.subTest(rows=rows):
                queries.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                result = build_literature_snapshot(self.root, output.name)
                self.assertEqual(1, result["counts"]["queries"])
                self.assertEqual([expected], json.loads(output.read_text())["queries"])

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

    def test_build_refuses_invalid_run_directory_and_unsafe_outputs(self):
        snapshot = self.root / "snapshot.current.json"
        before = snapshot.read_bytes()
        missing = self.root / "does-not-exist"
        with self.assertRaisesRegex(ValueError, "existing, non-symlink directory"):
            build_literature_snapshot(missing)
        with self.assertRaisesRegex(ValueError, "inside the run directory"):
            build_literature_snapshot(self.root, self.root.parent / "outside.json")
        with self.assertRaisesRegex(ValueError, "output file"):
            build_literature_snapshot(self.root, "../outside.json")
        self.assertEqual(before, snapshot.read_bytes())

    def test_invalid_registers_aggregate_errors_without_changing_output(self):
        output = self.root / "new-snapshot.json"
        output.write_bytes(b"preserve this output\n")
        before = output.read_bytes()
        (self.root / "protocol.json").write_text("[]", encoding="utf-8")
        (self.root / "claims.json").write_text("{broken", encoding="utf-8")
        (self.root / "queries.jsonl").write_text(
            "not-json\n[]\n{}\n"
            + json.dumps({"query_id": "q-empty", "source": " ", "query": "term"}) + "\n",
            encoding="utf-8",
        )

        with self.assertRaises(ValueError) as caught:
            build_literature_snapshot(self.root, output.name)
        message = str(caught.exception)
        for detected in (
            "input JSON must be an object: protocol.json",
            "protocol.json missing required field: question",
            "protocol.json missing required field: protocol_id",
            "claims:",
            "queries.jsonl line 1: invalid JSON",
            "queries.jsonl line 2 must be an object",
            "queries.jsonl line 3 has invalid query_id",
            "requires non-empty source and query for q-empty",
        ):
            self.assertIn(detected, message)
        self.assertEqual(before, output.read_bytes())

    def test_screening_validation_refusals_preserve_existing_snapshot(self):
        screening_path = self.root / "screening.json"
        output = self.root / "new-snapshot.json"
        output.write_bytes(b"keep current data\n")
        before = output.read_bytes()
        screening_path.write_text(json.dumps({"schema": "wrong", "records": [
        ]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "screening.json must use schema screening-table-v1"):
            build_literature_snapshot(self.root, output.name)
        screening_path.write_text(json.dumps({"schema": "screening-table-v1", "records": [
            None,
            {"record_id": "", "decision": "exclude"},
            {"record_id": "screen-1", "decision": "maybe"},
            {"record_id": "screen-2", "decision": "exclude", "identifiers": "doi:bad"},
            {"record_id": "screen-3", "decision": "exclude", "criterion": " ", "rationale": "missing"},
            {"record_id": "screen-3", "decision": "exclude"},
        ]}), encoding="utf-8")

        with self.assertRaises(ValueError) as caught:
            build_literature_snapshot(self.root, output.name)
        message = str(caught.exception)
        for detected in (
            "screening record 0 must be an object",
            "screening record 1 has invalid record_id",
            "screening record screen-1 has invalid decision",
            "screening record screen-2 identifiers must be a list of strings",
            "screening record screen-3 exclusion requires criterion and rationale",
            "duplicate screening record_id: screen-3",
        ):
            self.assertIn(detected, message)
        self.assertEqual(before, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
