from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.artifacts import validate_bundle  # noqa: E402
import codex_science.review_seeding as review_seeding  # noqa: E402
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

    def run_seed(self, drop: tuple[str, ...] = (), strip: bool = False, **overrides: object) -> dict:
        return seed(self.bundle, self.spec(**overrides), self.out, self.key, drop, strip)

    def control(self, **kwargs: object) -> dict:
        return self.run_seed(defect_class="control", file=None, find=None, replace=None, claim_id=None, **kwargs)

    def assert_valid(self) -> None:
        validate_bundle(json.loads((self.out / "manifest.json").read_text(encoding="utf-8")), self.out)

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
        shutil.rmtree(self.out)
        self.key.unlink()
        for target in ("manifest.json", "review.json"):
            with self.subTest(target=target):
                with self.assertRaisesRegex(ValueError, "managed by the review flow"):
                    self.run_seed(file=target, find="passed", claim_id=None, replace="x")
        self.assertEqual(sha(self.bundle / "manifest.json"), sha(EXAMPLE / "manifest.json"))
        script = ROOT / "scripts" / "seed_review_defects.py"
        out, keyfile = self.root / "cli-out", self.root / "cli-key.json"
        done = subprocess.run([sys.executable, str(script), "seed", "--bundle", str(self.bundle), "--spec", str(self.spec()),
                               "--out", str(out), "--key", str(keyfile)], capture_output=True, text=True)
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertEqual(json.loads(keyfile.read_text(encoding="utf-8")), json.loads(done.stdout))
        self.assertIn("Archived prior review files", done.stderr)

    def test_refresh_erasing_seeded_defect_is_detected(self) -> None:
        def clobber(run_dir: Path, *args: object, **kwargs: object) -> None:
            (run_dir / "claims.json").write_bytes((EXAMPLE / "claims.json").read_bytes())
        with mock.patch.object(review_seeding, "refresh", clobber):
            with self.assertRaisesRegex(ValueError, "refresh altered"):
                self.run_seed()
        self.assertFalse(self.out.exists())
        self.assertFalse(self.key.exists())

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

    def test_foreign_out_and_bad_key_parent_leave_nothing_of_ours(self) -> None:
        real = review_seeding.load_spec

        def racing(path: Path) -> dict:
            self.out.mkdir()
            (self.out / "theirs.txt").write_text("keep", encoding="utf-8")
            return real(path)
        with mock.patch.object(review_seeding, "load_spec", racing):
            with self.assertRaisesRegex(ValueError, "already exists"):
                self.run_seed()
        self.assertEqual("keep", (self.out / "theirs.txt").read_text(encoding="utf-8"))
        self.assertFalse(self.key.exists())
        shutil.rmtree(self.out)
        blocker = self.root / "blocker"
        blocker.write_text("file", encoding="utf-8")
        for key in (blocker / "key.json", blocker / "sub" / "key.json"):
            with self.assertRaisesRegex(ValueError, "not a directory"):
                seed(self.bundle, self.spec(), self.out, key)
            self.assertFalse(self.out.exists())
        with mock.patch.object(review_seeding.tempfile, "mkstemp", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                self.run_seed()
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
        with self.assertRaisesRegex(ValueError, "inside --bundle"):
            seed(self.bundle, self.spec(), self.out, self.bundle / "key.json")
        link = self.root / "bundle-link"
        link.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "inside --bundle"):
            seed(self.bundle, self.spec(), self.out, link / "key.json")
        self.assertFalse((self.bundle / "key.json").exists())
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

    def test_control_spec_without_expected_severity_seeds(self) -> None:
        key = self.control(expected_min_severity=None)
        self.assertNotIn("expected_min_severity", key["spec"])
        self.assertEqual([], key["dropped"])
        self.assertFalse(key["stripped_review_history"])
        self.assert_valid()

    def test_unregistered_extra_file_needs_drop(self) -> None:
        (self.bundle / "reviewer-findings.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unclassified files: reviewer-findings.json"):
            self.run_seed()
        self.assertFalse(self.out.exists())
        self.assertFalse(self.key.exists())
        key = self.run_seed(drop=("reviewer-findings.json",))
        self.assertEqual(["reviewer-findings.json"], key["dropped"])
        self.assertFalse((self.out / "reviewer-findings.json").exists())
        self.assertTrue((self.bundle / "reviewer-findings.json").exists())
        self.assert_valid()

    def test_drop_refusals_leave_nothing_behind(self) -> None:
        (self.bundle / "extra").mkdir()
        (self.bundle / "extra" / "note.txt").write_text("x", encoding="utf-8")
        (self.root / "outside.txt").write_text("x", encoding="utf-8")
        (self.bundle / "link.txt").symlink_to(self.root / "outside.txt")
        absolute_alias = self.bundle / "absolute-alias"
        absolute_alias.symlink_to(self.bundle / "extra", target_is_directory=True)
        relative_alias = self.bundle / "relative-alias"
        relative_alias.symlink_to("extra", target_is_directory=True)
        source_bytes = {p.relative_to(self.bundle).as_posix(): p.read_bytes()
                        for p in self.bundle.rglob("*") if p.is_file() and not p.is_symlink()}
        cases = [("claims.json", "registered"), ("lanes", "registered"), ("manifest.json", "registered"),
                 ("../outside.txt", "escapes"), ("/etc/hostname", "escapes"), (".", "escapes"), ("", "escapes"),
                 ("link.txt", "symlink"), ("absolute-alias/note.txt", "symlink"),
                 ("relative-alias/note.txt", "symlink"), ("nothing.txt", "does not exist")]
        for path, message in cases:
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, message):
                    self.run_seed(drop=(path,))
                self.assertFalse(self.out.exists())
                self.assertFalse(self.key.exists())
                self.assertEqual(source_bytes, {p.relative_to(self.bundle).as_posix(): p.read_bytes()
                                                for p in self.bundle.rglob("*") if p.is_file() and not p.is_symlink()})
        for alias in ("absolute-alias", "relative-alias"):
            with self.subTest(spec_alias=alias):
                with self.assertRaisesRegex(ValueError, "symlink"):
                    self.run_seed(file=f"{alias}/note.txt", find="x", claim_id=None, replace="y")
                self.assertFalse(self.out.exists())
                self.assertFalse(self.key.exists())
                self.assertEqual(source_bytes, {p.relative_to(self.bundle).as_posix(): p.read_bytes()
                                                for p in self.bundle.rglob("*") if p.is_file() and not p.is_symlink()})
        (self.bundle / "extra" / "claims.json").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "seeded file"):
            self.run_seed(drop=("extra",), file="extra/claims.json", find="x", claim_id=None)
        self.assertTrue((self.bundle / "extra" / "note.txt").exists())

    def test_drop_directory_and_duplicates(self) -> None:
        (self.bundle / "extra").mkdir()
        (self.bundle / "extra" / "note.txt").write_text("x", encoding="utf-8")
        key = self.run_seed(drop=("extra", "extra/"))
        self.assertEqual(["extra"], key["dropped"])
        self.assertFalse((self.out / "extra").exists())
        self.assert_valid()

    def test_strip_review_history(self) -> None:
        kept = self.control()
        self.assertTrue((self.out / "review-rounds").exists())
        self.assertFalse(kept["stripped_review_history"])
        shutil.rmtree(self.out)
        self.key.unlink()
        before = {p.relative_to(self.bundle).as_posix() for p in self.bundle.rglob("*") if "review-rounds" in p.parts}
        key = self.control(strip=True)
        self.assertTrue(key["stripped_review_history"])
        self.assertFalse((self.out / "review-rounds").exists())
        self.assertEqual(key, json.loads(self.key.read_text(encoding="utf-8")))
        self.assertEqual(before, {p.relative_to(self.bundle).as_posix() for p in self.bundle.rglob("*") if "review-rounds" in p.parts})
        self.assert_valid()

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
