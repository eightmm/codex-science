import copy
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from codex_science.action_connectors import (
    ActionLedger,
    ActionSpec,
    build_action_approval,
    build_preview,
    execute_action,
    validate_action_approval,
    validate_action_receipt,
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


def rehash_payload(payload: dict) -> dict:
    material = copy.deepcopy(payload)
    material.pop("fingerprint", None)
    if material.get("status") == "preview":
        material.pop("preview_id", None)
    digest = hashlib.sha256(
        json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if material.get("status") == "preview":
        material["preview_id"] = f"preview-{digest[:20]}"
    return {**material, "fingerprint": digest}


class ActionConnectorTests(unittest.TestCase):
    def assert_refused_before_execution(self, adapter, spec, preview, approval, message) -> None:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        ledger = ActionLedger(directory / "actions.sqlite")
        state = copy.deepcopy(adapter.state)
        with patch.object(adapter, "execute", wraps=adapter.execute) as execute:
            with self.assertRaisesRegex(ValueError, message):
                execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
            execute.assert_not_called()
        self.assertEqual(state, adapter.state)
        self.assertIsNone(ledger.get(spec.idempotency_key))

    def test_substituted_or_changed_adapter_proposal_is_refused(self) -> None:
        spec = write_spec()
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        for changes in ({}, [], 0, None, "malformed", {"changes": {"status": "archived"}}):
            with self.subTest(changes=changes):
                forged = rehash_payload({**preview, "proposed_changes": changes})
                approval = build_action_approval(forged, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
                self.assert_refused_before_execution(
                    FakeAdapter(), spec, forged, approval,
                    "preview proposed_changes do not match the adapter proposal; create a new preview",
                )
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        with patch.object(adapter, "preview", return_value={"changes": {"status": "archived"}}):
            self.assert_refused_before_execution(
                adapter, spec, preview, approval,
                "preview proposed_changes do not match the adapter proposal; create a new preview",
            )

    def test_read_flags_require_validated_approval_even_on_replay(self) -> None:
        for flag in ("approval_required", "paid", "sensitive_data"):
            with self.subTest(flag=flag):
                spec = ActionSpec.from_payload({**write_spec().to_dict(), "mode": "read", "approval_required": False, flag: True})
                adapter = FakeAdapter()
                preview = build_preview(adapter, spec)
                self.assert_refused_before_execution(adapter, spec, preview, None, "action requires explicit approval")
                self.assert_refused_before_execution(adapter, spec, preview, {}, "valid action approval is required")
                approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
                directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
                ledger = ActionLedger(directory / "actions.sqlite")
                receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
                self.assertEqual(approval["fingerprint"], receipt["approval_fingerprint"])
                self.assertEqual(receipt, execute_action(adapter, spec, preview, approval=approval, ledger=ledger))
                other = build_action_approval(preview, approved_by="other-reviewer", approved_scopes=list(spec.requested_scopes))
                with self.assertRaisesRegex(ValueError, "replayed action was approved by a different approval"):
                    execute_action(adapter, spec, preview, approval=other, ledger=ledger)
                self.assertEqual(receipt, ledger.get(spec.idempotency_key))
                with self.assertRaisesRegex(ValueError, "action requires explicit approval"):
                    execute_action(adapter, spec, preview, approval=None, ledger=ledger)
                self.assertEqual(1, adapter.execute_count)
        spec = replace(write_spec(), mode="read", approval_required=False)
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        ledger = ActionLedger(directory / "actions.sqlite")
        receipt = execute_action(adapter, spec, preview, approval=None, ledger=ledger)
        self.assertEqual(receipt, execute_action(adapter, spec, preview, approval=None, ledger=ledger))
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        with self.assertRaisesRegex(ValueError, "replayed action was approved by a different approval"):
            execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
        self.assertEqual(receipt, ledger.get(spec.idempotency_key))
        self.assertEqual(1, adapter.execute_count)

    def test_direct_spec_cannot_bypass_write_or_destructive_invariants(self) -> None:
        for spec, message in (
            (replace(write_spec(), approval_required=False), "write actions must require approval"),
            (replace(write_spec(), mode="read", approval_required=False, destructive=True), "destructive actions must use write mode"),
        ):
            with self.subTest(message=message):
                adapter = FakeAdapter()
                preview = build_preview(adapter, spec)
                self.assert_refused_before_execution(adapter, spec, preview, None, message)

    def test_preview_before_state_must_match_its_digest(self) -> None:
        spec = write_spec()
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        validate_preview(preview, spec)
        for before in ({}, [], 0, None, "malformed", {"version": 2}):
            with self.subTest(before=before):
                forged = rehash_payload({**preview, "before_state": before})
                with self.assertRaisesRegex(ValueError, "action preview before_state does not match before_state_sha256"):
                    validate_preview(forged, spec)
                self.assert_refused_before_execution(
                    adapter, spec, forged, None,
                    "action preview before_state does not match before_state_sha256",
                )

    def test_execution_rechecks_expected_before_digest(self) -> None:
        adapter = FakeAdapter()
        base = write_spec()
        preview = build_preview(adapter, base)
        for expected in ("0" * 64, "", 0, "malformed"):
            with self.subTest(expected=expected):
                spec = replace(base, expected_before_sha256=expected)
                forged = rehash_payload({**preview, "action_spec_sha256": spec.fingerprint})
                approval = build_action_approval(forged, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
                self.assert_refused_before_execution(
                    FakeAdapter(), spec, forged, approval,
                    "current remote state does not match expected_before_sha256",
                )
        spec = replace(base, expected_before_sha256=preview["before_state_sha256"])
        preview = build_preview(adapter, spec)
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ActionLedger(directory / "actions.sqlite"))
        validate_action_receipt(receipt, spec)
        self.assertEqual(1, adapter.execute_count)

    def test_supplied_read_approval_is_validated_before_execution(self) -> None:
        spec = replace(write_spec(), mode="read", approval_required=False)
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        for invalid, message in (
            ({}, "valid action approval is required"),
            (rehash_payload({**approval, "approved": False}), "valid action approval is required"),
            (rehash_payload({**approval, "approved_scopes": []}), "approved scopes do not cover requested scopes"),
            (rehash_payload({**approval, "target": "other-target"}), "approval target does not match preview"),
            ({**approval, "fingerprint": "malformed"}, "action approval fingerprint mismatch"),
        ):
            with self.subTest(message=message):
                self.assert_refused_before_execution(FakeAdapter(), spec, preview, invalid, message)
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        ledger = ActionLedger(directory / "actions.sqlite")
        receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
        self.assertEqual(approval["fingerprint"], receipt["approval_fingerprint"])
        with self.assertRaisesRegex(ValueError, "valid action approval is required"):
            execute_action(adapter, spec, preview, approval={}, ledger=ledger)
        self.assertEqual(1, adapter.execute_count)

    def test_receipt_can_be_bound_to_supplied_approval(self) -> None:
        spec = write_spec()
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ActionLedger(directory / "actions.sqlite"))
        try:
            validate_action_receipt(receipt, spec, approval=approval)
        except TypeError as error:
            self.fail(f"receipt approval binding is unavailable: {error}")
        validate_action_receipt(receipt, spec, approval)
        for field, values in (("approved_by", ("other-reviewer", "", 0, None)), ("approved_scopes", ([], 0, None, "malformed"))):
            for value in values:
                with self.subTest(field=field, value=value):
                    with self.assertRaisesRegex(ValueError, "action approval fingerprint mismatch"):
                        validate_action_receipt(receipt, spec, approval={**approval, field: value})
        for approved in (False, 0, None, "", [], "true", 1):
            with self.subTest(approved=approved):
                with self.assertRaisesRegex(ValueError, "valid action approval is required"):
                    validate_action_receipt(receipt, spec, approval={**approval, "approved": approved})
        denied = rehash_payload({**approval, "approved": False})
        denied_receipt = rehash_payload({**receipt, "approval_fingerprint": denied["fingerprint"]})
        with self.assertRaisesRegex(ValueError, "valid action approval is required"):
            validate_action_receipt(denied_receipt, spec, approval=denied)
        for digest in (None, "", 0, "0" * 64, [], "malformed"):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "action approval fingerprint mismatch"):
                    validate_action_receipt(receipt, spec, approval={**approval, "fingerprint": digest})
        for field in ("preview_id", "action_spec_sha256", "preview_fingerprint", "idempotency_key"):
            for value in (None, "", 0, "other"):
                with self.subTest(field=field, value=value):
                    other = rehash_payload({**approval, field: value})
                    forged = rehash_payload({**receipt, "approval_fingerprint": other["fingerprint"]})
                    with self.assertRaisesRegex(ValueError, "action receipt approval does not match"):
                        validate_action_receipt(forged, spec, approval=other)

    def executed_receipt(self, mode: str = "write") -> tuple[ActionSpec, dict]:
        spec = ActionSpec.from_payload({**write_spec().to_dict(), "mode": mode, "approval_required": mode == "write"})
        adapter = FakeAdapter()
        preview = build_preview(adapter, spec)
        approval = None if mode == "read" else build_action_approval(
            preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes),
        )
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ActionLedger(directory / "actions.sqlite"))
        return spec, receipt

    def test_preview_mirrored_fields_match_spec(self) -> None:
        spec = write_spec()
        preview = build_preview(FakeAdapter(), spec)
        validate_preview(preview, spec)
        changes = {
            "connector": "other-lab",
            "operation": "archive-sample",
            "mode": "read",
            "target": "workspace-1/sample-2",
            "idempotency_key": "other-action",
            "requested_scopes": ["sample:read"],
            "approval_required": False,
            "destructive": True,
            "paid": True,
            "sensitive_data": True,
            "compensation": None,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                forged = rehash_payload({**preview, field: value})
                with self.assertRaisesRegex(ValueError, f"action preview {field} does not match spec"):
                    validate_preview(forged, spec)
        for scopes in ([], 0, None, "sample:read", {}, list(reversed(spec.requested_scopes))):
            with self.subTest(scopes=scopes):
                forged = rehash_payload({**preview, "requested_scopes": scopes})
                with self.assertRaisesRegex(ValueError, "action preview requested_scopes does not match spec"):
                    validate_preview(forged, spec)
        no_scopes = ActionSpec.from_payload({**spec.to_dict(), "requested_scopes": []})
        validate_preview(build_preview(FakeAdapter(), no_scopes), no_scopes)

    def test_preview_target_mismatch_is_refused_before_adapter_calls(self) -> None:
        spec = write_spec()
        adapter = FakeAdapter()
        preview = rehash_payload({**build_preview(adapter, spec), "target": "workspace-1/sample-2"})
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        with tempfile.TemporaryDirectory() as directory:
            ledger = ActionLedger(Path(directory) / "actions.sqlite")
            with patch.object(adapter, "execute", wraps=adapter.execute) as execute, patch.object(adapter, "snapshot", wraps=adapter.snapshot) as snapshot:
                with self.assertRaisesRegex(ValueError, "action preview target does not match spec"):
                    execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
                execute.assert_not_called()
                snapshot.assert_not_called()
            self.assertEqual(0, adapter.execute_count)
            self.assertIsNone(ledger.get(spec.idempotency_key))

    def test_approval_mirrored_fields_match_preview(self) -> None:
        spec = write_spec()
        preview = build_preview(FakeAdapter(), spec)
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=list(spec.requested_scopes))
        for field, value in (("connector", "other-lab"), ("operation", "archive-sample"), ("target", "workspace-1/sample-2")):
            with self.subTest(field=field):
                forged = rehash_payload({**approval, field: value})
                with self.assertRaisesRegex(ValueError, f"approval {field} does not match preview"):
                    validate_action_approval(forged, preview)

    def test_approval_scopes_are_nonempty_strings_covering_requested_scopes(self) -> None:
        spec = write_spec()
        preview = build_preview(FakeAdapter(), spec)
        scopes = list(spec.requested_scopes)
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=scopes)
        for valid in (scopes, scopes + ["sample:archive"]):
            validate_action_approval(rehash_payload({**approval, "approved_scopes": valid}), preview)
        for invalid in ([], 0, None, {}, "sample:read sample:write", ["sample:read"], scopes + [""], scopes + [" "], scopes + [0], scopes + [None], scopes + [[]]):
            with self.subTest(scopes=invalid):
                forged = rehash_payload({**approval, "approved_scopes": invalid})
                with self.assertRaisesRegex(ValueError, "approved scopes do not cover requested scopes"):
                    validate_action_approval(forged, preview)
        no_scopes = ActionSpec.from_payload({**spec.to_dict(), "requested_scopes": []})
        empty_preview = build_preview(FakeAdapter(), no_scopes)
        empty_approval = build_action_approval(empty_preview, approved_by="reviewer", approved_scopes=[])
        validate_action_approval(empty_approval, empty_preview)

    def test_receipt_mode_must_be_supported(self) -> None:
        _, receipt = self.executed_receipt()
        for mode in (None, 0, [], {}, "execute"):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "invalid action receipt mode"):
                    validate_action_receipt(rehash_payload({**receipt, "mode": mode}))
        with self.assertRaisesRegex(ValueError, "mode is required"):
            validate_action_receipt(rehash_payload({**receipt, "mode": ""}))

    def test_write_receipt_requires_approval_digest(self) -> None:
        spec, receipt = self.executed_receipt()
        validate_action_receipt(receipt, spec)
        validate_action_receipt(rehash_payload({**receipt, "remote_object_ids": []}), spec)
        for digest in (None, "", 0, "0" * 63, "0" * 65, "g" * 64, [], {}):
            with self.subTest(digest=digest):
                forged = rehash_payload({**receipt, "approval_fingerprint": digest})
                with self.assertRaisesRegex(ValueError, "write action receipt requires approval_fingerprint"):
                    validate_action_receipt(forged)
        validate_action_receipt(rehash_payload({**receipt, "approval_fingerprint": "0" * 64}), spec)

    def test_read_receipt_allows_only_optional_approval_digest(self) -> None:
        spec, receipt = self.executed_receipt("read")
        self.assertIsNone(receipt["approval_fingerprint"])
        validate_action_receipt(receipt, spec)
        validate_action_receipt(rehash_payload({**receipt, "approval_fingerprint": "0" * 64}), spec)
        for digest in ("", 0, "0" * 63, "0" * 65, "g" * 64, [], {}):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "approval_fingerprint must be a SHA-256 digest|approval_fingerprint is required"):
                    validate_action_receipt(rehash_payload({**receipt, "approval_fingerprint": digest}))

    def test_receipt_mirrored_fields_match_spec(self) -> None:
        spec, receipt = self.executed_receipt()
        for field, value in (("connector", "other-lab"), ("operation", "archive-sample"), ("mode", "read"), ("target", "workspace-1/sample-2"), ("idempotency_key", "other-action")):
            with self.subTest(field=field):
                forged = rehash_payload({**receipt, field: value})
                with self.assertRaisesRegex(ValueError, f"action receipt {field} does not match spec"):
                    validate_action_receipt(forged, spec)

    def test_write_preview_approval_execution_and_idempotency(self) -> None:
        adapter = FakeAdapter()
        spec = write_spec()
        preview = build_preview(adapter, spec, created_at="2026-07-21T00:00:00Z")
        validate_preview(preview, spec)
        self.assertFalse(preview["executed"])
        approval = build_action_approval(
            preview,
            approved_by="reviewer",
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
            approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=["sample:read", "sample:write"])
            adapter.state["version"] = 2
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                execute_action(adapter, spec, preview, approval=approval, ledger=ledger)

    def test_approval_scope_and_idempotency_key_cannot_be_reused_for_other_spec(self) -> None:
        adapter = FakeAdapter()
        spec = write_spec()
        preview = build_preview(adapter, spec)
        with self.assertRaisesRegex(ValueError, "do not cover"):
            build_action_approval(preview, approved_by="reviewer", approved_scopes=["sample:read"])
        approval = build_action_approval(preview, approved_by="reviewer", approved_scopes=["sample:read", "sample:write"])
        with tempfile.TemporaryDirectory() as tempdir:
            ledger = ActionLedger(Path(tempdir) / "actions.sqlite")
            execute_action(adapter, spec, preview, approval=approval, ledger=ledger)
            changed = ActionSpec.from_payload({**spec.to_dict(), "parameters": {"status": "archived"}})
            changed_preview = build_preview(adapter, changed)
            changed_approval = build_action_approval(changed_preview, approved_by="reviewer", approved_scopes=["sample:read", "sample:write"])
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
