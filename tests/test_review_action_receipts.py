import hashlib
import tempfile
import unittest
from pathlib import Path

from codex_science.action_connectors import (
    ActionLedger,
    ActionSpec,
    build_action_approval,
    build_preview,
    execute_action,
    validate_action_receipt,
)
from codex_science.artifacts import add_artifact, new_manifest, write_manifest
from codex_science.reviewer_runtime import build_review_packet, finalize_review_response
from codex_science.review_receipts import validate_review_receipt


class Adapter:
    connector_name = "fixture"

    def __init__(self) -> None:
        self.state = {"id": "x", "version": 1}

    def snapshot(self, spec):
        return dict(self.state)

    def preview(self, spec, before):
        return {"change": spec.parameters}

    def execute(self, spec, preview):
        self.state = {"id": "x", "version": 2}
        return {"after_state": dict(self.state), "remote_object_ids": ["x"]}


def manifest_path(root: Path) -> Path:
    artifact = root / "value.json"
    artifact.write_text('{"value": 1}\n', encoding="utf-8")
    manifest = new_manifest(
        "review-unicode",
        "검토 패킷의 해시가 유니코드에서도 안정적인가?",
        [{"id": "record", "description": "Record value", "status": "completed"}],
    )
    manifest["claims"] = [{"id": "C1", "text": "값이 기록되었다.", "evidence": ["value.json"]}]
    manifest["review"] = {"status": "passed", "findings": []}
    add_artifact(manifest, "value.json", kind="result", sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())
    path = root / "manifest.json"
    write_manifest(manifest, path)
    return path


class ReviewActionReceiptTests(unittest.TestCase):
    def test_unicode_review_receipt_uses_canonical_review_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            packet = build_review_packet(manifest_path(root), review_modes=["record"], created_at="2026-07-21T00:00:00Z")
            artifact = packet["artifacts"][0]
            receipt = finalize_review_response(
                packet,
                {
                    "schema_version": 1,
                    "review_task_id": packet["review_task_id"],
                    "packet_fingerprint": packet["fingerprint"],
                    "reviewer": "독립-검토자",
                    "independent": True,
                    "review_modes": ["record"],
                    "reviewed_claim_ids": ["C1"],
                    "reviewed_artifacts": [{"path": artifact["path"], "sha256": artifact["sha256"]}],
                    "findings": [],
                    "limitations": ["원시 장비 파일은 검토하지 못했다."],
                    "status": "passed",
                },
            )
            validate_review_receipt(receipt)
            self.assertEqual("passed", receipt["status"])

    def test_action_receipt_is_bound_to_exact_spec(self) -> None:
        adapter = Adapter()
        spec = ActionSpec.from_payload(
            {
                "connector": "fixture",
                "operation": "update",
                "mode": "write",
                "target": "object/x",
                "parameters": {"value": 2},
                "requested_scopes": ["object:write"],
                "idempotency_key": "fixture-update-x-v1",
            }
        )
        preview = build_preview(adapter, spec, created_at="2026-07-21T00:00:00Z")
        approval = build_action_approval(preview, approved_by="jaemin", approved_scopes=["object:write"], approved_at="2026-07-21T00:01:00Z")
        with tempfile.TemporaryDirectory() as tempdir:
            receipt = execute_action(adapter, spec, preview, approval=approval, ledger=ActionLedger(Path(tempdir) / "ledger.sqlite"), executed_at="2026-07-21T00:02:00Z")
            validate_action_receipt(receipt, spec)
            changed = ActionSpec.from_payload({**spec.to_dict(), "parameters": {"value": 3}, "idempotency_key": "fixture-update-x-v2"})
            with self.assertRaisesRegex(ValueError, "different spec"):
                validate_action_receipt(receipt, changed)

    def test_mismatched_adapter_is_rejected_before_execution(self) -> None:
        class Wrong(Adapter):
            connector_name = "wrong"

        spec = ActionSpec.from_payload(
            {
                "connector": "fixture",
                "operation": "read",
                "mode": "read",
                "target": "object/x",
                "parameters": {},
                "requested_scopes": ["object:read"],
                "idempotency_key": "fixture-read-x-v1",
            }
        )
        preview = build_preview(Adapter(), spec)
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaisesRegex(ValueError, "adapter connector"):
                execute_action(Wrong(), spec, preview, approval=None, ledger=ActionLedger(Path(tempdir) / "ledger.sqlite"))


if __name__ == "__main__":
    unittest.main()
