import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.reviewer_runtime import _fingerprint, _review_order_policy, _review_priority, build_review_packet, finalize_review_response, respond_to_review, validate_review_packet
from codex_science.review_receipts import review_receipt_findings, validate_review_receipt


def make_reviewed_run(root: Path) -> Path:
    run = root / "run"
    run.mkdir()
    evidence = run / "evidence.json"
    evidence.write_text('{"estimate": 0.72}\n', encoding="utf-8")
    digest = hashlib.sha256(evidence.read_bytes()).hexdigest()
    manifest = new_manifest(
        "review-source-run",
        "Does the evidence support the bounded association claim?",
        [{"id": "analyze", "description": "Analyze the recorded evidence", "status": "completed"}],
    )
    manifest["inputs"] = [{"id": "study", "identifier": "pmid:12345678", "token": "must-redact"}]
    manifest["code"] = [{"path": "analysis.py", "revision": "abc"}]
    manifest["executions"] = [{"command": "python analysis.py", "exit_code": 0}]
    manifest["environment"] = {"python": "3.12", "API_TOKEN": "must-redact"}
    manifest["claims"] = [{"id": "C1", "text": "The recorded study supports an association.", "evidence": ["evidence.json"], "producer_rationale": "must-exclude"}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "evidence.json", kind="study-evidence", sha256=digest)
    path = run / "manifest.json"
    write_manifest(manifest, path)
    return path


