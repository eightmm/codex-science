from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.artifacts import validate_bundle  # noqa: E402
from codex_science.review_seeding import score, seed  # noqa: E402

EXAMPLE = ROOT / "examples" / "literature-review-reviewed-run"
CLAIM = "claim-method-effect"
FIND = "supports an association within its population and endpoint"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewSeedingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "bundle"
        shutil.copytree(EXAMPLE, self.bundle)
        self.out = self.root / "out"
        self.key = self.root / "key.json"

    def spec(self, **overrides: object) -> Path:
        spec = {"schema_version": 1, "defect_id": "d1", "defect_class": "overreach", "file": "claims.json",
                "find": FIND, "replace": "proves a causal effect in all populations", "claim_id": CLAIM,
                "expected_min_severity": "major"}
        spec.update(overrides)
        path = self.root / "spec.json"
        path.write_text(json.dumps({k: v for k, v in spec.items() if v is not None}), encoding="utf-8")
        return path

    def response(self, name: str, findings: list[dict]) -> Path:
        path = self.root / name
        path.write_text(json.dumps({"findings": findings}), encoding="utf-8")
        return path

    def run_seed(self, **overrides: object) -> dict:
        return seed(self.bundle, self.spec(**overrides), self.out, self.key)

    def test_seed_leaves_valid_bundle_and_key_matches(self) -> None:
        before = sha(self.bundle / "claims.json")
        key = self.run_seed()
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        validate_bundle(manifest, self.out)
        self.assertEqual("pending", manifest["review"]["status"])
        self.assertEqual(sha(self.out / "claims.json"), key["file_sha256_after"])
        self.assertEqual(before, key["file_sha256_before"])
        self.assertNotEqual(before, key["file_sha256_after"])
        self.assertEqual(before, sha(EXAMPLE / "claims.json"))
        self.assertEqual(key, json.loads(self.key.read_text(encoding="utf-8")))
        self.assertFalse((self.out / "review.json").exists())

    def test_refusals_leave_nothing_behind(self) -> None:
        cases = [({"find": "absent text"}, "found 0"), ({"find": "e"}, "found "),
                 ({"file": "../outside.txt"}, "escapes"), ({"file": "/etc/hostname"}, "escapes"),
                 ({"file": "missing.json"}, "not a regular file"), ({"find": ""}, "non-empty"),
                 ({"expected_min_severity": "minor"}, "expected_min_severity")]
        for overrides, message in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, message):
                    self.run_seed(**overrides)
                self.assertFalse(self.out.exists())
                self.assertFalse(self.key.exists())

    def test_binary_file_refused(self) -> None:
        (self.bundle / "blob.bin").write_bytes(b"\xff\x00abc")
        with self.assertRaisesRegex(ValueError, "text artifact"):
            self.run_seed(file="blob.bin", find="abc")

    def test_out_and_key_placement_refused(self) -> None:
        self.out.mkdir()
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_seed()
        self.out.rmdir()
        with self.assertRaisesRegex(ValueError, "inside --bundle"):
            seed(self.bundle, self.spec(), self.bundle / "nested", self.key)
        with self.assertRaisesRegex(ValueError, "inside --out"):
            seed(self.bundle, self.spec(), self.out, self.out / "key.json")
        self.assertFalse(self.out.exists())

    def test_control_copy_unchanged_except_review_archival(self) -> None:
        key = self.run_seed(defect_class="control", file=None, find=None, replace=None, claim_id=None)
        self.assertIsNone(key["file_sha256_after"])
        manifest = json.loads((self.out / "manifest.json").read_text(encoding="utf-8"))
        validate_bundle(manifest, self.out)
        source = {p.relative_to(self.bundle).as_posix(): sha(p) for p in self.bundle.rglob("*") if p.is_file()}
        copy = {p.relative_to(self.out).as_posix(): sha(p) for p in self.out.rglob("*") if p.is_file()}
        changed = {path for path in source.keys() | copy.keys() if source.get(path) != copy.get(path)}
        self.assertIn("review.json", changed)
        self.assertTrue(all(path in {"manifest.json", "review.json"} or "review-rounds" in path for path in changed), changed)
        self.assertNotIn("claims.json", changed)

    def test_control_spec_with_find_refused(self) -> None:
        with self.assertRaisesRegex(ValueError, "control"):
            self.run_seed(defect_class="control")

    def test_score_defect_cases(self) -> None:
        self.run_seed()
        finding = {"id": "f1", "severity": "major", "affected_claim_id": CLAIM}
        caught = self.response("caught.json", [{"id": "x", "severity": "minor"}, finding])
        minor = self.response("minor.json", [dict(finding, severity="minor")])
        by_path = self.response("path.json", [{"id": "p", "severity": "critical", "affected_claim_id": "other",
                                               "evidence": [{"artifact_path": "claims.json"}]}])
        miss = self.response("miss.json", [{"id": "m", "severity": "critical", "affected_claim_id": "other",
                                            "evidence": [{"artifact_path": "report.md"}]}])
        empty = self.response("empty.json", [])
        report = score(self.key, [caught, minor, by_path, miss, empty])
        self.assertIn("not a sensitivity estimate", report["evidence_boundary"])
        results = report["results"]
        self.assertEqual([True, False, True, False, False], [r["caught"] for r in results])
        self.assertEqual([True, True, True, False, False], [r["caught_any_severity"] for r in results])
        self.assertEqual(["f1"], results[0]["matched_finding_ids"])
        self.assertEqual(["p"], results[2]["matched_finding_ids"])

    def test_score_path_only_key_and_critical_threshold(self) -> None:
        self.run_seed(claim_id=None, expected_min_severity="critical")
        major = self.response("major.json", [{"id": "a", "severity": "major", "evidence": [{"artifact_path": "claims.json"}]}])
        critical = self.response("critical.json", [{"id": "b", "severity": "critical", "evidence": [{"artifact_path": "claims.json"}]}])
        wrong_claim = self.response("claim.json", [{"id": "c", "severity": "critical", "affected_claim_id": CLAIM}])
        results = score(self.key, [major, critical, wrong_claim])["results"]
        self.assertEqual([False, True, False], [r["caught"] for r in results])
        self.assertTrue(results[0]["caught_any_severity"])

    def test_score_control_false_positive(self) -> None:
        self.run_seed(defect_class="control", file=None, find=None, replace=None, claim_id=None)
        clean = self.response("clean.json", [{"id": "a", "severity": "minor"}, {"id": "b", "severity": "suggestion"}])
        dirty = self.response("dirty.json", [{"id": "c", "severity": "major"}])
        results = score(self.key, [clean, dirty])["results"]
        self.assertEqual([False, True], [r["false_positive"] for r in results])
        self.assertEqual(["c"], results[1]["serious_finding_ids"])

    def test_score_rejects_malformed_input(self) -> None:
        self.run_seed()
        bad = self.root / "bad.json"
        bad.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "findings"):
            score(self.key, [bad])
        with self.assertRaisesRegex(ValueError, "at least one"):
            score(self.key, [])


if __name__ == "__main__":
    unittest.main()
