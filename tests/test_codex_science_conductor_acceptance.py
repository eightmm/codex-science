"""Deterministic local approval gates; no provider or empirical result is tested."""

import copy
import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

from codex_science.action_connectors import (
    ActionLedger,
    ActionSpec,
    build_action_approval,
    build_preview,
    execute_action,
    validate_action_receipt,
)
from tests.test_action_connectors import FakeAdapter


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "codex-science" / "input.json"
QUALITY = ROOT / "runtime-skills" / "codex-science" / "quality.json"
STAMP = "2026-07-21T00:00:00Z"
SEEDED_FAILURE_TESTS = {
    "missing-write-approval": "test_missing_write_approval",
    "approval-spec-digest-mismatch": "test_approval_spec_digest_mismatch",
    "approval-reused-for-different-target": "test_approval_reused_for_different_target",
    "preview-spec-mismatch": "test_preview_spec_mismatch",
    "remote-state-drift": "test_remote_state_drift",
    "idempotency-key-reuse": "test_idempotency_key_reuse",
}


class CodexScienceConductorAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch("codex_science.action_connectors._now", return_value=STAMP))
        self.enterContext(patch("codex_science.action_connectors.uuid.uuid4", return_value=UUID(int=1)))
        self.adapter = FakeAdapter()
        self.spec = ActionSpec.from_payload(copy.deepcopy(self.payload))
        self.preview = build_preview(self.adapter, self.spec, created_at=STAMP)
        self.approval = build_action_approval(
            self.preview,
            approved_by="fixture-reviewer",
            approved_scopes=self.payload["requested_scopes"],
            approved_at=STAMP,
        )
        self.ledger = ActionLedger(self.directory / "actions.sqlite")

    def assert_refused(self, spec, preview, approval, message) -> None:
        count = self.adapter.execute_count
        state = copy.deepcopy(self.adapter.state)
        existing = self.ledger.get(spec.idempotency_key)
        with self.assertRaisesRegex(ValueError, message):
            execute_action(
                self.adapter, spec, preview, approval=approval, ledger=self.ledger,
                executed_at=STAMP,
            )
        self.assertEqual(count, self.adapter.execute_count)
        self.assertEqual(state, self.adapter.state)
        self.assertEqual(existing, self.ledger.get(spec.idempotency_key))

    def run_cli(self, *arguments) -> dict:
        script = ROOT / "scripts" / "connector_action_contract.py"
        module_spec = importlib.util.spec_from_file_location("connector_action_acceptance", script)
        assert module_spec is not None and module_spec.loader is not None
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        output = self.directory / f"cli-{arguments[0]}.json"
        stdout, stderr = io.StringIO(), io.StringIO()
        argv = [str(script), *map(str, arguments), "--output", str(output)]
        with patch("sys.argv", argv), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(0, module.main(), stderr.getvalue())
        self.assertIn("Success! Data written to:", stdout.getvalue())
        return json.loads(output.read_text(encoding="utf-8"))

    def test_fixture_passes_public_cli_and_local_execution_chain(self) -> None:
        validated = self.run_cli("validate-spec", FIXTURE)
        self.assertEqual("valid", validated["status"])
        self.assertEqual(self.spec.fingerprint, validated["action_spec_sha256"])
        self.assertEqual(self.payload, validated["spec"])
        preview_path = self.directory / "preview.json"
        preview_path.write_text(json.dumps(self.preview), encoding="utf-8")
        validated_preview = self.run_cli("validate-preview", preview_path, "--spec", FIXTURE)
        self.assertEqual("valid", validated_preview["status"])
        self.assertEqual(self.preview["fingerprint"], validated_preview["preview_fingerprint"])
        approval = self.run_cli(
            "approve", preview_path, "--approved-by", "fixture-reviewer",
            "--scope", "sample:read", "--scope", "sample:write",
        )
        self.assertEqual(self.approval, approval)
        receipt = execute_action(
            self.adapter, self.spec, self.preview, approval=approval,
            ledger=self.ledger, executed_at=STAMP,
        )
        validate_action_receipt(receipt, self.spec)
        self.assertEqual("executed", receipt["status"])
        self.assertEqual(self.spec.fingerprint, receipt["action_spec_sha256"])
        self.assertEqual(self.preview["fingerprint"], receipt["preview_fingerprint"])
        self.assertEqual(approval["fingerprint"], receipt["approval_fingerprint"])
        self.assertEqual(self.spec.target, receipt["target"])
        self.assertEqual(["sample-1"], receipt["remote_object_ids"])
        self.assertEqual("published", receipt["after_state"]["status"])
        self.assertEqual(2, receipt["after_state"]["version"])
        self.assertNotEqual(receipt["before_state_sha256"], receipt["after_state_sha256"])
        self.assertEqual(receipt, self.ledger.get(self.spec.idempotency_key))
        repeated = execute_action(
            self.adapter, self.spec, self.preview, approval=approval,
            ledger=self.ledger, executed_at=STAMP,
        )
        self.assertEqual(receipt, repeated)
        self.assertEqual(1, self.adapter.execute_count)

    def test_missing_write_approval(self) -> None:
        self.assert_refused(
            self.spec, self.preview, None, "write action requires explicit approval",
        )

    def test_approval_spec_digest_mismatch(self) -> None:
        for digest in ("", "0" * 64, "malformed"):
            with self.subTest(digest=digest):
                approval = copy.deepcopy(self.approval)
                approval["action_spec_sha256"] = digest
                self.assert_refused(
                    self.spec, self.preview, approval,
                    "approval action_spec_sha256 does not match preview",
                )

    def test_approval_reused_for_different_target(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["target"] = "workspace-1/sample-2"
        spec = ActionSpec.from_payload(payload)
        preview = build_preview(self.adapter, spec, created_at=STAMP)
        self.assert_refused(
            spec, preview, self.approval, "approval preview_id does not match preview",
        )

    def test_preview_spec_mismatch(self) -> None:
        payload = copy.deepcopy(self.payload)
        payload["parameters"]["status"] = "archived"
        spec = ActionSpec.from_payload(payload)
        self.assert_refused(
            spec, self.preview, self.approval, "action preview covers a different spec",
        )

    def test_remote_state_drift(self) -> None:
        self.adapter.state["version"] += 1
        self.assert_refused(
            self.spec, self.preview, self.approval, "remote state changed after preview",
        )

    def test_idempotency_key_reuse(self) -> None:
        execute_action(
            self.adapter, self.spec, self.preview, approval=self.approval,
            ledger=self.ledger, executed_at=STAMP,
        )
        payload = copy.deepcopy(self.payload)
        payload["parameters"]["status"] = "archived"
        spec = ActionSpec.from_payload(payload)
        preview = build_preview(self.adapter, spec, created_at=STAMP)
        approval = build_action_approval(
            preview, approved_by="fixture-reviewer",
            approved_scopes=payload["requested_scopes"], approved_at=STAMP,
        )
        self.assert_refused(
            spec, preview, approval, "idempotency key is already bound to a different spec",
        )

    def test_quality_declares_exactly_the_exercised_failures(self) -> None:
        quality = json.loads(QUALITY.read_text(encoding="utf-8"))
        self.assertEqual("L4", quality["declared_maturity"])
        self.assertEqual([FIXTURE.relative_to(ROOT).as_posix()], quality["acceptance_fixtures"])
        self.assertIn(Path(__file__).relative_to(ROOT).as_posix(), quality["test_files"])
        self.assertEqual(set(SEEDED_FAILURE_TESTS), set(quality["seeded_failures"]))
        self.assertEqual(len(SEEDED_FAILURE_TESTS), len(quality["seeded_failures"]))
        methods = unittest.defaultTestLoader.getTestCaseNames(type(self))
        self.assertEqual(len(SEEDED_FAILURE_TESTS), len(set(SEEDED_FAILURE_TESTS.values())))
        for failure in quality["seeded_failures"]:
            with self.subTest(failure=failure):
                self.assertIn(SEEDED_FAILURE_TESTS[failure], methods)


if __name__ == "__main__":
    unittest.main()
