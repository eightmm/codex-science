import copy
import tempfile
import unittest
from pathlib import Path

from codex_science.action_connectors import (
    ActionLedger,
    ActionSpec,
    build_action_approval,
    build_preview,
    execute_action,
    validate_action_approval,
    validate_preview,
)


class FakeAdapter:
    connector_name = "fake-lab"

    def __init__(self) -> None:
        self.state = {"object_id": "sample-1", "status": "draft", "version": 1}
        self.execute_count = 0

    def snapshot(self, spec: ActionSpec):
        return copy.deepcopy(self.state)

    def preview(self, spec: ActionSpec, before):
        return {"operation": spec.operation, "changes": {"status": spec.parameters["status"]}, "before_version": before["version"]}

    def execute(self, spec: ActionSpec, preview):
        self.execute_count += 1
        self.state = {**self.state, "status": spec.parameters["status"], "version": self.state["version"] + 1}
        return {"after_state": copy.deepcopy(self.state), "remote_object_ids": [self.state["object_id"]], "provider_receipt": {"request_id": "provider-1"}}


def write_spec() -> ActionSpec:
    return ActionSpec.from_payload(
        {
            "schema_version": 1,
            "connector": "fake-lab",
            "operation": "publish-sample",
            "mode": "write",
            "target": "workspace-1/sample-1",
            "parameters": {"status": "published"},
            "requested_scopes": ["sample:read", "sample:write"],
            "idempotency_key": "publish-sample-1-v1",
            "approval_required": True,
            "destructive": False,
            "paid": False,
            "sensitive_data": False,
            "compensation": "Set status back to draft through a separately approved action."
        }
    )


class ActionConnectorTests(unittest.TestCase):
    def test_write_preview_approval_execution_and_idempotency(self) -> None:
        adapter = FakeAdapter()
        spec = write_spec()
        preview = build_preview(adapter, spec, created_at="2026-07-21T00:00:00Z")
        validate_preview(preview, spec)
        self.assertFalse(preview["executed"])
        approval = build_action_approval(
            preview,
            approved_by="jaemin",
            approved_scopes=["sample:read", "sample:write"],
            approved_at="2026-07-21T00:01:00Z",
        )
        validate_action_approval(approval, preview)
        with tempfile.TemporaryDirectory() as tempdir:
            ledger = ActionLedger(Path(tempdir) / "actions.sqlite")
            receipt = execute_action(
                adapter,
                spec,
                preview,
                approval=approval,
                ledger=ledger,
                executed_at="2026-07-21T00:02:00Z",
            )
            self.assertEqual("executed", receipt["status"])
            self.assertNotEqual(receipt["before_state_sha256"], receipt["after_state_sha256"])
            self.assertEqual(["sample-1"], receipt["remote_object_ids"])
            repeated = execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
            self.assertEqual(receipt, repeated)
            self.assertEqual(1, adapter.execute_count)

    def test_write_requires_exact_approval_and_unchanged_before_state(self) -> None:
        adapter = FakeAdapter()
        spec = write_spec()
        preview = build_preview(adapter, spec, created_at="2026-07-21T00:00:00Z")
        with tempfile.TemporaryDirectory() as tempdir:
            ledger = ActionLedger(Path(tempdir) / "actions.sqlite")
            with self.assertRaisesRegex(ValueError, "requires explicit approval"):
                execute_action(adapter, spec, preview, approval=None, ledger=ledger)
            approval = build_action_approval(preview, approved_by="jaemin", approved_scopes=["sample:read", "sample:write"])
            adapter.state["version"] = 2
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                execute_action(adapter, spec, preview, approval=approval, ledger=ledger)

    def test_approval_scope_and_idempotency_key_cannot_be_reused_for_other_spec(self) -> None:
        adapter = FakeAdapter()
        spec = write_spec()
        preview = build_preview(adapter, spec)
        with self.assertRaisesRegex(ValueError, "do not cover"):
            build_action_approval(preview, approved_by="jaemin", approved_scopes=["sample:read"])
        approval = build_action_approval(preview, approved_by="jaemin", approved_scopes=["sample:read", "sample:write"])
        with tempfile.TemporaryDirectory() as tempdir:
            ledger = ActionLedger(Path(tempdir) / "actions.sqlite")
            execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
            changed = ActionSpec.from_payload({**spec.to_dict(), "parameters": {"status": "archived"}})
            changed_preview = build_preview(adapter, changed)
            changed_approval = build_action_approval(changed_preview, approved_by="jaemin", approved_scopes=["sample:read", "sample:write"])
            with self.assertRaisesRegex(ValueError, "different spec"):
                execute_action(adapter, changed, changed_preview, approval=changed_approval, ledger=ledger)

    def test_credentials_are_out_of_band_and_write_cannot_disable_approval(self) -> None:
        base = write_spec().to_dict()
        with self.assertRaisesRegex(ValueError, "credential-like"):
            ActionSpec.from_payload({**base, "parameters": {"api_token": "secret"}})
        with self.assertRaisesRegex(ValueError, "must require approval"):
            ActionSpec.from_payload({**base, "approval_required": False})


if __name__ == "__main__":
    unittest.main()