class ReviewerRuntimeTests(unittest.TestCase):
    def test_packet_refuses_conflicting_shared_claim_text(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = make_reviewed_run(Path(tempdir))
            manifest = json.loads(path.read_text(encoding="utf-8"))
            text = manifest["claims"][0]["text"]
            register = {"schema_version": 1, "claims": [{
                "id": "C1", "text": text, "permitted_inference": "Association only.",
                "status": "supported", "falsifier": "An incompatible observation.",
                "uncertainty": "Not reproduced.", "next_action": "Reproduce it.",
            }]}
            register_path = path.parent / "claims.json"
            register_path.write_text(json.dumps(register), encoding="utf-8")
            add_artifact(manifest, "claims.json", kind="claim-register",
                         sha256=hashlib.sha256(register_path.read_bytes()).hexdigest())
            for manifest_text in (text, "  " + text.replace(" ", " \n\t") + "  ", "", "   ", None):
                manifest["claims"][0]["text"] = manifest_text
                write_manifest(manifest, path)
                self.assertEqual(text, build_review_packet(path, review_modes=["record"])["claims"][0]["text"])
            manifest["claims"][0]["text"] = "The study establishes a different conclusion."
            write_manifest(manifest, path)
            with self.assertRaisesRegex(ValueError, "conflicting claim text.*C1"):
                build_review_packet(path, review_modes=["record"])

    def test_reviewer_cli_prepare_tier_and_default(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            for tier, source in ((None, "default"), ("quick", "caller"), ("full", "caller")):
                output = Path(tempdir) / f"{tier or 'default'}.json"
                command = [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "science_reviewer.py"), "prepare", str(manifest), "--mode", "record", "--output", str(output)]
                if tier is not None:
                    command.extend(["--tier", tier])
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(0, result.returncode, result.stderr)
                policy = json.loads(output.read_text(encoding="utf-8"))["review_order_policy"]
                self.assertEqual(tier or "standard", policy["tier"])
                self.assertEqual(source, policy["tier_source"])

            invalid = subprocess.run(
                [sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "science_reviewer.py"), "prepare", str(manifest), "--mode", "record", "--tier", "invalid", "--output", str(Path(tempdir) / "invalid.json")],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(2, invalid.returncode)
            self.assertIn("invalid choice", invalid.stderr)

    def test_priority_order_ties_and_coverage_tiers(self) -> None:
        manifest = {"claims": [], "artifacts": [{"path": "analysis.json"}], "executions": [{"id": "run-analysis", "exit_code": 0}]}
        claims = [
            {"id": "D", "kind": "descriptive", "evidence": ["analysis.json"]},
            {"id": "B", "kind": "descriptive", "evidence": ["study-1"]},
            {"id": "A", "kind": "causal", "evidence": []},
            {"id": "C", "kind": "descriptive", "evidence": []},
            {"id": "E", "kind": "descriptive", "evidence": ["study-2"]},
        ]
        sidecars = {
            "claim_by_id": {claim["id"]: claim for claim in claims},
            "claim_register": {"claims": claims},
            "graph_v2": {
                "nodes": [
                    {"id": "study-1", "type": "study"},
                    {"id": "study-2", "type": "study"},
                    {"id": "analysis.json", "type": "artifact", "path": "analysis.json"},
                ],
                "edges": [
                    {"source": "study-1", "target": "B", "relation": "supports"},
                    {"source": "study-2", "target": "E", "relation": "supports"},
                    {"source": "analysis.json", "target": "D", "relation": "supports"},
                ],
            },
        }
        priority = _review_priority(manifest, claims, sidecars)
        self.assertEqual(
            [{"claim_id": "A", "basis": "synthesis", "priority": 1},
             {"claim_id": "B", "basis": "literature", "priority": 2},
             {"claim_id": "E", "basis": "literature", "priority": 2},
             {"claim_id": "C", "basis": "unknown", "priority": 3},
             {"claim_id": "D", "basis": "data", "priority": 4}],
            priority,
        )
        self.assertEqual(["A", "B", "E", "C", "D"], [row["claim_id"] for row in priority])
        self.assertEqual(["A", "B"], _review_order_policy(priority, "quick", "caller")["suggested_first_claim_ids"])
        self.assertEqual(["A", "B", "E", "C"], _review_order_policy(priority, "standard", "caller")["suggested_first_claim_ids"])
        self.assertEqual(["A", "B", "E", "C", "D"], _review_order_policy(priority, "full", "caller")["suggested_first_claim_ids"])

    def test_unresolvable_and_contradicts_only_supports_are_unknown(self) -> None:
        claims = [
            {"id": "C1", "kind": "descriptive"},
            {"id": "C2", "kind": "descriptive"},
            {"id": "C3", "kind": "descriptive", "evidence": ["result.json"]},
        ]
        manifest = {"claims": claims, "artifacts": [{"path": "result.json"}], "executions": [{"exit_code": 0}]}
        sidecars = {
            "claim_by_id": {claim["id"]: claim for claim in claims},
            "graph_v2": {
                "nodes": [
                    {"id": "study-1", "type": "study"},
                    {"id": "orphan-artifact", "type": "artifact"},
                ],
                "edges": [
                    {"source": "orphan-artifact", "target": "C1", "relation": "supports"},
                    {"source": "study-1", "target": "C2", "relation": "contradicts"},
                ],
            },
        }
        self.assertEqual(
            [
                {"claim_id": "C1", "basis": "unknown", "priority": 3},
                {"claim_id": "C2", "basis": "unknown", "priority": 3},
                {"claim_id": "C3", "basis": "unknown", "priority": 3},
            ],
            _review_priority(manifest, claims, sidecars),
        )

    def test_unrelated_successful_execution_does_not_make_claim_data(self) -> None:
        claims = [{"id": "C1", "kind": "descriptive"}]
        sidecars = {
            "claim_by_id": {"C1": claims[0]},
            "graph_v2": {
                "nodes": [{"id": "analysis-run", "type": "execution"}, {"id": "C1", "type": "claim"}],
                "edges": [{"source": "analysis-run", "target": "C1", "relation": "supports"}],
            },
        }
        manifest = {"claims": claims, "artifacts": [], "executions": [{"id": "unrelated-run", "exit_code": 0}]}

        self.assertEqual("unknown", _review_priority(manifest, claims, sidecars)[0]["basis"])

    def test_claim_supported_by_matching_successful_execution_is_data(self) -> None:
        claims = [{"id": "C1", "kind": "descriptive"}]
        sidecars = {
            "claim_by_id": {"C1": claims[0]},
            "graph_v2": {
                "nodes": [{"id": "analysis-run", "type": "execution"}, {"id": "C1", "type": "claim"}],
                "edges": [{"source": "analysis-run", "target": "C1", "relation": "supports"}],
            },
        }
        manifest = {"claims": claims, "artifacts": [], "executions": [{"id": "analysis-run", "exit_code": 0}]}

        self.assertEqual("data", _review_priority(manifest, claims, sidecars)[0]["basis"])

    def test_artifact_requires_a_matching_successful_output_path_and_hash(self) -> None:
        claims = [{"id": "C1", "kind": "descriptive"}]
        sidecars = {
            "claim_by_id": {"C1": claims[0]},
            "graph_v2": {
                "nodes": [{"id": "result.json", "type": "artifact", "path": "result.json", "sha256": "a" * 64}, {"id": "C1", "type": "claim"}],
                "edges": [{"source": "result.json", "target": "C1", "relation": "supports"}],
            },
        }
        manifest = {
            "claims": claims,
            "artifacts": [{"path": "result.json", "sha256": "a" * 64}],
            "executions": [{"id": "analysis-run", "exit_code": 0, "outputs": [{"path": "result.json", "sha256": "b" * 64}]}],
        }

        self.assertEqual("unknown", _review_priority(manifest, claims, sidecars)[0]["basis"])
        manifest["executions"][0]["outputs"][0]["sha256"] = "a" * 64
        self.assertEqual("data", _review_priority(manifest, claims, sidecars)[0]["basis"])

    def test_tier_validation_provenance_and_suggestions(self) -> None:
        with self.assertRaisesRegex(ValueError, "tier must be one of"):
            build_review_packet(Path("missing-manifest.json"), review_modes=["record"], tier="invalid")
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["claims"] = [
                {"id": f"C{index}", "text": f"Claim {index}", "evidence": []}
                for index in range(1, 6)
            ]
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            quick = build_review_packet(manifest, review_modes=["record"], tier="quick", created_at="2026-10-21T00:00:00Z")
            standard = build_review_packet(manifest, review_modes=["record"], tier="standard", created_at="2026-10-21T00:00:00Z")
            full = build_review_packet(manifest, review_modes=["record"], tier="full", created_at="2026-10-21T00:00:00Z")
            default = build_review_packet(manifest, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            self.assertEqual({"tier": "quick", "tier_source": "caller", "suggested_first_claim_ids": ["C1"], "scope": "Advisory ordering only; every material claim must still be reviewed."}, quick["review_order_policy"])
            self.assertEqual(["C1", "C2", "C3"], standard["review_order_policy"]["suggested_first_claim_ids"])
            self.assertEqual(["C1", "C2", "C3", "C4", "C5"], full["review_order_policy"]["suggested_first_claim_ids"])
            self.assertEqual("caller", standard["review_order_policy"]["tier_source"])
            self.assertEqual("default", default["review_order_policy"]["tier_source"])
            bad_tier_packet = dict(quick)
            bad_policy = dict(quick["review_order_policy"])
            bad_policy["tier"] = "legacy"
            bad_tier_packet["review_order_policy"] = bad_policy
            with self.assertRaisesRegex(ValueError, "invalid review_order_policy"):
                validate_review_packet(bad_tier_packet)
            duplicate_priority_packet = dict(quick)
            duplicate_priority_packet["review_priority"] = [
                *quick["review_priority"], dict(quick["review_priority"][0])
            ]
            with self.assertRaisesRegex(ValueError, "claim IDs must be non-empty and unique"):
                validate_review_packet(duplicate_priority_packet)

    def test_quick_tier_does_not_relax_full_response_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["claims"].append({"id": "C2", "text": "Second claim.", "evidence": []})
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            packet = build_review_packet(manifest, review_modes=["record"], tier="quick", created_at="2026-10-21T00:00:00Z")
            artifact = packet["artifacts"][0]
            response = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "reviewer",
                "independent": True,
                "review_modes": ["record"],
                "reviewed_claim_ids": ["C1"],
                "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                "findings": [],
                "limitations": ["Review is incomplete."],
            }
            with self.assertRaisesRegex(ValueError, "omits material claims"):
                finalize_review_response(packet, response)

    def test_packet_fields_are_deterministic_and_legacy_packets_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            first = build_review_packet(manifest, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            second = build_review_packet(manifest, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            self.assertEqual(first, second)
            self.assertEqual(["C1"], first["review_order_policy"]["suggested_first_claim_ids"])
            self.assertEqual("default", first["review_order_policy"]["tier_source"])
            legacy = dict(first)
            legacy.pop("review_priority")
            legacy.pop("review_order_policy")
            legacy.pop("review_task_id")
            legacy.pop("fingerprint")
            fingerprint = _fingerprint(legacy)
            legacy["review_task_id"] = f"review-task-{fingerprint[:20]}"
            legacy["fingerprint"] = fingerprint
            validate_review_packet(legacy)

    def test_manifest_claim_kind_must_be_a_known_string(self) -> None:
        for kind in ("predictive", ["causal"]):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tempdir:
                manifest = make_reviewed_run(Path(tempdir))
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                payload["claims"][0]["kind"] = kind
                manifest.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Invalid claim kind for C1"):
                    build_review_packet(manifest, review_modes=["record"])

    def test_kind_routing_does_not_mutate_custom_questions_or_duplicate_on_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["claims"][0]["kind"] = "causal"
            manifest.write_text(json.dumps(payload), encoding="utf-8")

            first = build_review_packet(manifest, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            questions = list(first["review_questions"])
            second = build_review_packet(
                manifest, review_modes=["record"], review_questions=questions,
                created_at="2026-10-21T00:00:00Z",
            )
            self.assertEqual(first["review_questions"], second["review_questions"])
            self.assertEqual(first["review_questions"], questions)

            custom = ["Check the custom review protocol."]
            custom_packet = build_review_packet(
                manifest, review_modes=["record"], review_questions=custom,
                created_at="2026-10-21T00:00:00Z",
            )
            self.assertEqual(["Check the custom review protocol."], custom_packet["review_questions"])
            self.assertEqual(["Check the custom review protocol."], custom)

    def test_packet_is_hash_bound_and_excludes_producer_only_context(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record", "method"],
                created_at="2026-07-21T00:00:00Z",
            )
            validate_review_packet(packet)
            serialized = json.dumps(packet)
            self.assertNotIn("must-exclude", serialized)
            self.assertNotIn("must-redact", serialized)
            self.assertIn("[REDACTED]", serialized)
            self.assertEqual(["C1"], packet["material_claim_ids"])
            self.assertEqual(1, len(packet["artifacts"]))
            self.assertTrue(packet["independent_required"])

    def test_complete_independent_response_builds_passed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record", "method"],
                created_at="2026-07-21T00:00:00Z",
            )
            artifact = packet["artifacts"][0]
            response = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "independent-reviewer-1",
                "independent": True,
                "review_modes": ["record", "method"],
                "reviewed_claim_ids": ["C1"],
                "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                "findings": [],
                "limitations": ["The source study is not independently reproduced in this review."],
                "status": "passed"
            }
            receipt = finalize_review_response(packet, response)
            validate_review_receipt(receipt)
            self.assertEqual("passed", receipt["status"])
            self.assertTrue(receipt["independent"])
            self.assertEqual(packet["review_task_id"], receipt["review_task_id"])

            response["reviewer"] = None
            with self.assertRaisesRegex(ValueError, "reviewer is required"):
                finalize_review_response(packet, response)

            response["reviewer"] = "independent-reviewer-1"
            response["findings"] = [
                {
                    "id": "F-not-applicable",
                    "severity": "major",
                    "code": "not-applicable-control",
                    "message": "This control does not apply to the reviewed design.",
                    "resolution_status": "not-applicable",
                    "evidence": [],
                    "required_action": "",
                }
            ]
            receipt = finalize_review_response(packet, response)
            self.assertEqual(
                [],
                review_receipt_findings(
                    receipt,
                    {artifact["path"]: artifact["sha256"]},
                ),
            )

    def test_nonindependent_or_incomplete_review_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(
                manifest,
                review_modes=["record"],
                created_at="2026-07-21T00:00:00Z",
            )
            artifact = packet["artifacts"][0]
            response = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "producer-second-pass",
                "independent": False,
                "review_modes": ["record"],
                "reviewed_claim_ids": [],
                "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                "findings": [],
                "limitations": ["Same producer context."],
                "blocked_reason": "No independent reviewer was available.",
                "status": "passed"
            }
            receipt = finalize_review_response(packet, response)
            self.assertEqual("findings", receipt["status"])
            codes = {item["code"] for item in receipt["findings"]}
            self.assertIn("review-not-independent", codes)
            self.assertIn("incomplete-review-coverage", codes)

    def test_response_cannot_substitute_artifact_hash_or_unknown_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            packet = build_review_packet(manifest, review_modes=["record"], created_at="2026-07-21T00:00:00Z")
            base = {
                "schema_version": 1,
                "review_task_id": packet["review_task_id"],
                "packet_fingerprint": packet["fingerprint"],
                "reviewer": "reviewer",
                "independent": True,
                "review_modes": ["record"],
                "reviewed_claim_ids": ["C1"],
                "reviewed_artifacts": [{"path": packet["artifacts"][0]["path"], "sha256": "0" * 64}],
                "findings": [],
                "limitations": ["Limited."],
                "status": "passed"
            }
            with self.assertRaisesRegex(ValueError, "does not match"):
                finalize_review_response(packet, base)
            changed = dict(base)
            changed["reviewed_claim_ids"] = ["UNKNOWN"]
            changed["reviewed_artifacts"] = [{"path": packet["artifacts"][0]["path"], "sha256": packet["artifacts"][0]["sha256"]}]
            with self.assertRaisesRegex(ValueError, "unknown claims"):
                finalize_review_response(packet, changed)


    def _respond_setup(self, tempdir: str) -> tuple[Path, dict]:
        manifest = make_reviewed_run(Path(tempdir))
        packet = build_review_packet(manifest, review_modes=["record", "method"], created_at="2026-07-21T00:00:00Z")
        task = manifest.parent / "review-task.json"
        task.write_text(json.dumps(packet), encoding="utf-8")
        return task, packet

    def _respond(self, task: Path, *extra: str) -> subprocess.CompletedProcess:
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_reviewer.py"
        base = ["--reviewer", "r1", "--status", "passed", "--limitation", "Not reproduced."]
        if "--not-independent" not in extra:
            base.append("--independent")
        return subprocess.run([sys.executable, str(script), "respond", str(task), *base, *extra], capture_output=True, text=True, check=False)

    def test_respond_builds_passed_response_from_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            task, packet = self._respond_setup(tempdir)
            result = self._respond(task, "--reviewed-all")
            self.assertEqual(0, result.returncode, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual("passed", summary["effective_status"])
            self.assertEqual((1, 1, 0), (summary["reviewed_artifacts"], summary["reviewed_claims"], summary["findings"]))
            response = json.loads((task.parent / "reviewer-response.json").read_text(encoding="utf-8"))
            self.assertEqual([{"path": a["path"], "sha256": a["sha256"]} for a in packet["artifacts"]], response["reviewed_artifacts"])
            self.assertEqual(packet["fingerprint"], response["packet_fingerprint"])
            self.assertEqual("passed", finalize_review_response(packet, response)["status"])

    def test_respond_fills_evidence_hash_and_reports_effective_status(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            task, packet = self._respond_setup(tempdir)
            path = packet["artifacts"][0]["path"]
            findings = Path(tempdir) / "findings.json"
            findings.write_text(json.dumps([{"id": "F1", "severity": "major", "code": "x", "message": "m", "evidence": [{"artifact_path": path}]}]), encoding="utf-8")
            result = self._respond(task, "--reviewed", path, "--findings", str(findings))
            self.assertEqual(0, result.returncode, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(("passed", "findings", 1), (summary["requested_status"], summary["effective_status"], summary["findings"]))
            response = json.loads((task.parent / "reviewer-response.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["artifacts"][0]["sha256"], response["findings"][0]["evidence"][0]["artifact_sha256"])

    def test_respond_help_describes_findings_format(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "science_reviewer.py"
        result = subprocess.run([sys.executable, str(script), "respond", "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(0, result.returncode, result.stderr)
        text = " ".join(result.stdout.split())
        for key in ("id", "severity", "code", "message", "artifact_path", "json_pointer"):
            self.assertIn(key, text)

    def test_respond_refuses_bad_inputs_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            task, packet = self._respond_setup(tempdir)
            path = packet["artifacts"][0]["path"]
            response_path = task.parent / "reviewer-response.json"
            findings = Path(tempdir) / "findings.json"
            findings.write_text(json.dumps([
                {"id": "F1", "severity": "minor", "code": "x", "message": "m", "evidence": [{"artifact_path": "nope.json"}, {"artifact_path": path, "artifact_sha256": "0" * 64}]},
            ]), encoding="utf-8")
            result = self._respond(task, "--reviewed", "ghost.json", "--findings", str(findings))
            self.assertEqual(1, result.returncode)
            for text in ("error:", "ghost.json", "nope.json", "hash differs"):
                self.assertIn(text, result.stderr)
            self.assertFalse(response_path.exists())
            manifest_path = task.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["claims"].append({"id": "C2", "text": "Second claim.", "evidence": ["evidence.json"]})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            two = build_review_packet(manifest_path, review_modes=["record"], created_at="2026-07-21T00:00:00Z")
            task.write_text(json.dumps(two), encoding="utf-8")
            result = self._respond(task, "--reviewed-all", "--claim", "C1")
            self.assertEqual(1, result.returncode)
            self.assertIn("--blocked-reason is required", result.stderr)
            self.assertFalse(response_path.exists())
            result = self._respond(task, "--reviewed-all", "--claim", "C1", "--blocked-reason", "C2 out of scope")
            self.assertEqual("findings", json.loads(result.stdout)["effective_status"])
            response_path.unlink()
            task.write_text(json.dumps(packet), encoding="utf-8")
            (task.parent / path).write_text("changed\n", encoding="utf-8")
            result = self._respond(task, "--reviewed-all")
            self.assertEqual(1, result.returncode)
            self.assertIn("stale", result.stderr)
            self.assertFalse(response_path.exists())

    def test_respond_requires_status_and_independence_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            task, _packet = self._respond_setup(tempdir)
            script = Path(__file__).resolve().parents[1] / "scripts" / "science_reviewer.py"
            for args in (["--status", "passed"], ["--independent"]):
                result = subprocess.run([sys.executable, str(script), "respond", str(task), "--reviewer", "r", "--limitation", "l", "--reviewed-all", *args], capture_output=True, text=True, check=False)
                self.assertEqual(2, result.returncode)

    def test_respond_refuses_unsafe_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            task, packet = self._respond_setup(tempdir)
            run = task.parent
            link = run / "link.json"
            link.symlink_to(Path(tempdir) / "elsewhere.json")
            for target in (link, Path(tempdir) / "outside.json", task, run / "manifest.json", run / packet["artifacts"][0]["path"]):
                before = target.read_bytes() if target.is_file() and not target.is_symlink() else None
                result = self._respond(task, "--reviewed-all", "--output", str(target))
                self.assertEqual(1, result.returncode, target)
                self.assertIn("error:", result.stderr)
                if before is not None:
                    self.assertEqual(before, target.read_bytes())
            self.assertFalse((Path(tempdir) / "elsewhere.json").exists())
            self.assertFalse((Path(tempdir) / "outside.json").exists())

    def test_respond_refuses_overwriting_renamed_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            manifest = make_reviewed_run(Path(tempdir))
            bundle = manifest.rename(manifest.with_name("bundle.json"))
            packet = build_review_packet(bundle, review_modes=["record"], created_at="2026-07-21T00:00:00Z")
            task = bundle.parent / "review-task.json"
            task.write_text(json.dumps(packet), encoding="utf-8")
            before = bundle.read_bytes()
            result = self._respond(task, "--reviewed-all", "--output", str(bundle))
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("overwrite a packet or manifest file", result.stderr)
            self.assertEqual(before, bundle.read_bytes())


def resign(packet: dict, mutate) -> dict:
    """Apply ``mutate`` to a copy of the packet body and recompute the hash binding so only the targeted rule can fail."""
    material = copy.deepcopy(packet)
    material.pop("review_task_id")
    material.pop("fingerprint")
    mutate(material)
    fingerprint = _fingerprint(material)
    return {**material, "review_task_id": f"review-task-{fingerprint[:20]}", "fingerprint": fingerprint}


def valid_response(packet: dict) -> dict:
    artifact = packet["artifacts"][0]
    return {
        "schema_version": 1,
        "review_task_id": packet["review_task_id"],
        "packet_fingerprint": packet["fingerprint"],
        "reviewer": "reviewer",
        "independent": True,
        "review_modes": ["record"],
        "reviewed_claim_ids": ["C1"],
        "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
        "findings": [],
        "limitations": ["Limited."],
        "status": "passed",
    }


class ReviewerRuntimeRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tempdir = tempfile.TemporaryDirectory()
        cls.manifest = make_reviewed_run(Path(cls._tempdir.name))
        cls.packet = build_review_packet(cls.manifest, review_modes=["record", "method"], created_at="2026-07-21T00:00:00Z")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tempdir.cleanup()

    def assertPacketRejected(self, mutate, message: str) -> None:
        with self.assertRaisesRegex(ValueError, message):
            validate_review_packet(resign(self.packet, mutate))

    def test_base_packet_and_response_are_valid(self) -> None:
        validate_review_packet(self.packet)
        self.assertEqual("passed", finalize_review_response(self.packet, valid_response(self.packet))["status"])

    def test_packet_schema_version_must_be_one(self) -> None:
        for version in (2, 0, None, "1"):
            with self.subTest(version=version):
                self.assertPacketRejected(lambda m, v=version: m.__setitem__("schema_version", v), "unsupported review packet schema")

    def test_packet_required_text_fields_and_digest(self) -> None:
        for field in ("review_task_id", "source_run_id", "source_manifest_path", "source_manifest_sha256", "created_at", "evidence_boundary"):
            for value in (None, "", "  ", 7):
                with self.subTest(field=field, value=value):
                    packet = {**self.packet, field: value}
                    with self.assertRaisesRegex(ValueError, f"{field} is required"):
                        validate_review_packet(packet)
        for digest in ("abc", "g" * 64, "a" * 63, "a" * 65):
            with self.subTest(digest=digest):
                self.assertPacketRejected(lambda m, d=digest: m.__setitem__("source_manifest_sha256", d), "must be a SHA-256 digest")

    def test_packet_modes_must_be_nonempty_known_list(self) -> None:
        for modes in ([], ["nope"], ["record", "nope"], "record", None):
            with self.subTest(modes=modes):
                self.assertPacketRejected(lambda m, v=modes: m.__setitem__("review_modes", v), "invalid review packet modes")

    def test_packet_artifacts_and_claim_ids_must_be_lists(self) -> None:
        for field in ("artifacts", "material_claim_ids"):
            for value in (None, "C1", {"C1": 1}):
                with self.subTest(field=field, value=value):
                    self.assertPacketRejected(lambda m, f=field, v=value: m.__setitem__(f, v), "must be lists")

    def test_review_priority_shape_is_validated(self) -> None:
        row = {"claim_id": "C1", "basis": "data", "priority": 4}
        cases = {
            "not a list": {"C1": row},
            "non-mapping row": ["C1"],
            "extra key": [{**row, "note": "x"}],
            "missing key": [{"claim_id": "C1", "basis": "data"}],
            "unknown basis": [{**row, "basis": "vibes"}],
            "wrong priority": [{**row, "priority": 1}],
            "bool priority": [{"claim_id": "C1", "basis": "synthesis", "priority": True}],
            "float priority": [{**row, "priority": 4.0}],
        }
        for label, rows in cases.items():
            with self.subTest(label):
                self.assertPacketRejected(lambda m, v=rows: m.__setitem__("review_priority", v), "invalid review_priority$")

    def test_review_priority_claim_ids_must_be_unique_nonempty_strings(self) -> None:
        for ids in ([""], ["  "], [3], ["C1", "C1"]):
            with self.subTest(ids=ids):
                def mutate(m, ids=ids):
                    m["review_priority"] = [{"claim_id": claim_id, "basis": "data", "priority": 4} for claim_id in ids]
                self.assertPacketRejected(mutate, "claim IDs must be non-empty and unique")

    def test_review_priority_must_be_ordered_and_cover_material_claims(self) -> None:
        def unordered(m):
            m["material_claim_ids"] = ["A", "B"]
            m["review_priority"] = [{"claim_id": "A", "basis": "data", "priority": 4}, {"claim_id": "B", "basis": "synthesis", "priority": 1}]
        self.assertPacketRejected(unordered, "not deterministically ordered")

        def tie_unordered(m):
            m["material_claim_ids"] = ["A", "B"]
            m["review_priority"] = [{"claim_id": "B", "basis": "data", "priority": 4}, {"claim_id": "A", "basis": "data", "priority": 4}]
        self.assertPacketRejected(tie_unordered, "not deterministically ordered")

        def missing(m):
            m["material_claim_ids"] = ["C1", "C2"]
        self.assertPacketRejected(missing, "must cover material claims")

        def extra(m):
            m["material_claim_ids"] = []
        self.assertPacketRejected(extra, "must cover material claims")

    def test_review_order_policy_shape_is_validated(self) -> None:
        cases = {
            "not a mapping": lambda p: "standard",
            "unknown tier": lambda p: {**p, "tier": "huge"},
            "non-string tier": lambda p: {**p, "tier": ["full"]},
            "unknown tier source": lambda p: {**p, "tier_source": "magic"},
            "suggested not a list": lambda p: {**p, "suggested_first_claim_ids": "C1"},
            "wrong scope": lambda p: {**p, "scope": "Every claim is optional."},
        }
        for label, build in cases.items():
            with self.subTest(label):
                self.assertPacketRejected(lambda m, b=build: m.__setitem__("review_order_policy", b(m["review_order_policy"])), "invalid review_order_policy$")

    def test_review_order_policy_suggested_ids_are_constrained(self) -> None:
        cases = {
            "blank id": ["  "],
            "non-string id": [1],
            "duplicate id": ["C1", "C1"],
            "id outside material claims": ["C9"],
        }
        for label, suggested in cases.items():
            with self.subTest(label):
                def mutate(m, suggested=suggested):
                    m["review_order_policy"] = {**m["review_order_policy"], "suggested_first_claim_ids": suggested}
                self.assertPacketRejected(mutate, "invalid suggested review order claim IDs")

        def default_with_full_tier(m):
            m["review_order_policy"] = {**m["review_order_policy"], "tier": "full", "tier_source": "default"}
        self.assertPacketRejected(default_with_full_tier, "invalid suggested review order claim IDs")

    def test_review_order_policy_must_match_priority(self) -> None:
        def mutate(m):
            m["review_order_policy"] = {**m["review_order_policy"], "suggested_first_claim_ids": []}
        self.assertPacketRejected(mutate, "does not match review_priority")

    def test_packet_fingerprint_and_task_id_must_bind_the_body(self) -> None:
        tampered = {**self.packet, "created_at": "2030-01-01T00:00:00Z"}
        wrong_task = {**self.packet, "review_task_id": "review-task-" + "0" * 20}
        no_fingerprint = {key: value for key, value in self.packet.items() if key != "fingerprint"}
        for label, packet in (("body changed", tampered), ("task id changed", wrong_task), ("fingerprint absent", no_fingerprint)):
            with self.subTest(label), self.assertRaisesRegex(ValueError, "fingerprint or task ID mismatch"):
                validate_review_packet(packet)

    def test_finalize_rejects_invalid_packet_before_reading_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported review packet schema"):
            finalize_review_response({**self.packet, "schema_version": 2}, valid_response(self.packet))

    def assertResponseRejected(self, message: str, **changes) -> None:
        response = {**valid_response(self.packet), **changes}
        with self.assertRaisesRegex(ValueError, message):
            finalize_review_response(self.packet, response)

    def test_finalize_response_schema_and_packet_binding(self) -> None:
        self.assertResponseRejected("unsupported review response schema", schema_version=2)
        for field, value in (("review_task_id", "review-task-other"), ("review_task_id", None), ("packet_fingerprint", "0" * 64), ("packet_fingerprint", None)):
            with self.subTest(field=field, value=value):
                self.assertResponseRejected("covers a different packet", **{field: value})
        for reviewer in (None, "", "   "):
            with self.subTest(reviewer=reviewer):
                self.assertResponseRejected("reviewer is required", reviewer=reviewer)

    def test_finalize_independent_must_be_a_boolean(self) -> None:
        for value in ("true", 1, 0, None):
            with self.subTest(value=value):
                self.assertResponseRejected("independent must be a boolean", independent=value)

    def test_finalize_review_modes_must_be_nonempty_subset_of_packet(self) -> None:
        self.assertResponseRejected("response review_modes must be a list", review_modes="record")
        for modes in ([], ["source"], ["record", "reproduction"]):
            with self.subTest(modes=modes):
                self.assertResponseRejected("empty or exceed the packet", review_modes=modes)
        self.assertResponseRejected("response review mode is required", review_modes=["record", ""])

    def test_finalize_claim_and_artifact_lists_are_typed(self) -> None:
        self.assertResponseRejected("reviewed_claim_ids must be a list", reviewed_claim_ids="C1")
        self.assertResponseRejected("reviewed_artifacts must be a list", reviewed_artifacts={"path": "x"})
        self.assertResponseRejected("reviewed artifact 0 must be an object", reviewed_artifacts=["evidence.json"])
        self.assertResponseRejected("reviewed artifact 0 path is required", reviewed_artifacts=[{"sha256": "0" * 64}])
        self.assertResponseRejected("must be a SHA-256 digest", reviewed_artifacts=[{"path": "evidence.json", "sha256": "xyz"}])
        self.assertResponseRejected("does not match packet: ghost.json", reviewed_artifacts=[{"path": "ghost.json", "sha256": self.packet["artifacts"][0]["sha256"]}])

    def test_finalize_requires_at_least_one_covered_artifact(self) -> None:
        self.assertResponseRejected("at least one artifact", reviewed_artifacts=[])

    def test_finalize_requires_explicit_findings_even_for_clean_reviews(self) -> None:
        response = valid_response(self.packet)
        self.assertEqual("passed", finalize_review_response(self.packet, response)["status"])
        del response["findings"]
        with self.assertRaisesRegex(ValueError, "findings must be a list"):
            finalize_review_response(self.packet, response)

    def test_finalize_rejects_explicit_affected_claims_outside_packet(self) -> None:
        finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m"}
        receipt = finalize_review_response(self.packet, {**valid_response(self.packet),
            "findings": [{**finding, "affected_claim_id": "C1"}]})
        self.assertEqual("passed", receipt["status"])
        self.assertEqual("passed", finalize_review_response(self.packet, {
            **valid_response(self.packet), "findings": [finding]})["status"])
        for claim_id in ("C999", "", "  ", None, 0, [], {}):
            with self.subTest(claim_id=claim_id):
                self.assertResponseRejected("affected_claim_id", findings=[
                    {**finding, "affected_claim_id": claim_id}])

    def test_finalize_findings_must_be_a_list_of_valid_objects(self) -> None:
        self.assertResponseRejected("findings must be a list", findings={"id": "F1"})
        self.assertResponseRejected("all findings must be objects", findings=["F1"])
        good = {"id": "F1", "severity": "minor", "code": "c", "message": "m"}
        self.assertResponseRejected("all findings must be objects", findings=[good, None])
        cases = (
            ({"id": ""}, "finding 0 id is required"),
            ({"severity": "fatal"}, "invalid finding severity: fatal"),
            ({"code": " "}, "code is required"),
            ({"message": None}, "message is required"),
            ({"resolution_status": "later"}, "invalid finding resolution status: later"),
            ({"evidence": "evidence.json"}, "evidence must be a list"),
        )
        for change, message in cases:
            with self.subTest(change=change):
                self.assertResponseRejected(message, findings=[{**good, **change}])

    def test_finalize_finding_evidence_path_must_be_in_packet(self) -> None:
        finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m"}
        for path in ("unreviewed.txt", "", 0, None, [], {}):
            with self.subTest(path=path):
                evidence = [{"artifact_path": path, "artifact_sha256": "0" * 64}]
                with self.assertRaises(ValueError) as caught:
                    finalize_review_response(self.packet, {**valid_response(self.packet), "findings": [{**finding, "evidence": evidence}]})
                self.assertEqual(f"finding F1 evidence 0 path not in packet: {str(path) or '<missing>'}", str(caught.exception))
        for digest in ("0" * 64, None):
            with self.subTest(missing_path=digest):
                self.assertResponseRejected("finding F1 evidence 0 path not in packet: <missing>", findings=[{**finding, "evidence": [{"artifact_sha256": digest}]}])
        path = self.packet["artifacts"][0]["path"]
        findings = [{**finding, "evidence": [{"artifact_path": "unreviewed.txt"}]},
                    {**finding, "id": "F2", "evidence": [{"artifact_path": path, "artifact_sha256": "0" * 64}]}]
        with self.assertRaises(ValueError) as caught:
            finalize_review_response(self.packet, {**valid_response(self.packet), "findings": findings})
        self.assertEqual(f"finding F1 evidence 0 path not in packet: unreviewed.txt; finding F2 evidence 0 hash differs from packet: {path}", str(caught.exception))

    def test_finalize_finding_evidence_hash_must_match_packet(self) -> None:
        path = self.packet["artifacts"][0]["path"]
        finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m"}
        for digest in ("0" * 64, "", "xyz", "0" * 63, "0" * 65, None, 0, [], {}):
            with self.subTest(digest=digest):
                evidence = [{"artifact_path": path, "artifact_sha256": digest}]
                with self.assertRaises(ValueError) as caught:
                    finalize_review_response(self.packet, {**valid_response(self.packet), "findings": [{**finding, "evidence": evidence}]})
                self.assertEqual(f"finding F1 evidence 0 hash differs from packet: {path}", str(caught.exception))

    def test_finalize_fills_missing_finding_evidence_hash_without_mutating_response(self) -> None:
        artifact = self.packet["artifacts"][0]
        evidence = [{"artifact_path": artifact["path"], "line_range": [1, 1]},
                    {"artifact_path": artifact["path"], "artifact_sha256": artifact["sha256"].upper()}]
        finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m", "evidence": evidence}
        response = {**valid_response(self.packet), "findings": [finding]}
        original = copy.deepcopy(response)
        receipt = finalize_review_response(self.packet, response)
        expected = [{**evidence[0], "artifact_sha256": artifact["sha256"]}, evidence[1]]
        self.assertEqual(expected, receipt["findings"][0]["evidence"])
        self.assertEqual(original, response)
        self.assertEqual(receipt, finalize_review_response(self.packet, response))

    def test_finalize_url_only_evidence_is_refused(self) -> None:
        entries = ({"url": "https://example.org/study", "locator": "Table 1"}, {},
                   {"path": self.packet["artifacts"][0]["path"], "sha256": self.packet["artifacts"][0]["sha256"]})
        for entry in entries:
            with self.subTest(entry=entry):
                finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m", "evidence": [entry]}
                response = {**valid_response(self.packet), "findings": [finding]}
                original = copy.deepcopy(response)
                with self.assertRaises(ValueError) as caught:
                    finalize_review_response(self.packet, response)
                self.assertEqual("finding F1 evidence 0 path not in packet: <missing>", str(caught.exception))
                self.assertEqual(original, response)

    def test_finalize_nonobject_evidence_is_refused(self) -> None:
        for entry in (None, 0, False, "", "evidence.json", []):
            with self.subTest(entry=entry):
                finding = {"id": "F1", "severity": "minor", "code": "c", "message": "m", "evidence": [entry, {}]}
                with self.assertRaises(ValueError) as caught:
                    finalize_review_response(self.packet, {**valid_response(self.packet), "findings": [finding]})
                self.assertEqual("finding F1 evidence 0 must be an object; finding F1 evidence 1 path not in packet: <missing>", str(caught.exception))

    def test_finalize_status_must_be_known(self) -> None:
        for status in ("done", "", None, "PASSED"):
            with self.subTest(status=status):
                self.assertResponseRejected("invalid review response status", status=status)
        for status in ("passed", "findings", "blocked"):
            with self.subTest(accepted=status):
                self.assertEqual(status, finalize_review_response(self.packet, {**valid_response(self.packet), "status": status})["status"])

    def test_finalize_requires_nonempty_limitations(self) -> None:
        self.assertResponseRejected("must state limitations", limitations=[])
        response = valid_response(self.packet)
        del response["limitations"]
        with self.assertRaisesRegex(ValueError, "must state limitations"):
            finalize_review_response(self.packet, response)
        for value in ("Limited.", [" "], [3], ["ok", ""], None):
            with self.subTest(value=value):
                self.assertResponseRejected("limitations must be a non-empty string list", limitations=value)

    def test_unresolved_blocking_finding_overrides_requested_pass(self) -> None:
        finding = {"id": "F1", "severity": "critical", "code": "c", "message": "m"}
        receipt = finalize_review_response(self.packet, {**valid_response(self.packet), "findings": [finding]})
        self.assertEqual("findings", receipt["status"])
        resolved = finalize_review_response(self.packet, {**valid_response(self.packet), "findings": [{**finding, "resolution_status": "resolved"}]})
        self.assertEqual("passed", resolved["status"])


class RespondToReviewRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.root = Path(tempdir.name)
        manifest = make_reviewed_run(self.root)
        self.packet = build_review_packet(manifest, review_modes=["record", "method"], created_at="2026-07-21T00:00:00Z")
        self.task = manifest.parent / "review-task.json"
        self.task.write_text(json.dumps(self.packet), encoding="utf-8")
        self.response_path = self.task.parent / "reviewer-response.json"
        self.artifact_path = self.packet["artifacts"][0]["path"]

    def respond(self, **overrides):
        arguments = {"reviewer": "r1", "independent": True, "status": "passed", "limitations": ["Not reproduced."], "reviewed_all": True}
        arguments.update(overrides)
        return respond_to_review(self.task, **arguments)

    def assertRefused(self, message: str, **overrides) -> None:
        with self.assertRaisesRegex(ValueError, message):
            self.respond(**overrides)
        self.assertFalse(self.response_path.exists())

    def write_findings(self, text: str) -> Path:
        path = self.root / "findings.json"
        path.write_text(text, encoding="utf-8")
        return path

    def test_baseline_writes_response(self) -> None:
        summary = self.respond()
        self.assertEqual("passed", summary["effective_status"])
        self.assertTrue(self.response_path.exists())

    def test_reviewed_all_and_reviewed_are_mutually_exclusive_and_required(self) -> None:
        self.assertRefused("pass exactly one of --reviewed-all or --reviewed PATH", reviewed_all=True, reviewed_paths=[self.artifact_path])
        self.assertRefused("pass exactly one of --reviewed-all or --reviewed PATH", reviewed_all=False, reviewed_paths=None)
        self.assertRefused("pass exactly one of --reviewed-all or --reviewed PATH", reviewed_all=False, reviewed_paths=[])

    def test_unknown_modes_and_claims_are_refused(self) -> None:
        self.assertRefused("modes not in packet: source", modes=["record", "source"])
        self.assertRefused("claims not in packet: C9", claim_ids=["C1", "C9"])
        self.assertRefused("claims not in packet: C9", claim_ids=["C9"], blocked_reason="narrowed")

    def test_narrowed_claims_need_nonblank_blocked_reason(self) -> None:
        manifest_path = self.task.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["claims"].append({"id": "C2", "text": "Second claim.", "evidence": ["evidence.json"]})
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        two = build_review_packet(manifest_path, review_modes=["record"], created_at="2026-07-21T00:00:00Z")
        self.task.write_text(json.dumps(two), encoding="utf-8")
        for reason in ("", "   "):
            with self.subTest(reason=reason):
                self.assertRefused("--blocked-reason is required", claim_ids=["C1"], blocked_reason=reason)

    def test_findings_file_read_and_parse_failures_are_reported(self) -> None:
        missing = self.root / "absent.json"
        self.assertRefused("findings file unreadable", findings_path=missing)
        self.assertRefused("findings file unreadable", findings_path=self.write_findings("{not json"))
        self.assertRefused("findings file unreadable", findings_path=self.write_findings(""))
        self.assertRefused("findings file unreadable", findings_path=self.root)

    def test_findings_file_must_be_a_list_of_objects(self) -> None:
        for text in ('{"id": "F1"}', '"F1"', "null", "3"):
            with self.subTest(text=text):
                self.assertRefused("findings file must contain a JSON list", findings_path=self.write_findings(text))
        self.assertRefused("finding 0 must be an object", findings_path=self.write_findings('["F1"]'))
        self.assertRefused("finding 1 must be an object", findings_path=self.write_findings(json.dumps([{"id": "F1", "severity": "minor", "code": "c", "message": "m"}, None])))

    def test_findings_evidence_entries_are_checked_against_packet(self) -> None:
        base = {"id": "F1", "severity": "minor", "code": "c", "message": "m"}
        cases = (
            ([{"artifact_sha256": "0" * 64}], "evidence 0 path not in packet: <missing>"),
            ([{"artifact_path": "ghost.json"}], "evidence 0 path not in packet: ghost.json"),
            (["evidence.json"], "evidence 0 must be an object"),
            ([{"artifact_path": self.artifact_path, "artifact_sha256": "0" * 64}], "hash differs from packet"),
        )
        for evidence, message in cases:
            with self.subTest(message=message):
                self.assertRefused(message, findings_path=self.write_findings(json.dumps([{**base, "evidence": evidence}])))

    def test_finalize_rejections_surface_through_respond_without_writing(self) -> None:
        self.assertRefused("invalid review response status", status="done")
        self.assertRefused("must state limitations", limitations=[])
        self.assertRefused("limitations must be a non-empty string list", limitations=[" "])
        self.assertRefused("invalid finding severity: fatal", findings_path=self.write_findings(json.dumps([{"id": "F1", "severity": "fatal", "code": "c", "message": "m"}])))

    def test_all_problems_are_reported_together(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.respond(reviewed_all=False, reviewed_paths=["ghost.json"], modes=["source"], claim_ids=["C9"], findings_path=self.root / "absent.json")
        for fragment in ("reviewed paths not in packet: ghost.json", "modes not in packet: source", "claims not in packet: C9", "findings file unreadable"):
            self.assertIn(fragment, str(caught.exception))
        self.assertFalse(self.response_path.exists())


if __name__ == "__main__":
    unittest.main()
