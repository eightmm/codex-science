import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from codex_science.evidence import _validate_claim_register, _validate_study_table, validate_sidecars
from codex_science.reviewer_runtime import build_review_packet
from tests.test_reviewer_runtime import make_reviewed_run


def claim(kind=None):
    value = {"id": "C1", "text": "A bounded claim.", "permitted_inference": "bounded",
             "status": "supported", "falsifier": "counterevidence", "uncertainty": "limited",
             "next_action": "review"}
    if kind is not None:
        value["kind"] = kind
    return {"schema_version": 1, "claims": [value]}


def study(excerpt=None):
    value = {"study_id": "S1", "persistent_id": "doi:10.1/test", "title": "Study",
             "evidence_type": "primary", "included": True, "supports_claim_ids": ["C1"],
             "contradicts_claim_ids": []}
    if excerpt is not None:
        value["support_excerpts"] = [excerpt]
    return {"schema_version": 1, "studies": [value]}


class EvidenceSupportExcerptTests(unittest.TestCase):
    def test_claim_kind_enum_and_legacy_claim(self):
        _validate_claim_register(claim())
        for kind in ("descriptive", "associational", "causal", "confirmatory"):
            _validate_claim_register(claim(kind))
        with self.assertRaisesRegex(ValueError, "Invalid claim kind"):
            _validate_claim_register(claim("predictive"))

    def test_excerpt_occurrence_hash_and_not_found(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            root.mkdir()
            source = "The study found a meaningful association across the sampled cohort.\n"
            (root / "source.txt").write_text(source, encoding="utf-8")
            digest = hashlib.sha256((root / "source.txt").read_bytes()).hexdigest()
            item = {"claim_id": "C1", "text": "found a meaningful   association across\nthe sampled cohort.",
                    "source_artifact": "source.txt", "source_sha256": digest}
            _validate_study_table(study(item), root)
            with self.assertRaisesRegex(ValueError, "excerpt_not_found"):
                _validate_study_table(study(dict(item, text="This phrase is not supported by any source.")), root)
            with self.assertRaisesRegex(ValueError, "excerpt_hash_mismatch"):
                _validate_study_table(study(dict(item, source_sha256="0" * 64)), root)
            missing_source = dict(item)
            missing_source.pop("source_artifact")
            with self.assertRaisesRegex(ValueError, "excerpt_source_missing"):
                _validate_study_table(study(missing_source), root)
            missing_hash = dict(item)
            missing_hash.pop("source_sha256")
            with self.assertRaisesRegex(ValueError, "excerpt_hash_mismatch"):
                _validate_study_table(study(missing_hash), root)

    def test_excerpt_requires_link_and_rejects_symlink_and_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "run"
            root.mkdir()
            content = "A sufficiently long excerpt appears in this source text."
            (root / "source.txt").write_text(content, encoding="utf-8")
            item = {"claim_id": "C2", "text": content, "source_artifact": "source.txt",
                    "source_sha256": hashlib.sha256(content.encode()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "not linked"):
                _validate_study_table(study(item), root)
            outside = root.parent / "outside.txt"
            outside.write_text(content, encoding="utf-8")
            (root / "linked.txt").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "excerpt_source_missing"):
                _validate_study_table(study(dict(item, claim_id="C1", source_artifact="linked.txt")), root)
            with self.assertRaisesRegex(ValueError, "excerpt_source_missing"):
                _validate_study_table(study(dict(item, claim_id="C1", source_artifact="../outside.txt")), root)
            with self.assertRaisesRegex(ValueError, "excerpt_source_missing"):
                _validate_study_table(study(dict(item, claim_id="C1", source_artifact="absent.txt")), root)

    def test_excerpt_claim_id_matches_trimmed_study_claim_ids(self):
        table = study({"claim_id": "C1", "text": "An excerpt with enough characters.",
                       "source_artifact": "source.txt", "source_sha256": "a" * 64})
        table["studies"][0]["supports_claim_ids"] = [" C1 "]
        normalized = _validate_study_table(table)
        self.assertEqual(["C1"], normalized["S1"]["supports_claim_ids"])

    def test_manifest_and_claim_register_kinds_must_agree(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            register = {"schema_version": 1, "claims": [
                {"id": "C1", "text": "A claim", "permitted_inference": "bounded", "status": "supported",
                 "falsifier": "counterevidence", "uncertainty": "limited", "next_action": "review",
                 "kind": "causal"},
            ]}
            path = root / "claims.json"
            path.write_text(json.dumps(register), encoding="utf-8")
            manifest = {"claims": [{"id": "C1", "kind": "descriptive"}],
                        "artifacts": [{"path": "claims.json", "kind": "claim-register"}]}
            with self.assertRaisesRegex(ValueError, "Claim C1 kind differs"):
                validate_sidecars(manifest, root, {"claims.json": path})

    def test_reviewer_kind_questions_are_additive_and_legacy_questions_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            path = make_reviewed_run(Path(temp))
            packet = build_review_packet(path, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            generic = packet["review_questions"]
            self.assertEqual(5, len(generic))
            import json
            manifest = json.loads(path.read_text())
            manifest["claims"][0]["kind"] = "causal"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            routed = build_review_packet(path, review_modes=["record"], created_at="2026-10-21T00:00:00Z")
            self.assertEqual(generic, routed["review_questions"][:len(generic)])
            self.assertTrue(any("confounding" in question for question in routed["review_questions"]))
            for kind, expected in (("confirmatory", "multiplicity"), ("associational", "causal language"),
                                   ("descriptive", "denominator")):
                manifest["claims"][0]["kind"] = kind
                path.write_text(json.dumps(manifest), encoding="utf-8")
                questions = build_review_packet(
                    path, review_modes=["record"], created_at="2026-10-21T00:00:00Z"
                )["review_questions"]
                self.assertTrue(any(expected in question for question in questions))


if __name__ == "__main__":
    unittest.main()
