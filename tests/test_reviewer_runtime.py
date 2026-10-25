import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.reviewer_runtime import _fingerprint, _review_order_policy, _review_priority, build_review_packet, finalize_review_response, validate_review_packet
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

if __name__ == "__main__":
    unittest.main()
