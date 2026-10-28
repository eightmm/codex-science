from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.review_receipts import canonical_sha256  # noqa: E402
from codex_science.review_receipts import build_review_receipt  # noqa: E402
from codex_science.artifact_store import describe_directory  # noqa: E402
from codex_science.review import review_manifest  # noqa: E402
CLI = ROOT / "scripts" / "package_run.py"
EXAMPLE = ROOT / "examples" / "literature-review-reviewed-run"


class PackageRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run_dir = Path(self.temp.name) / "run"
        shutil.copytree(EXAMPLE, self.run_dir)

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(CLI), *args], text=True, capture_output=True, check=False)

    def _make_unreviewed_run(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        removed = [item for item in manifest["artifacts"] if item.get("kind") in {"review-receipt", "review-receipt-v2"}]
        manifest["artifacts"] = [item for item in manifest["artifacts"] if item not in removed]
        for item in removed:
            (self.run_dir / item["path"]).unlink()
        manifest["review"] = {"status": "pending", "findings": []}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    def test_validator_refuses_review_output_over_evidence(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        tree = self.run_dir / "tree"
        tree.mkdir()
        (tree / "data.json").write_text("{}")
        descriptor = describe_directory(tree)
        descriptor_path = self.run_dir / "tree.descriptor.json"
        descriptor_path.write_text(json.dumps(descriptor.to_dict()))
        manifest["artifacts"].append({"path": "tree", "kind": "data", "artifact_type": "directory-tree",
                                      "sha256": descriptor.root_sha256, "descriptor_path": descriptor_path.name})
        receipt = self.run_dir / "receipts" / "review.json"
        receipt.parent.mkdir()
        receipt.write_text("{}")
        manifest["review"]["receipt"] = "receipts/review.json"
        manifest_path.write_text(json.dumps(manifest))
        targets = [manifest_path, *(self.run_dir / item["path"] for item in manifest["artifacts"])]
        targets.extend((descriptor_path, tree / "new.json", receipt, receipt.parent / "new.json"))
        targets.extend(self.run_dir / name for name in (".review/new.json", "reviews/new.json", "review/new.json", "review-rounds/1/new.json"))
        alias = self.run_dir / "alias.json"
        alias.symlink_to(manifest_path)
        targets.append(alias)
        hardlink = self.run_dir / "hardlink.json"
        hardlink.hardlink_to(manifest_path)
        targets.append(hardlink)
        for target in targets:
            with self.subTest(target=target.relative_to(self.run_dir)):
                before = {path: path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
                result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"),
                                         str(manifest_path), "--review-output", str(target), "--require-passed-review"],
                                        text=True, capture_output=True, check=False)
                after = {path: path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
                for path in after.keys() - before.keys():
                    path.unlink()
                for path, content in before.items():
                    path.write_bytes(content)
                self.assertEqual(before, after)
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn("--review-output", result.stderr)
        for _ in range(2):
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"),
                                     str(manifest_path), "--review-output", str(self.run_dir / "deterministic-review.json"),
                                     "--require-passed-review"], text=True, capture_output=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_unincorporated_execution_blocks_passed_review_until_refresh(self) -> None:
        from codex_science.artifacts import new_manifest
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        journal = self.run_dir / "execution-log.jsonl"
        journal.write_text("\n")
        self.assertEqual("passed", review_manifest(manifest, self.run_dir)["status"])
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "new-failure", "--",
                          sys.executable, "-c", "raise SystemExit(1)")
        self.assertEqual(1, result.returncode, result.stderr)
        output = Path(self.temp.name) / "review-output.json"
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"),
                                 str(manifest_path), "--review-output", str(output), "--require-passed-review"],
                                text=True, capture_output=True, check=False)
        self.assertEqual(1, result.returncode, result.stderr)
        findings = json.loads(output.read_text())["findings"]
        self.assertIn("unincorporated-execution", {item["code"] for item in findings})
        self.assertIn("package_run.py refresh", next(item["message"] for item in findings if item["code"] == "unincorporated-execution"))
        entry = json.loads(journal.read_text().strip())
        for field in ("executions", "superseded_executions"):
            current = new_manifest("run", "Question", [])
            current[field] = [entry]
            codes = {item["code"] for item in review_manifest(current, self.run_dir, sidecars={})["findings"]}
            self.assertNotIn("unincorporated-execution", codes)
        for malformed in ("{", "[]", "{}", '{"id":0}', '{"id":""}'):
            journal.write_text(malformed + "\n")
            findings = review_manifest(manifest, self.run_dir, sidecars={})["findings"]
            self.assertIn("invalid-execution-journal", {item["code"] for item in findings})
        journal.write_text(json.dumps(entry) + "\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(0, result.returncode, result.stderr)
        refreshed = json.loads(manifest_path.read_text())
        codes = {item["code"] for item in review_manifest(refreshed, self.run_dir)["findings"]}
        self.assertNotIn("unincorporated-execution", codes)
        self.assertIn("failed-execution", codes)
        log = self.run_dir / entry["log_path"]
        for content, code in ((b"changed", "execution-log-mismatch"), (None, "execution-log-missing")):
            if content is None:
                log.unlink()
            else:
                log.write_bytes(content)
            codes = {item["code"] for item in review_manifest(refreshed, self.run_dir)["findings"]}
            self.assertIn(code, codes)

    def test_register_receipt_refuses_changed_packet_manifest_contract(self) -> None:
        from codex_science.reviewer_runtime import build_review_packet, finalize_review_response
        manifest_path = self.run_dir / "manifest.json"
        packet = build_review_packet(manifest_path, review_modes=["record"])
        (self.run_dir / "review-task.json").write_text(json.dumps(packet))
        response = {"review_task_id": packet["review_task_id"], "packet_fingerprint": packet["fingerprint"],
                    "reviewer": "fixture-reviewer", "independent": True, "review_modes": ["record"], "status": "passed",
                    "reviewed_claim_ids": packet["material_claim_ids"], "reviewed_artifacts": packet["artifacts"],
                    "findings": [], "limitations": ["fixture only"]}
        receipt = finalize_review_response(packet, response)
        (self.run_dir / "final-review.json").write_text(json.dumps(receipt))
        original = manifest_path.read_bytes()
        for change in ("claim", "inputs"):
            with self.subTest(change=change):
                manifest = json.loads(original)
                if change == "claim":
                    manifest["claims"][0]["text"] += " Changed decision."
                else:
                    manifest["inputs"] = [{"id": "changed-input"}]
                manifest_path.write_text(json.dumps(manifest))
                before = manifest_path.read_bytes()
                result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertIn("packet", result.stderr)
                self.assertEqual(before, manifest_path.read_bytes())
        manifest_path.write_bytes(original)
        changed = {**packet, "fingerprint": "0" * 64}
        (self.run_dir / "review-task.json").write_text(json.dumps(changed))
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(1, result.returncode, result.stderr)
        self.assertIn("packet identity mismatch", result.stderr)
        self.assertEqual(original, manifest_path.read_bytes())
        (self.run_dir / "review-task.json").write_text(json.dumps(packet))
        for _ in range(2):
            result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
            self.assertEqual(0, result.returncode, result.stderr)

    def test_register_receipt_accepts_manifest_claim_whitespace(self) -> None:
        from codex_science.reviewer_runtime import build_review_packet, finalize_review_response

        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["claims"][0]["text"] += " \n\t"
        manifest_path.write_text(json.dumps(manifest))
        packet = build_review_packet(manifest_path, review_modes=["record"])
        self.assertNotEqual(manifest["claims"][0]["text"], packet["claims"][0]["text"])
        (self.run_dir / "review-task.json").write_text(json.dumps(packet))
        response = {"review_task_id": packet["review_task_id"], "packet_fingerprint": packet["fingerprint"],
                    "reviewer": "fixture-reviewer", "independent": True, "review_modes": ["record"], "status": "passed",
                    "reviewed_claim_ids": packet["material_claim_ids"], "reviewed_artifacts": packet["artifacts"],
                    "findings": [
                        {"id": severity, "severity": severity, "code": "wording", "message": "Optional wording edit",
                         "resolution_status": "open", "evidence": [{"artifact_path": packet["artifacts"][0]["path"]}]}
                        for severity in ("minor", "suggestion")
                    ], "limitations": ["fixture only"]}
        (self.run_dir / "final-review.json").write_text(json.dumps(finalize_review_response(packet, response)))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda _: self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json"),
                range(2),
            ))
        for result in results:
            self.assertEqual(0, result.returncode, result.stderr)
        before = manifest_path.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(before, manifest_path.read_bytes())
        current = json.loads(manifest_path.read_text())
        self.assertEqual("passed", current["review"]["status"])
        self.assertEqual({"minor", "suggestion"}, {item["severity"] for item in current["review"]["findings"]})
        current["claims"][0]["text"] = " \t".join(current["claims"][0]["text"].split())
        manifest_path.write_text(json.dumps(current))
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(0, result.returncode, result.stderr)
        registered = manifest_path.read_bytes()
        for text in ("", " ", "0", 0, None, [], "Changed decision."):
            with self.subTest(text=text):
                changed = json.loads(registered)
                changed["claims"][0]["text"] = text
                manifest_path.write_text(json.dumps(changed))
                before = manifest_path.read_bytes()
                result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertEqual(before, manifest_path.read_bytes())

    def test_register_receipt_accepts_honest_exec_refresh_and_completed_step(self) -> None:
        from codex_science.reviewer_runtime import build_review_packet, finalize_review_response
        from codex_science.run_packaging import plan_receipt_registration

        self._make_unreviewed_run()
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["plan"][-1]["status"] = "pending"
        manifest_path.write_text(json.dumps(manifest))
        packet = build_review_packet(manifest_path, review_modes=["record"])
        # The reviewer retains the packet outside the run while refresh updates bookkeeping.
        retained_packet = Path(self.temp.name) / "review-task.json"
        retained_packet.write_text(json.dumps(packet))
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "review-check", "--",
                          sys.executable, "-c", "print('checked')")
        self.assertEqual(0, result.returncode, result.stderr)
        (self.run_dir / "review-summary.txt").write_text("Review complete.\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--complete-step", "review",
                          "--kind", "review-summary.txt=provenance-record")
        self.assertEqual(0, result.returncode, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(["review"], summary["completed_steps"])
        self.assertEqual(1, summary["executions_added"])
        self.assertIn("review-summary.txt", summary["added"])
        (self.run_dir / "reviewer-notes.md").write_text("Checked the saved record.\n")
        shutil.copyfile(retained_packet, self.run_dir / "review-task.json")
        response = {"review_task_id": packet["review_task_id"], "packet_fingerprint": packet["fingerprint"],
                    "reviewer": "fixture-reviewer", "independent": True, "review_modes": ["record"], "status": "passed",
                    "reviewed_claim_ids": packet["material_claim_ids"], "reviewed_artifacts": packet["artifacts"],
                    "findings": [], "limitations": ["fixture only"]}
        receipt = finalize_review_response(packet, response)
        (self.run_dir / "final-review.json").write_text(json.dumps(receipt))
        current = json.loads(manifest_path.read_text())
        for change in ("bookkeeping", "inputs", "claim", "question", "plan", "code", "environment"):
            with self.subTest(change=change):
                proposed = json.loads(json.dumps(current))
                if change == "bookkeeping":
                    proposed["review"] = {"status": "pending", "findings": [], "reason": "Bookkeeping updated"}
                    proposed["updated_at"] = "2026-10-29T00:00:00Z"
                elif change == "inputs":
                    proposed["inputs"] = []
                elif change == "claim":
                    proposed["claims"][0]["text"] += " Changed decision."
                elif change == "question":
                    proposed["question"] += " Changed question."
                elif change == "plan":
                    proposed["plan"][0]["description"] += " Changed method."
                elif change == "code":
                    proposed["code"] = []
                else:
                    proposed["environment"] = {}
                before = manifest_path.read_bytes()
                if change == "bookkeeping":
                    planned, _summary = plan_receipt_registration(self.run_dir, proposed, "final-review.json")
                    self.assertEqual("passed", planned["review"]["status"])
                else:
                    with self.assertRaisesRegex(ValueError, "review packet"):
                        plan_receipt_registration(self.run_dir, proposed, "final-review.json")
                self.assertEqual(before, manifest_path.read_bytes())
        for _ in range(2):
            result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
            self.assertEqual(0, result.returncode, result.stderr)
        registered = json.loads(manifest_path.read_text())
        self.assertEqual("passed", registered["review"]["status"])
        self.assertEqual("completed", registered["plan"][-1]["status"])
        self.assertIn("review-check", {item.get("id") for item in registered["executions"]})
        registered["inputs"] = []
        with self.assertRaisesRegex(ValueError, "review packet"):
            plan_receipt_registration(self.run_dir, registered, "final-review.json")

    def test_register_receipt_compares_manifest_claims_without_sidecars(self) -> None:
        from codex_science.artifacts import add_artifact, new_manifest
        from codex_science.reviewer_runtime import build_review_packet, finalize_review_response
        from codex_science.run_packaging import plan_receipt_registration

        manifest_path = self.run_dir / "manifest.json"
        manifest = new_manifest("run", "Question", [])
        add_artifact(manifest, "report.md", kind="report",
                     sha256=hashlib.sha256((self.run_dir / "report.md").read_bytes()).hexdigest())
        manifest["claims"] = [{"id": "C1", "text": "Bounded result", "evidence": ["report.md"]}]
        manifest_path.write_text(json.dumps(manifest))
        packet = build_review_packet(manifest_path, review_modes=["record"])
        (self.run_dir / "review-task.json").write_text(json.dumps(packet))
        response = {"review_task_id": packet["review_task_id"], "packet_fingerprint": packet["fingerprint"],
                    "reviewer": "fixture-reviewer", "independent": True, "review_modes": ["record"], "status": "passed",
                    "reviewed_claim_ids": packet["material_claim_ids"], "reviewed_artifacts": packet["artifacts"],
                    "findings": [], "limitations": ["fixture only"]}
        (self.run_dir / "final-review.json").write_text(json.dumps(finalize_review_response(packet, response)))
        manifest["review"]["reason"] = "In-memory bookkeeping"
        planned, _summary = plan_receipt_registration(self.run_dir, manifest, "final-review.json")
        self.assertEqual("passed", planned["review"]["status"])
        from codex_science.run_packaging import _review_packet_content_matches

        for field, value in (("claims", []), ("claims", [{"id": "C2", "text": "Other", "evidence": ["report.md"]}]),
                             ("plan", [0]), ("inputs", ["changed"])):
            with self.subTest(field=field, value=value):
                changed = {**manifest, field: value}
                with self.assertRaisesRegex(ValueError, "review packet"):
                    plan_receipt_registration(self.run_dir, changed, "final-review.json")
        for field, value in (("claims", []), ("material_claim_ids", []), ("decision_contract", None),
                             ("decision_contract", {}), ("decision_contract", {**packet["decision_contract"], "plan": [0]})):
            with self.subTest(packet_field=field, value=value):
                self.assertFalse(_review_packet_content_matches(self.run_dir, manifest, {**packet, field: value}))

    def test_prepare_review_writes_outputs_and_fresh_deterministic_review(self) -> None:
        self._make_unreviewed_run()
        (self.run_dir / "report.md").write_text((self.run_dir / "report.md").read_text() + " refreshed content\n")
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "standard")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["schema"], "prepare-review-v1")
        for name in ("citation-trace.json", "claim-sufficiency.json", "deterministic-review.json", "review-task.json"):
            self.assertTrue((self.run_dir / name).is_file())
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(len(manifest["executions"]), 3)
        self.assertEqual(summary["next"], "spawn the independent reviewer with review-task.json")
        validation = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"),
                                     str(self.run_dir / "manifest.json"), "--review-output",
                                     str(self.run_dir / "deterministic-review.json")],
                                    text=True, capture_output=True, check=False)
        self.assertEqual(validation.returncode, 0, validation.stderr)
        studies_path = self.run_dir / "studies.json"
        studies = json.loads(studies_path.read_text())
        studies["studies"].append({
            "cohort_id": "cohort-example-counter",
            "contradicts_claim_ids": ["claim-method-effect"],
            "evidence_type": "primary",
            "included": True,
            "persistent_id": "doi:10.0000/example.counter.1",
            "study_id": "study-example-counter",
            "supports_claim_ids": [],
            "title": "Counter study with unresolved results",
        })
        studies_path.write_text(json.dumps(studies, indent=2) + "\n")
        graph_path = self.run_dir / "evidence_graph.json"
        graph = json.loads(graph_path.read_text())
        graph["nodes"].append({"id": "study-example-counter", "label": "Counter study", "type": "study"})
        graph["edges"].append({"independence_group": "cohort-example-counter", "relation": "contradicts",
                               "source": "study-example-counter", "target": "claim-method-effect"})
        graph_path.write_text(json.dumps(graph, indent=2) + "\n")
        contradicted = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "standard", "--new-round")
        self.assertEqual(contradicted.returncode, 1)
        contradiction_summary = json.loads(contradicted.stdout)
        sufficiency = next(item for item in contradiction_summary["problems"] if item["stage"] == "claim-sufficiency")
        self.assertIn("contradicted_unresolved", {item["verdict"] for item in sufficiency["advisory"]})
        self.assertIn("deterministic-review", {item["stage"] for item in contradiction_summary["problems"]})

    def test_prepare_review_accepts_additional_files_with_default_kind(self) -> None:
        self._make_unreviewed_run()
        (self.run_dir / "review-corrections.json").write_text('{"notes":[]}\n')
        blocked = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("Unclassified files: review-corrections.json", json.loads(blocked.stdout)["problems"][0]["error"])
        self.assertIn("--kind PATH=KIND or --default-kind KIND", json.loads(blocked.stdout)["problems"][0]["error"])
        accepted = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick",
                            "--default-kind", "provenance")
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        extra = next(item for item in manifest["artifacts"] if item["path"] == "review-corrections.json")
        self.assertEqual(extra["kind"], "provenance")

    def test_prepare_review_initial_refresh_failure_marks_existing_packet_stale(self) -> None:
        self._make_unreviewed_run()
        first = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.run_dir / "report.md").write_text((self.run_dir / "report.md").read_text() + " changed\n")
        (self.run_dir / "unclassified-extra.json").write_text("{}\n")
        blocked = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick", "--new-round")
        self.assertEqual(blocked.returncode, 1)
        summary = json.loads(blocked.stdout)
        self.assertEqual(summary["problems"][0]["phase"], "initial")
        self.assertTrue(summary["review_task_stale"])

    def _snapshot(self) -> tuple[list[str], bytes]:
        names = sorted(str(p.relative_to(self.run_dir)) for p in self.run_dir.rglob("*"))
        return names, (self.run_dir / "manifest.json").read_bytes()

    def test_prepare_review_refresh_failure_previews_orphan_citations_read_only(self) -> None:
        self._make_unreviewed_run()
        (self.run_dir / "unclassified-extra.json").write_text("{}\n")
        report = self.run_dir / "report.md"
        report.write_text(report.read_text() + " doi:10.5555/orphan.reference\n")
        before = self._snapshot()
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(result.returncode, 1)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["problems"][0]["stage"], "refresh")
        preview = next(item for item in summary["problems"] if item["stage"] == "citation-trace")
        self.assertTrue(preview["preview"])
        self.assertEqual(preview["error"], "orphan_citations")
        self.assertEqual([item["identifier"] for item in preview["findings"]], ["doi:10.5555/orphan.reference"])
        self.assertEqual(summary["outputs_written"], [])
        self.assertEqual(self._snapshot(), before)

    def test_prepare_review_refresh_failure_without_orphans_has_no_citation_preview(self) -> None:
        self._make_unreviewed_run()
        (self.run_dir / "unclassified-extra.json").write_text("{}\n")
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(result.returncode, 1)
        stages = [item["stage"] for item in json.loads(result.stdout)["problems"]]
        self.assertEqual(stages[0], "refresh")
        self.assertNotIn("citation-trace", stages)

    def test_prepare_review_blocks_orphan_and_lists_problem(self) -> None:
        self._make_unreviewed_run()
        report = self.run_dir / "report.md"
        report.write_text(report.read_text() + " doi:10.5555/orphan.reference\n")
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(result.returncode, 1)
        summary = json.loads(result.stdout)
        self.assertIn("citation-trace", {item["stage"] for item in summary["problems"]})
        self.assertFalse((self.run_dir / "review-task.json").exists())
        self.assertFalse(summary["review_task_stale"])
        report.write_text(report.read_text().replace(" doi:10.5555/orphan.reference\n", ""))
        rerun = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertTrue((self.run_dir / "review-task.json").is_file())
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        identifiers = [item["id"] for item in manifest["executions"]
                       if isinstance(item.get("id"), str) and item["id"].startswith("prepare-review-")]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        citation = next(item for item in manifest["artifacts"] if item["path"] == "citation-trace.json")
        self.assertEqual(citation["kind"], "citation-trace")

    def test_prepare_review_registers_outputs_left_by_interrupted_call(self) -> None:
        self._make_unreviewed_run()
        (self.run_dir / "citation-trace.json").write_text('{"schema":"citation-trace-v1"}\n')
        (self.run_dir / "claim-sufficiency.json").write_text('{"schema":"claim-sufficiency-v1"}\n')
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertFalse(any(item.get("path") in {"citation-trace.json", "claim-sufficiency.json"}
                             for item in manifest["artifacts"]))
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick",
                          "--kind", "citation-trace.json=custom-kind")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
        self.assertEqual(kinds["citation-trace.json"], "citation-trace")
        self.assertEqual(kinds["claim-sufficiency.json"], "claim-sufficiency")

    def test_prepare_review_packet_artifact_edit_fails_receipt_check(self) -> None:
        self._make_unreviewed_run()
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick")
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads((self.run_dir / "review-task.json").read_text())
        receipt = build_review_receipt(
            review_id="packet-edit-check", reviewer="fixture-reviewer", independent=True,
            review_modes=["record"], status="passed", covered_artifacts=packet["artifacts"],
            covered_claim_ids=[], findings=[], limitations=["fixture only"],
        )
        (self.run_dir / "fixture-receipt.json").write_text(json.dumps(receipt))
        (self.run_dir / "report.md").write_text((self.run_dir / "report.md").read_text() + "edited\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "fixture-receipt.json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("report.md", result.stderr)

    def test_prepare_review_bad_mode_has_argparse_error_prefix(self) -> None:
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick", "--mode", "unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("error:", result.stderr)

    def test_prepare_review_refuses_existing_evidence_and_new_round_archives(self) -> None:
        before = {path.relative_to(self.run_dir).as_posix(): path.read_bytes()
                  for path in self.run_dir.rglob("*") if path.is_file()}
        refused = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full")
        self.assertEqual(refused.returncode, 1)
        self.assertTrue(refused.stderr.startswith("error:"))
        self.assertIn("--new-round", refused.stderr)
        self.assertIn("--register-receipt", refused.stderr)
        after = {path.relative_to(self.run_dir).as_posix(): path.read_bytes()
                 for path in self.run_dir.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        (self.run_dir / "review.json").unlink()
        before_failed_archive = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() if path.is_file() else None
                                 for path in self.run_dir.rglob("*")}
        archive_failed = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full", "--new-round")
        self.assertEqual(archive_failed.returncode, 1)
        failure_summary = json.loads(archive_failed.stdout)
        self.assertEqual(failure_summary["problems"][0]["phase"], "initial")
        after_failed_archive = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() if path.is_file() else None
                                for path in self.run_dir.rglob("*")}
        self.assertEqual(after_failed_archive, before_failed_archive)
        self.assertFalse((self.run_dir / "execution-log.jsonl").exists())
        self.assertFalse((self.run_dir / "logs").exists())
        self.assertFalse((self.run_dir / "citation-trace.json").exists())
        self.assertFalse((self.run_dir / "claim-sufficiency.json").exists())
        self.assertFalse((self.run_dir / "deterministic-review.json").exists())
        self.assertFalse((self.run_dir / "review-task.json").exists())
        (self.run_dir / "review.json").write_bytes(before["review.json"])
        started = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full", "--new-round")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertTrue((self.run_dir / "review-rounds" / "1" / "review.json").is_file())
        first_packet = json.loads((self.run_dir / "review-task.json").read_text())
        self.assertEqual(first_packet["source_manifest_sha256"], hashlib.sha256((self.run_dir / "manifest.json").read_bytes()).hexdigest())

        second_round = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full", "--new-round")
        self.assertEqual(second_round.returncode, 0, second_round.stderr)
        self.assertTrue((self.run_dir / "review-rounds" / "2" / "review-task.json").is_file())
        self.assertTrue((self.run_dir / "review-task.json").is_file())

        external_packet = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "science_reviewer.py"), "prepare",
             str(self.run_dir / "manifest.json"), "--mode", "record", "--output", str(self.run_dir / "review-task.json")],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(external_packet.returncode, 0, external_packet.stderr)
        third_round = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full", "--new-round")
        self.assertEqual(third_round.returncode, 0, third_round.stderr)
        self.assertTrue((self.run_dir / "review-rounds" / "3" / "review-task.json").is_file())
        replacement = json.loads((self.run_dir / "review-task.json").read_text())
        self.assertEqual(replacement["source_manifest_sha256"], hashlib.sha256((self.run_dir / "manifest.json").read_bytes()).hexdigest())
        self.assertFalse(json.loads(third_round.stdout)["review_task_stale"])
        (self.run_dir / "report.md").write_text((self.run_dir / "report.md").read_text() + " doi:10.5555/round-four-orphan\n")
        blocked_round = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "full", "--new-round")
        self.assertEqual(blocked_round.returncode, 1)
        self.assertTrue(json.loads(blocked_round.stdout)["review_task_stale"])
        self.assertFalse((self.run_dir / "review-task.json").exists())

    def test_refresh_records_missing_runtime_history_and_rejects_malformed(self) -> None:
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["runtime_history"] = []
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(path.read_text())["runtime_history"]), 1)
        manifest = json.loads(path.read_text())
        manifest["runtime_history"] = ["invalid"]
        path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("runtime_history entries must be objects", result.stderr)

    def test_exec_records_log_and_passthrough(self) -> None:
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "sample", "--", sys.executable, "-c", "print('hello'); raise SystemExit(7)")
        self.assertEqual(result.returncode, 7)
        record = json.loads((self.run_dir / "execution-log.jsonl").read_text().splitlines()[0])
        self.assertEqual(record["id"], "sample")
        self.assertEqual(record["exit_code"], 7)
        self.assertIn("hello", (self.run_dir / record["log_path"]).read_text())
        self.assertEqual(self.cli("exec", "--run-dir", str(self.run_dir), "--id", "done", "--", sys.executable, "-c", "pass").returncode, 0)
        again = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "done", "--", sys.executable, "-c", "pass")
        self.assertEqual(again.returncode, 1)
        self.assertIn("Duplicate execution id: done; pass a new --id", again.stderr)
        helped = self.cli("exec", "--help")
        self.assertIn("unique within the run", " ".join(helped.stdout.split()))

    def test_refresh_forget_removes_entry_of_deleted_file_and_refuses_unsafe_paths(self) -> None:
        self._make_unreviewed_run()
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"].append({"path": "risk-of-bias.json", "kind": "provenance-record",
                                      "sha256": "0" * 64})
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        (self.run_dir / "risk-of-bias.json").write_text("{}\n")
        base = ("refresh", "--run-dir", str(self.run_dir))
        (self.run_dir / "risk-of-bias.json").rename(self.run_dir / "bias-summary.json")
        missing = self.cli(*base, "--default-kind", "provenance-record")
        self.assertEqual(missing.returncode, 1)
        self.assertIn("Artifact file is missing: risk-of-bias.json", missing.stderr)
        self.assertIn("refresh --forget risk-of-bias.json", missing.stderr)
        before = manifest_path.read_bytes()
        for forget, message in (("nope.json", "is not a manifest artifact"),
                                ("report.md", "the file still exists")):
            result = self.cli(*base, "--forget", forget, "--default-kind", "provenance-record")
            self.assertEqual(result.returncode, 1)
            self.assertIn(message, result.stderr)
            self.assertIn("no files were changed", result.stderr)
            self.assertEqual(manifest_path.read_bytes(), before)
        manifest["claims"][0]["evidence"].append("risk-of-bias.json")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        before = manifest_path.read_bytes()
        result = self.cli(*base, "--forget", "risk-of-bias.json", "--default-kind", "provenance-record")
        self.assertEqual(result.returncode, 1)
        self.assertIn("a manifest claim lists it as evidence", result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)
        manifest["claims"][0]["evidence"].remove("risk-of-bias.json")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = self.cli(*base, "--forget", "risk-of-bias.json", "--forget", "risk-of-bias.json",
                          "--default-kind", "provenance-record")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["forgotten"], ["risk-of-bias.json"])
        self.assertIn("bias-summary.json", summary["added"])
        paths = [item["path"] for item in json.loads(manifest_path.read_text())["artifacts"]]
        self.assertNotIn("risk-of-bias.json", paths)
        self.assertEqual(json.loads(self.cli(*base).stdout)["forgotten"], [])
        combined = self.cli(*base, "--forget", "x", "--register-receipt", "review.json")
        self.assertEqual(combined.returncode, 1)
        self.assertIn("--forget", combined.stderr)

    def test_refresh_exact_kind_reclassifies_existing_entry_but_glob_does_not(self) -> None:
        self._make_unreviewed_run()
        manifest_path = self.run_dir / "manifest.json"
        (self.run_dir / "results.json").write_text("{}\n")
        base = ("refresh", "--run-dir", str(self.run_dir))
        first = self.cli(*base, "--kind", "results.json=statistical-analysis")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["reclassified"], [])

        def kind() -> str:
            return next(i["kind"] for i in json.loads(manifest_path.read_text())["artifacts"] if i["path"] == "results.json")

        glob = self.cli(*base, "--kind", "results.*=metrics")
        self.assertEqual(glob.returncode, 0, glob.stderr)
        self.assertEqual(json.loads(glob.stdout)["reclassified"], [])
        self.assertEqual(kind(), "statistical-analysis")
        same = self.cli(*base, "--kind", "results.json=statistical-analysis")
        self.assertEqual(json.loads(same.stdout)["reclassified"], [])
        exact = self.cli(*base, "--kind", "results.json=metrics")
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertEqual(json.loads(exact.stdout)["reclassified"],
                         [{"path": "results.json", "from": "statistical-analysis", "to": "metrics"}])
        self.assertEqual(kind(), "metrics")
        before = manifest_path.read_bytes()
        refused = self.cli(*base, "--kind", "results.json=review-receipt")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("managed by the review flow", refused.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)

    def test_prepare_review_forwards_forget_to_first_refresh(self) -> None:
        self._make_unreviewed_run()
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"].append({"path": "gone.json", "kind": "provenance-record", "sha256": "0" * 64})
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = self.cli("prepare-review", "--run-dir", str(self.run_dir), "--tier", "quick", "--forget", "gone.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        paths = [item["path"] for item in json.loads(manifest_path.read_text())["artifacts"]]
        self.assertNotIn("gone.json", paths)

    def test_refresh_kind_override_of_review_entry_refused_before_invalidation(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        receipt = next(i["path"] for i in json.loads(manifest_path.read_text())["artifacts"] if i["kind"].startswith("review-receipt"))
        before = manifest_path.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--kind", f"{receipt}=metrics")
        self.assertEqual(result.returncode, 1)
        self.assertIn("managed by the review flow", result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)
        self.assertFalse((self.run_dir / "review-rounds").exists())

    def test_refresh_hashes_and_invalidates_review(self) -> None:
        (self.run_dir / "report.md").write_text("changed\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        report = next(item for item in manifest["artifacts"] if item["path"] == "report.md")
        self.assertNotEqual(report["sha256"], "5fd1e51f952b1280f6614d931cb03c1f0dd1fc9b595ec29b90374d80f4757799")
        self.assertEqual(manifest["review"]["status"], "pending")
        self.assertNotIn("receipt", manifest["review"])
        self.assertFalse(any(item["kind"].startswith("review-receipt") for item in manifest["artifacts"]))
        validation = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"), str(self.run_dir / "manifest.json")], text=True, capture_output=True, check=False)
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_refresh_completes_plan_steps_and_reports_ids(self) -> None:
        self._make_unreviewed_run()
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["plan"][0]["status"] = "pending"
        manifest["plan"][1]["status"] = "blocked"
        manifest["plan"].append({"id": "protocol", "description": "Second matching record", "status": "pending", "order": 9})
        manifest["plan"].append({"id": "0", "description": "Zero is a string ID", "status": "pending"})
        expected = [{**step, "status": "completed"} if step["id"] in {"protocol", "search", "0"} else step
                    for step in manifest["plan"]]
        path.write_text(json.dumps(manifest) + "\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--complete-step", "search",
                          "--complete-step", "protocol", "--complete-step", "search", "--complete-step", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(path.read_text())["plan"], expected)
        self.assertEqual(json.loads(result.stdout)["completed_steps"], ["search", "protocol", "0"])
        self.assertFalse(any(item["code"] == "incomplete-plan" for item in
                             review_manifest(json.loads(path.read_text()), self.run_dir)["findings"]))

    def test_refresh_unknown_complete_step_changes_no_files(self) -> None:
        base = ("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--complete-step", "protocol")
        for identifier in ("missing", "", " ", "0", "protocol?[]"):
            with self.subTest(identifier=identifier):
                before = {p.relative_to(self.run_dir): p.read_bytes() for p in self.run_dir.rglob("*") if p.is_file()}
                result = self.cli(*base, "--complete-step", identifier)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"Unknown plan step IDs: {identifier!r}; known step IDs:", result.stderr)
                for known in ("protocol", "search", "extract", "synthesize"):
                    self.assertIn(repr(known), result.stderr)
                self.assertTrue(result.stderr.rstrip().endswith("; no files were changed"), result.stderr)
                self.assertEqual({p.relative_to(self.run_dir): p.read_bytes() for p in self.run_dir.rglob("*") if p.is_file()}, before)
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["plan"] = []
        path.write_text(json.dumps(manifest) + "\n")
        before_bytes = path.read_bytes()
        result = self.cli(*base)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("known step IDs: (none)", result.stderr)
        self.assertEqual(path.read_bytes(), before_bytes)

    def test_refresh_complete_step_refuses_malformed_plan(self) -> None:
        self._make_unreviewed_run()
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        for plan in ({}, [None]):
            with self.subTest(plan=plan):
                manifest["plan"] = plan
                path.write_text(json.dumps(manifest) + "\n")
                before = path.read_bytes()
                result = self.cli("refresh", "--run-dir", str(self.run_dir), "--complete-step", "protocol")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("Manifest plan must be a list of step objects", result.stderr)
                self.assertTrue(result.stderr.rstrip().endswith("; no files were changed"), result.stderr)
                self.assertEqual(path.read_bytes(), before)

    def test_refresh_completed_step_is_noop(self) -> None:
        self._make_unreviewed_run()
        initial = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertEqual(initial.returncode, 0, initial.stderr)
        self.assertEqual(json.loads(initial.stdout)["completed_steps"], [])
        path = self.run_dir / "manifest.json"
        before = path.read_bytes()
        for _ in range(2):
            result = self.cli("refresh", "--run-dir", str(self.run_dir), "--complete-step", "protocol")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["completed_steps"], [])
            self.assertEqual(path.read_bytes(), before)

    def test_refresh_complete_step_refuses_receipt_registration(self) -> None:
        error = self._refused_register("--run-dir", str(self.run_dir), "--complete-step", "protocol",
                                       "--register-receipt", "review.json")
        self.assertIn("--register-receipt cannot be combined with refresh options (--complete-step)", error)
        self.assertIn("rerun with only --run-dir and --register-receipt", error)

    def test_refresh_complete_step_keeps_review_guard(self) -> None:
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        for status in ("pending", "completed"):
            with self.subTest(status=status):
                manifest["plan"][0]["status"] = status
                path.write_text(json.dumps(manifest) + "\n")
                before = self._snapshot()
                result = self.cli("refresh", "--run-dir", str(self.run_dir), "--complete-step", "protocol")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("Run has independent review evidence", result.stderr)
                self.assertEqual(self._snapshot(), before)

    def test_refresh_complete_step_combines_options_transactionally(self) -> None:
        path = self.run_dir / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["plan"][0]["status"] = "pending"
        manifest["artifacts"].append({"path": "retired.txt", "kind": "provenance-record", "sha256": "0" * 64})
        path.write_text(json.dumps(manifest) + "\n")
        (self.run_dir / "extra.txt").write_text("extra\n")
        (self.run_dir / "notes.txt").write_text("notes\n")
        base = ("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--complete-step", "protocol",
                "--kind", "extra.txt=report", "--default-kind", "provenance-record")
        before = self._snapshot()
        refused = self.cli(*base, "--forget", "absent.txt")
        self.assertEqual(refused.returncode, 1, refused.stderr)
        self.assertIn("--forget", refused.stderr)
        self.assertEqual(self._snapshot(), before)
        result = self.cli(*base, "--forget", "retired.txt")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(summary["completed_steps"], ["protocol"])
        self.assertEqual(summary["forgotten"], ["retired.txt"])
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest["plan"][0]["status"], "completed")
        self.assertEqual(manifest["review"]["status"], "pending")
        kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
        self.assertEqual(kinds["extra.txt"], "report")
        self.assertEqual(kinds["notes.txt"], "provenance-record")
        self.assertTrue((self.run_dir / summary["review_archive"] / "review.json").is_file())

    def test_refresh_complete_step_help_and_guidance(self) -> None:
        result = self.cli("refresh", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--complete-step ID", result.stdout)
        self.assertIn("completed_steps", result.stdout)
        command = '"<plugin-root>/scripts/package_run.py" refresh --run-dir <run-dir> --complete-step <id>'
        for relative in ("authored-skills/literature-review/SKILL.md", "runtime-skills/codex-science/SKILL.md",
                         "runtime-skills/science-provenance/SKILL.md"):
            with self.subTest(relative=relative):
                self.assertIn(command, (ROOT / relative).read_text())

    def _write_review_flow_files(self) -> list[str]:
        files = {
            "review-task.json": {
                "artifacts": [], "response_contract": {}, "fingerprint": "a" * 64,
                "independent_required": True,
            },
            "reviewer-response.json": {
                "review_task_id": "review-task-test", "packet_fingerprint": "a" * 64,
                "reviewed_artifacts": [],
            },
            "independent-review.json": {
                "review_id": "review-test", "covered_artifacts": [], "fingerprint": "b" * 64,
            },
        }
        for name, payload in files.items():
            (self.run_dir / name).write_text(json.dumps(payload) + "\n")
        (self.run_dir / "reviewer-notes.md").write_text("review notes\n")
        (self.run_dir / "deterministic-review-final.json").write_text('{"status":"passed"}\n')
        return [*files, "reviewer-notes.md", "deterministic-review-final.json"]

    def test_review_files_archive_across_review_rounds(self) -> None:
        first_round = self._write_review_flow_files()
        legacy_receipt = self.run_dir / "review.json"
        legacy_receipt_bytes = legacy_receipt.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("review-rounds/1", result.stdout)
        self.assertEqual((self.run_dir / "review-rounds" / "1" / "review.json").read_bytes(), legacy_receipt_bytes)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(manifest["review"]["status"], "pending")
        self.assertFalse(any(item["kind"] in {"review-receipt", "review-receipt-v2"} for item in manifest["artifacts"]))
        self.assertFalse(any(item.get("path") == "review.json" for item in manifest["artifacts"]))
        self.assertFalse(any(item.get("path") == "reviewer-response.json" for item in manifest["artifacts"]))
        for relative in first_round:
            self.assertFalse((self.run_dir / relative).exists())
            self.assertTrue((self.run_dir / "review-rounds" / "1" / relative).is_file())

        (self.run_dir / "report.md").write_text("sidecar edit after review\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stderr)

        second_round = self._write_review_flow_files()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("review-rounds/2", result.stdout)
        for relative in second_round:
            self.assertTrue((self.run_dir / "review-rounds" / "2" / relative).is_file())

    def test_deterministic_review_alone_is_stale_not_independent_evidence(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["review"] = {"status": "pending"}
        review_records = [item for item in manifest["artifacts"] if item.get("kind") in {"review-receipt", "review-receipt-v2"}]
        manifest["artifacts"] = [item for item in manifest["artifacts"] if item not in review_records]
        for item in review_records:
            (self.run_dir / item["path"]).unlink()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        deterministic = self.run_dir / "deterministic-review.json"
        deterministic.write_text('{"status":"failed"}\n')
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(deterministic.is_file())
        self.assertFalse((self.run_dir / "review-rounds").exists())
        self.assertEqual(["deterministic-review.json"], json.loads(result.stdout)["stale_deterministic_review"])

    def test_real_review_task_still_refuses_without_invalidation(self) -> None:
        (self.run_dir / "review-task.json").write_text('{"response_contract":{},"fingerprint":"x","independent_required":true}\n')
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("independent review", result.stderr)

    def test_interrupted_review_archive_is_recovered_on_retry(self) -> None:
        review_path = self.run_dir / "review.json"
        review_path.parent.joinpath("review-rounds", "1").mkdir(parents=True)
        review_path.rename(self.run_dir / "review-rounds" / "1" / "review.json")

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("review-rounds/1", result.stdout)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(manifest["review"]["status"], "pending")
        self.assertFalse(any(item.get("path") == "review.json" for item in manifest["artifacts"]))
        self.assertFalse((self.run_dir / "review-rounds" / "2").exists())
        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_artifact.py"), str(self.run_dir / "manifest.json")],
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_interrupted_review_archive_with_mismatched_bytes_is_unchanged(self) -> None:
        review_path = self.run_dir / "review.json"
        archived = self.run_dir / "review-rounds" / "1" / "review.json"
        archived.parent.mkdir(parents=True)
        archived.write_bytes(review_path.read_bytes() + b"altered")
        review_path.unlink()
        before = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no archived copy matched", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        after = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)

    def test_missing_manifest_receipt_refuses_invalidation_without_changes(self) -> None:
        (self.run_dir / "review.json").unlink()
        before = (self.run_dir / "manifest.json").read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Review file is missing: review.json", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        self.assertEqual((self.run_dir / "manifest.json").read_bytes(), before)
        self.assertFalse((self.run_dir / "review-rounds").exists())

    def test_missing_manifest_names_the_template_to_copy(self) -> None:
        (self.run_dir / "manifest.json").unlink()
        for args in (("refresh", "--run-dir", str(self.run_dir)), ("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "review.json")):
            with self.subTest(args[-1]):
                result = self.cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Run manifest is missing", result.stderr)
                match = re.search(r"copy (\S+manifest\.template\.json) to that path", result.stderr)
                self.assertIsNotNone(match, result.stderr)
                self.assertTrue(Path(match.group(1)).is_file())
        self.assertFalse((self.run_dir / "manifest.json").exists())

    def test_digest_mismatch_names_the_refresh_command_in_every_cli(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        (self.run_dir / manifest["artifacts"][0]["path"]).write_bytes(b"edited after hashing\n")
        run, manifest_arg = str(self.run_dir), str(manifest_path)
        scripts = Path(CLI).parent
        commands = {
            "check_claim_sufficiency": ["--run-dir", run, "--tier", "quick"],
            "check_statement_support": ["--run-dir", run],
            "retrieve_statement_sources": [run],
            "export_scientific_run": [manifest_arg, str(self.run_dir / "out"), "--receipt", str(self.run_dir / "receipt.json")],
            "promote_run_to_skill": [manifest_arg, str(self.run_dir / "draft"), "--name", "x-skill", "--description", "d", "--receipt", str(self.run_dir / "promo.json")],
            "science_reviewer": ["prepare", manifest_arg, "--mode", "record", "--output", str(self.run_dir / "packet.json")],
            "render_artifact_index": [manifest_arg],
            "render_artifact_index --html": ["--html", manifest_arg],
            "render_workbench": [manifest_arg],
        }
        for name, args in commands.items():
            with self.subTest(name):
                result = subprocess.run([sys.executable, str(scripts / f"{name.split()[0]}.py"), *args], text=True, capture_output=True, check=False)
                combined = result.stdout + result.stderr
                self.assertIn("Artifact digest mismatch", combined)
                self.assertIn(f"package_run.py refresh --run-dir={run}", combined)

    def test_archived_legacy_receipt_is_not_rediscovered(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        receipt = next(item for item in manifest["artifacts"] if item["kind"] == "review-receipt")
        original = self.run_dir / receipt["path"]
        renamed = self.run_dir / "legacy-review.json"
        original.rename(renamed)
        receipt["path"] = "legacy-review.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        receipt_bytes = renamed.read_bytes()

        result = self.cli(
            "refresh", "--run-dir", str(self.run_dir), "--invalidate-review",
            "--default-kind", "provenance-record",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.run_dir / "review-rounds" / "1" / "legacy-review.json").read_bytes(), receipt_bytes)
        refreshed = json.loads(manifest_path.read_text())
        self.assertFalse(any(item.get("path") == "legacy-review.json" for item in refreshed["artifacts"]))
        for item in refreshed["artifacts"]:
            self.assertTrue((self.run_dir / item["path"]).exists(), item["path"])

    def test_failed_review_invalidation_moves_nothing(self) -> None:
        review_files = self._write_review_flow_files()
        (self.run_dir / "unclassified.bin").write_bytes(b"unknown")
        before = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unclassified.bin", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        self.assertFalse((self.run_dir / "review-rounds").exists())
        after = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)
        for relative in review_files:
            self.assertTrue((self.run_dir / relative).is_file())

    def test_reviewed_bundle_refused_without_override(self) -> None:
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalidates the independent review", result.stderr)

    def test_unclassified_and_kind_override(self) -> None:
        (self.run_dir / "custom.bin").write_bytes(b"data")
        before = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("custom.bin", result.stderr)
        after = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
        self.assertEqual(after, before)
        self.assertIn("no files were changed", result.stderr)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--kind", "custom.bin=custom-data")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(next(item for item in manifest["artifacts"] if item["path"] == "custom.bin")["kind"], "custom-data")

    def test_escaping_symlink_rejected(self) -> None:
        outside = Path(self.temp.name) / "outside.dat"
        outside.write_text("outside")
        (self.run_dir / "custom.dat").symlink_to(outside)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--kind", "custom.dat=data")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("escapes run directory", result.stderr)

    def test_lane_output_hash_refresh(self) -> None:
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {"report.md": "0" * 64}
        lane_path.write_text(json.dumps(lane))
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        lane = json.loads(lane_path.read_text())
        self.assertEqual(lane["output_sha256"]["report.md"], __import__("hashlib").sha256((self.run_dir / "report.md").read_bytes()).hexdigest())

    def test_code_entries_preserved_and_merged(self) -> None:
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        old_code = next(item for item in manifest["code"] if item["path"] == "scripts/diff_literature_review.py")
        (self.run_dir / "build.py").write_text("print('build')\n")
        authored_code = {"path": "./build.py", "revision": "authored-revision"}
        manifest["code"].append(authored_code)
        (self.run_dir / "manifest.json").write_text(json.dumps(manifest))
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertIn(old_code, manifest["code"])
        merged = [item for item in manifest["code"] if Path(item["path"]).as_posix().lstrip("./") == "build.py"]
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["path"], "./build.py")
        self.assertEqual(merged[0]["revision"], "authored-revision")
        self.assertEqual(merged[0]["sha256"], hashlib.sha256((self.run_dir / "build.py").read_bytes()).hexdigest())

    def test_conventions_register_run_files(self) -> None:
        (self.run_dir / "raw").mkdir()
        (self.run_dir / "raw" / "x.txt").write_text("source")
        (self.run_dir / "bias").mkdir()
        (self.run_dir / "bias" / "s1.json").write_text("{}\n")
        (self.run_dir / "build.py").write_text("print('build')\n")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
        self.assertEqual(kinds["raw/x.txt"], "source-snapshot")
        self.assertEqual(kinds["bias/s1.json"], "risk-of-bias")
        self.assertEqual(kinds["build.py"], "code")

    def test_glob_kind_and_default_kind(self) -> None:
        (self.run_dir / "notes").mkdir()
        (self.run_dir / "notes" / "agent.md").write_text("notes")
        (self.run_dir / "untyped.dat").write_text("data")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review", "--kind", "./notes//*.md=provenance-record", "--default-kind", "misc")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        kinds = {item["path"]: item["kind"] for item in manifest["artifacts"]}
        self.assertEqual(kinds["notes/agent.md"], "provenance-record")
        self.assertEqual(kinds["untyped.dat"], "misc")

    def test_register_receipt_on_unchanged_reviewed_bundle(self) -> None:
        report_hash = hashlib.sha256((self.run_dir / "report.md").read_bytes()).hexdigest()
        source = {
            "schema_version": 1, "review_id": "review-test", "reviewer": "fixture-reviewer",
            "independent": True, "review_modes": ["record"], "status": "passed",
            "covered_artifacts": [{"path": "report.md", "sha256": report_hash}],
            "covered_claim_ids": [], "findings": [], "limitations": ["fixture only"],
            "review_task_id": "review-task-test", "packet_fingerprint": "a" * 64,
        }
        source["fingerprint"] = canonical_sha256(source)
        receipt_path = self.run_dir / "final-review.json"
        receipt_path.write_text(json.dumps(source))
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        entry = next(item for item in manifest["artifacts"] if item["path"] == "final-review.json")
        self.assertEqual(entry["kind"], "review-receipt-v2")
        self.assertEqual(manifest["review"]["status"], "passed")
        self.assertEqual(manifest["review"]["receipt"], "final-review.json")
        self.assertEqual(manifest["review"]["findings"], [])

        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_artifact.py"),
             str(self.run_dir / "manifest.json"), "--review-output", str(Path(self.temp.name) / "review-output.json"),
             "--require-passed-review"], text=True, capture_output=True, check=False,
        )
        self.assertEqual(validation.returncode, 0, validation.stderr)
        rendered = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_artifact_index.py"),
             str(self.run_dir / "manifest.json")], text=True, capture_output=True, check=False,
        )
        self.assertEqual(rendered.returncode, 0, rendered.stderr)
        self.assertIn("✅ Passed", (self.run_dir / "index.md").read_text())

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(manifest["review"]["status"], "pending")
        self.assertNotIn("receipt", manifest["review"])

    def test_register_receipt_updates_prelisted_artifact_and_is_idempotent(self) -> None:
        report_hash = hashlib.sha256((self.run_dir / "report.md").read_bytes()).hexdigest()
        source = {
            "schema_version": 1, "review_id": "review-test", "reviewer": "fixture-reviewer",
            "independent": True, "review_modes": ["record"], "status": "passed",
            "covered_artifacts": [{"path": "report.md", "sha256": report_hash}],
            "covered_claim_ids": [], "findings": [], "limitations": ["fixture only"],
            "review_task_id": "review-task-test", "packet_fingerprint": "a" * 64,
        }
        source["fingerprint"] = canonical_sha256(source)
        receipt_path = self.run_dir / "final-review.json"
        receipt_path.write_text(json.dumps(source))
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"].append({
            "path": "final-review.json", "kind": "review-receipt-v2",
            "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        })
        manifest_path.write_text(json.dumps(manifest))

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual([item["path"] for item in manifest["artifacts"]].count("final-review.json"), 1)
        self.assertEqual(manifest["review"]["status"], "passed")
        self.assertEqual(manifest["review"]["receipt"], "final-review.json")

        before = manifest_path.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)

        stale = {**source, "covered_artifacts": [{"path": "report.md", "sha256": "0" * 64}]}
        stale.pop("fingerprint")
        legacy = {key: value for key, value in stale.items() if key != "review_id"}
        for replacement, code in ((stale, "stale-review-receipt"), (legacy, "Legacy review receipts")):
            replacement["fingerprint"] = canonical_sha256(replacement)
            receipt_path.write_text(json.dumps(replacement))
            manifest = json.loads(manifest_path.read_text())
            entry = next(item for item in manifest["artifacts"] if item["path"] == "final-review.json")
            entry["sha256"] = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest))
            before = manifest_path.read_bytes()
            result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "final-review.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(code, result.stderr)
            self.assertEqual(manifest_path.read_bytes(), before)

    def _refused_register(self, *args: str, cwd: Path | None = None) -> str:
        manifest_path = self.run_dir / "manifest.json"
        before = manifest_path.read_bytes()
        result = subprocess.run([sys.executable, str(CLI), "refresh", *args], text=True, capture_output=True,
                                check=False, cwd=cwd)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue(result.stderr.rstrip().endswith("; no files were changed"), result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)
        return result.stderr

    def test_register_receipt_combined_options_name_offender_and_retry(self) -> None:
        error = self._refused_register("--run-dir", str(self.run_dir), "--default-kind", "provenance-record",
                                       "--register-receipt", "review.json")
        self.assertIn("--default-kind", error)
        self.assertNotIn("--invalidate-review", error)
        self.assertIn("rerun with only --run-dir and --register-receipt", error)

    def test_register_receipt_cwd_relative_path_suggests_run_relative_form(self) -> None:
        (self.run_dir / "sub").mkdir()
        (self.run_dir / "sub" / "r.json").write_text("{}")
        error = self._refused_register("--run-dir", str(self.run_dir), "--register-receipt", "run/sub/r.json",
                                       cwd=self.run_dir.parent)
        self.assertIn("relative to the run directory", error)
        self.assertIn("pass sub/r.json", error)
        self.assertNotIn(self.temp.name, error)

    def test_register_receipt_symlink_in_cwd_gets_no_suggestion(self) -> None:
        alias = self.run_dir.parent / "alias.json"
        try:
            alias.symlink_to(self.run_dir / "review.json")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unsupported")
        error = self._refused_register("--run-dir", str(self.run_dir), "--register-receipt", "alias.json",
                                       cwd=self.run_dir.parent)
        self.assertIn("Review receipt is missing: alias.json", error)
        self.assertNotIn("pass ", error)

    def test_register_receipt_missing_without_matching_file_has_no_suggestion(self) -> None:
        error = self._refused_register("--run-dir", str(self.run_dir), "--register-receipt", "nope.json",
                                       cwd=self.run_dir.parent)
        self.assertIn("Review receipt is missing: nope.json", error)
        self.assertNotIn("pass ", error)

    def test_register_receipt_refuses_stale_bundle(self) -> None:
        (self.run_dir / "report.md").write_text("changed")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "review.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("report.md", result.stderr)

    def test_register_receipt_refuses_stale_incoming_coverage_without_writing(self) -> None:
        source = {
            "schema_version": 1, "review_id": "stale-review-test", "reviewer": "fixture-reviewer",
            "independent": True, "review_modes": ["record"], "status": "passed",
            "covered_artifacts": [{"path": "report.md", "sha256": "0" * 64}],
            "covered_claim_ids": [], "findings": [], "limitations": ["fixture only"],
        }
        source["fingerprint"] = canonical_sha256(source)
        (self.run_dir / "stale-review.json").write_text(json.dumps(source))
        manifest_path = self.run_dir / "manifest.json"
        before = manifest_path.read_bytes()

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "stale-review.json")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale-review-receipt", result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before)

    def test_register_receipt_alias_is_already_registered(self) -> None:
        before = (self.run_dir / "manifest.json").read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--register-receipt", "./review.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Legacy review receipts without review_id", result.stderr)
        self.assertEqual((self.run_dir / "manifest.json").read_bytes(), before)

    def test_unchanged_lane_is_not_rewritten(self) -> None:
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {"report.md": hashlib.sha256((self.run_dir / "report.md").read_bytes()).hexdigest()}
        lane_path.write_text(json.dumps(lane))
        before = lane_path.stat().st_mtime_ns
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(lane_path.stat().st_mtime_ns, before)

    def test_symlink_lane_refused_without_touching_target(self) -> None:
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        outside = Path(self.temp.name) / "outside-lane.json"
        outside.write_text('{"output_sha256":{"report.md":"' + "0" * 64 + '"}}')
        lane_path.unlink()
        lane_path.symlink_to(outside)
        before = outside.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(outside.read_bytes(), before)

    def test_symlink_manifest_refused(self) -> None:
        manifest = self.run_dir / "manifest.json"
        outside = Path(self.temp.name) / "outside-manifest.json"
        shutil.copy2(manifest, outside)
        manifest.unlink()
        manifest.symlink_to(outside)
        before = outside.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(outside.read_bytes(), before)

    def test_stale_lane_and_missing_artifact_refusal_is_transactional(self) -> None:
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {"report.md": "0" * 64}
        lane_path.write_text(json.dumps(lane))
        missing = self.run_dir / "report.md"
        missing.unlink()
        before_lane = lane_path.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("report.md", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        self.assertEqual(lane_path.read_bytes(), before_lane)

    def test_exec_skips_reserved_log_without_journal_record(self) -> None:
        logs = self.run_dir / "logs"
        logs.mkdir()
        (logs / "exec-001.log").write_text("interrupted\n")
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--", sys.executable, "-c", "print('two')")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads((self.run_dir / "execution-log.jsonl").read_text().splitlines()[0])
        self.assertEqual(record["id"], "exec-002")
        (logs / "exec-001.log").unlink()
        with (self.run_dir / "execution-log.jsonl").open("a", encoding="utf-8") as stream:
            stream.write('{"id":"exec-001"}\n')
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--", sys.executable, "-c", "print('three')")
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in (self.run_dir / "execution-log.jsonl").read_text().splitlines()]
        self.assertEqual(records[-1]["id"], "exec-003")
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["executions"].append({"id": "exec-004", "command": "legacy"})
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        result = self.cli("exec", "--run-dir", str(self.run_dir), "--", sys.executable, "-c", "print('five')")
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in (self.run_dir / "execution-log.jsonl").read_text().splitlines()]
        self.assertEqual(records[-1]["id"], "exec-005")
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(manifest_path.read_text())
        self.assertTrue({"exec-001", "exec-002", "exec-003", "exec-004", "exec-005"}.issubset(
            {item.get("id") for item in manifest["executions"]}
        ))

    def test_conflicting_journal_execution_refused_without_changes(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        existing = {
            "id": "exec-conflict", "command": "python task.py", "started_at": "start",
            "ended_at": "end", "exit_code": 0, "log_path": "logs/exec-conflict.log",
        }
        manifest["executions"].append(existing)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        (self.run_dir / "execution-log.jsonl").write_text(json.dumps({**existing, "exit_code": 1}) + "\n")
        before = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exec-conflict", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        after = {
            path.relative_to(self.run_dir).as_posix(): path.read_bytes()
            for path in self.run_dir.rglob("*") if path.is_file()
        }
        self.assertEqual(after, before)

    def _retry_command(self, marker: Path) -> list[str]:
        code = f"from pathlib import Path; raise SystemExit(0 if Path({str(marker)!r}).exists() else 1)"
        return [sys.executable, "-c", code]

    def test_successful_retry_supersedes_failure_and_clears_review_finding(self) -> None:
        marker = Path(self.temp.name) / "retry-ready"
        command = self._retry_command(marker)
        failed = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "failed-attempt", "--", *command)
        self.assertEqual(failed.returncode, 1)
        marker.touch()
        succeeded = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "successful-retry", "--", *command)
        self.assertEqual(succeeded.returncode, 0, succeeded.stderr)

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        failed_record = next(item for item in manifest["superseded_executions"] if item["id"] == "failed-attempt")
        self.assertEqual(failed_record["superseded_by"], "successful-retry")
        self.assertEqual(failed_record["log_sha256"], json.loads((self.run_dir / "execution-log.jsonl").read_text().splitlines()[0])["log_sha256"])
        self.assertFalse(any(item.get("id") == "failed-attempt" for item in manifest["executions"]))
        self.assertTrue(any(item.get("id") == "successful-retry" for item in manifest["executions"]))
        self.assertFalse(any(item["code"] == "failed-execution" for item in review_manifest(manifest)["findings"]))
        self.assertEqual(json.loads(result.stdout.splitlines()[-1])["superseded_failures"], 1)
        result = self.cli("refresh", "--run-dir", str(self.run_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["superseded_failures"], 0)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual(sum(item["id"] == "failed-attempt" for item in manifest["superseded_executions"]), 1)

    def test_failed_id_reused_records_retry_id_and_keeps_both(self) -> None:
        marker = Path(self.temp.name) / "retry-ready"
        command = self._retry_command(marker)
        failed = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "X", "--", *command)
        self.assertEqual(failed.returncode, 1)
        failed_log = (self.run_dir / "logs" / "X.log").read_bytes()
        marker.touch()
        retried = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "X", "--", *command)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertIn("note: execution id X already has a failed run; recorded this run as X-retry-2", retried.stderr)
        self.assertEqual((self.run_dir / "logs" / "X.log").read_bytes(), failed_log)
        self.assertTrue((self.run_dir / "logs" / "X-retry-2.log").is_file())
        ids = [json.loads(line)["id"] for line in (self.run_dir / "execution-log.jsonl").read_text().splitlines()]
        self.assertEqual(ids, ["X", "X-retry-2"])
        refreshed = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual([item["id"] for item in manifest["superseded_executions"]], ["X"])
        self.assertEqual(manifest["superseded_executions"][0]["superseded_by"], "X-retry-2")
        self.assertEqual([item.get("id") for item in manifest["executions"] if item.get("id")], ["X-retry-2"])
        validation = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"), str(self.run_dir / "manifest.json")], text=True, capture_output=True, check=False)
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        third = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "X", "--", sys.executable, "-c", "raise SystemExit(1)")
        self.assertEqual(third.returncode, 1)
        self.assertIn("X-retry-3", third.stderr)

    def test_succeeded_id_reused_is_refused_with_next_free_hint(self) -> None:
        ok = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "X", "--", sys.executable, "-c", "pass")
        self.assertEqual(ok.returncode, 0, ok.stderr)
        again = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "X", "--", sys.executable, "-c", "pass")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("Duplicate execution id: X; pass a new --id (next free: X-2) or omit it", again.stderr)
        self.assertEqual(len((self.run_dir / "execution-log.jsonl").read_text().splitlines()), 1)

    def test_failure_without_retry_remains_review_finding(self) -> None:
        result = self.cli(
            "exec", "--run-dir", str(self.run_dir), "--id", "unretried-failure", "--",
            sys.executable, "-c", "raise SystemExit(3)",
        )
        self.assertEqual(result.returncode, 3)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertTrue(any(item.get("id") == "unretried-failure" for item in manifest["executions"]))
        finding = next(item for item in review_manifest(manifest)["findings"] if item["code"] == "failed-execution")
        self.assertEqual("major", finding["severity"])
        self.assertIn("If the nonzero exit was the expected outcome of a negative check", finding["message"])
        self.assertIn(
            "A transient source failure clears when the identical command is rerun and succeeds.",
            finding["message"],
        )

    def test_different_success_does_not_supersede_failure(self) -> None:
        failed = self.cli(
            "exec", "--run-dir", str(self.run_dir), "--id", "failed-command", "--",
            sys.executable, "-c", "raise SystemExit(2)",
        )
        self.assertEqual(failed.returncode, 2)
        succeeded = self.cli(
            "exec", "--run-dir", str(self.run_dir), "--id", "different-success", "--",
            sys.executable, "-c", "raise SystemExit(0)",
        )
        self.assertEqual(succeeded.returncode, 0)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertTrue(any(item.get("id") == "failed-command" for item in manifest["executions"]))
        self.assertFalse(any(item.get("id") == "failed-command" for item in manifest["superseded_executions"]))
        self.assertTrue(any(item["code"] == "failed-execution" for item in review_manifest(manifest)["findings"]))

    def test_later_retry_moves_previously_imported_failure(self) -> None:
        marker = Path(self.temp.name) / "later-retry-ready"
        command = self._retry_command(marker)
        failed = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "early-failure", "--", *command)
        self.assertEqual(failed.returncode, 1)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        existing_failure = next(item for item in manifest["executions"] if item.get("id") == "early-failure")
        existing_failure["authored_note"] = "preserve this field"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        marker.touch()
        succeeded = self.cli("exec", "--run-dir", str(self.run_dir), "--id", "late-success", "--", *command)
        self.assertEqual(succeeded.returncode, 0, succeeded.stderr)
        result = self.cli("refresh", "--run-dir", str(self.run_dir))

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(manifest_path.read_text())
        moved = next(item for item in manifest["superseded_executions"] if item["id"] == "early-failure")
        self.assertEqual(moved["superseded_by"], "late-success")
        self.assertEqual(moved["authored_note"], "preserve this field")
        self.assertFalse(any(item.get("id") == "early-failure" for item in manifest["executions"]))
        self.assertEqual(json.loads(result.stdout)["superseded_failures"], 1)

    def test_parallel_execs_get_distinct_ids_and_survive_refresh(self) -> None:
        def run_one(label: str) -> subprocess.CompletedProcess[str]:
            return self.cli("exec", "--run-dir", str(self.run_dir), "--", sys.executable, "-c", f"print('{label}')")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run_one, ("one", "two")))
        self.assertTrue(all(result.returncode == 0 for result in results), [result.stderr for result in results])
        records = [json.loads(line) for line in (self.run_dir / "execution-log.jsonl").read_text().splitlines()]
        self.assertEqual(len({item["id"] for item in records}), 2)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.run_dir / "manifest.json").read_text())
        self.assertEqual({item["id"] for item in manifest["executions"] if item.get("id")}, {item["id"] for item in records})

    def test_size_metadata_refreshes_and_bundle_validates(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        report = next(item for item in manifest["artifacts"] if item["path"] == "report.md")
        report["size_bytes"] = (self.run_dir / "report.md").stat().st_size
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        lane_record = next(item for item in manifest["artifacts"] if item["path"] == "lanes/pubmed-search.json")
        lane_record["size_bytes"] = lane_path.stat().st_size
        manifest_path.write_text(json.dumps(manifest))
        (self.run_dir / "report.md").write_text("new report with a different size\n")
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {"report.md": "0" * 64}
        lane_path.write_text(json.dumps(lane))
        pre_refresh_lane_size = lane_path.stat().st_size
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        refreshed = json.loads(manifest_path.read_text())
        report = next(item for item in refreshed["artifacts"] if item["path"] == "report.md")
        self.assertEqual(report["size_bytes"], (self.run_dir / "report.md").stat().st_size)
        lane_record = next(item for item in refreshed["artifacts"] if item["path"] == "lanes/pubmed-search.json")
        self.assertNotEqual(lane_path.stat().st_size, pre_refresh_lane_size)
        self.assertEqual(lane_record["size_bytes"], lane_path.stat().st_size)
        validation = self.cli_validator(manifest_path)
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def cli_validator(self, manifest: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "validate_artifact.py"), str(manifest)], text=True, capture_output=True, check=False)

    def test_descriptor_backed_change_refused(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        report = next(item for item in manifest["artifacts"] if item["path"] == "report.md")
        report["descriptor_path"] = "report.descriptor.json"
        manifest_path.write_text(json.dumps(manifest))
        (self.run_dir / "report.md").write_text("changed report\n")
        before_manifest = manifest_path.read_bytes()
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scripts/describe_artifact.py", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        self.assertEqual(manifest_path.read_bytes(), before_manifest)

    def _register_lanes_directory(self, *, stale_lane: bool, descriptor: bool = False) -> Path:
        lane_path = self.run_dir / "lanes" / "pubmed-search.json"
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {
            "report.md": "0" * 64 if stale_lane else hashlib.sha256((self.run_dir / "report.md").read_bytes()).hexdigest()
        }
        lane_path.write_text(json.dumps(lane))
        directory = describe_directory(self.run_dir / "lanes")
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        record = {
            "path": "./lanes//", "kind": "lane-directory", "sha256": directory.root_sha256,
            "artifact_type": "directory-tree", "size_bytes": directory.total_bytes,
            "entry_count": directory.entry_count,
        }
        if descriptor:
            record["descriptor_path"] = "lanes/descriptor.json"
        manifest["artifacts"].append(record)
        manifest_path.write_text(json.dumps(manifest))
        return manifest_path

    def test_directory_tree_containing_stale_lane_refused_transactionally(self) -> None:
        manifest_path = self._register_lanes_directory(stale_lane=True, descriptor=True)
        before = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lanes", result.stderr)
        self.assertIn("lanes/pubmed-search.json", result.stderr)
        self.assertIn("no files were changed", result.stderr)
        after = {path.relative_to(self.run_dir).as_posix(): path.read_bytes() for path in self.run_dir.rglob("*") if path.is_file()}
        self.assertEqual(after, before)

    def test_directory_tree_containing_unchanged_lane_refreshes(self) -> None:
        manifest_path = self._register_lanes_directory(stale_lane=False)
        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        validation = self.cli_validator(manifest_path)
        self.assertEqual(validation.returncode, 0, validation.stderr)

    def test_aliased_lane_artifact_is_refreshed_without_duplicate(self) -> None:
        manifest_path = self.run_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        lane_relative = "lanes/pubmed-search.json"
        lane_item = next(item for item in manifest["artifacts"] if item["path"] == lane_relative)
        lane_item["path"] = "./lanes//pubmed-search.json"
        manifest_path.write_text(json.dumps(manifest))
        lane_path = self.run_dir / lane_relative
        lane = json.loads(lane_path.read_text())
        lane["output_sha256"] = {"./report.md": "0" * 64}
        lane_path.write_text(json.dumps(lane))

        result = self.cli("refresh", "--run-dir", str(self.run_dir), "--invalidate-review")
        self.assertEqual(result.returncode, 0, result.stderr)
        refreshed = json.loads(manifest_path.read_text())
        lane_entries = [item for item in refreshed["artifacts"] if Path(item["path"]).as_posix().lstrip("./") == lane_relative]
        self.assertEqual(len(lane_entries), 1)
        self.assertEqual(lane_entries[0]["path"], "./lanes//pubmed-search.json")
        self.assertEqual(lane_entries[0]["sha256"], hashlib.sha256(lane_path.read_bytes()).hexdigest())
        validation = self.cli_validator(manifest_path)
        self.assertEqual(validation.returncode, 0, validation.stderr)


if __name__ == "__main__":
    unittest.main()
