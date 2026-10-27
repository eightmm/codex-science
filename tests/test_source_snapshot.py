import hashlib
import io
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import codex_science.source_snapshot as source_snapshot
from codex_science.artifact_store import describe_directory
from tests.test_compute_backends import initialize_repo


class SourceSnapshotUnitTests(unittest.TestCase):
    def _archive(self, entries: list[tuple[str, bytes]]) -> io.BytesIO:
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as bundle:
            for name, content in entries:
                item = tarfile.TarInfo(name)
                item.size = len(content)
                item.mode = 0o640
                bundle.addfile(item, io.BytesIO(content))
        archive.seek(0)
        return archive

    def test_input_descriptors_allow_empty_and_reject_overlap_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            nested = root / "folder"
            nested.mkdir()
            (nested / "value.txt").write_text("kept", encoding="utf-8")
            before = sorted(path.name for path in root.iterdir())

            empty = source_snapshot._verify_inputs(root, [{"id": "optional", "path": None}])
            self.assertEqual("optional", empty[0]["id"])
            self.assertEqual(0, empty[0]["entry_count"])
            self.assertEqual({}, empty[0]["file_manifest"])

            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "requires an ID"):
                source_snapshot._verify_inputs(root, [{"id": "  ", "path": None}])
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "overlap.*parent.*child"):
                source_snapshot._verify_inputs(
                    root,
                    [
                        {"id": "parent", "path": "folder", "root_sha256": describe_directory(nested).root_sha256},
                        {
                            "id": "child",
                            "path": "folder/value.txt",
                            "sha256": hashlib.sha256(b"kept").hexdigest(),
                        },
                    ],
                )

            self.assertEqual(before, sorted(path.name for path in root.iterdir()))
            self.assertEqual("kept", (nested / "value.txt").read_text(encoding="utf-8"))

    def test_safe_extract_success_and_limits_at_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            destination = Path(tempdir) / "source"
            destination.mkdir()
            archive = self._archive([("nested/value.txt", b"abc")])
            with mock.patch.object(source_snapshot, "MAX_SOURCE_ENTRIES", 1), mock.patch.object(
                source_snapshot, "MAX_SOURCE_CONTENT_BYTES", 3
            ):
                source_snapshot._safe_extract(archive, destination)
            self.assertEqual(b"abc", (destination / "nested" / "value.txt").read_bytes())
            self.assertEqual(0o640, (destination / "nested" / "value.txt").stat().st_mode & 0o777)

            too_many = self._archive([("a", b""), ("b", b"")])
            with mock.patch.object(source_snapshot, "MAX_SOURCE_ENTRIES", 0):
                with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "entry limit"):
                    source_snapshot._safe_extract(too_many, destination)
            too_large = self._archive([("large", b"abcd")])
            with mock.patch.object(source_snapshot, "MAX_SOURCE_CONTENT_BYTES", 3):
                with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "bounded bundle limit"):
                    source_snapshot._safe_extract(too_large, destination)
            self.assertEqual(["nested"], sorted(path.name for path in destination.iterdir()))

    def test_materialize_outputs_cwd_and_cleans_up_after_extraction_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            job_dir = root / "bundle"
            expected_spec = hashlib.sha256(b"job spec").hexdigest()
            receipt = source_snapshot.create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=[],
                job_spec_sha256=expected_spec,
                job_dir=job_dir,
            )
            self.assertEqual(commit, source_snapshot.validate_source_receipt(receipt)["commit"])
            self.assertEqual(source_snapshot.SOURCE_ARCHIVE_NAME, receipt["archive"]["path"])
            self.assertGreater(receipt["archive"]["size_bytes"], 0)
            cwd = source_snapshot.materialize_source_bundle(
                job_dir, receipt, expected_job_spec_sha256=expected_spec
            )
            self.assertEqual(job_dir / "source", cwd)
            self.assertEqual("committed\n", (cwd / "source.txt").read_text(encoding="utf-8"))
            self.assertEqual(cwd, source_snapshot.materialized_working_directory(job_dir, receipt))

            missing_cwd = dict(receipt)
            missing_cwd["worktree_relative_cwd"] = "missing"
            missing_cwd.pop("fingerprint")
            missing_cwd["fingerprint"] = source_snapshot._fingerprint(missing_cwd)
            failed_job = root / "failed"
            failed_job.mkdir()
            shutil.copyfile(job_dir / source_snapshot.SOURCE_ARCHIVE_NAME, failed_job / source_snapshot.SOURCE_ARCHIVE_NAME)
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "working directory is missing"):
                source_snapshot.materialize_source_bundle(
                    failed_job, missing_cwd, expected_job_spec_sha256=expected_spec
                )
            self.assertFalse((failed_job / "source").exists())

            bad_receipt = dict(receipt)
            bad_receipt["archive"] = dict(receipt["archive"], path="../outside")
            bad_receipt.pop("fingerprint")
            bad_receipt["fingerprint"] = source_snapshot._fingerprint(bad_receipt)
            existing = sorted(path.name for path in job_dir.iterdir())
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "safe relative path"):
                source_snapshot.materialize_source_bundle(
                    job_dir, bad_receipt, expected_job_spec_sha256=expected_spec
                )
            self.assertEqual(existing, sorted(path.name for path in job_dir.iterdir()))

    def test_receipt_validation_rejects_zero_size_and_wrong_job_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            job_dir = root / "bundle"
            expected_spec = hashlib.sha256(b"job spec").hexdigest()
            receipt = source_snapshot.create_git_source_bundle(
                working_directory=working,
                commit=commit,
                inputs=[],
                job_spec_sha256=expected_spec,
                job_dir=job_dir,
            )
            names_before = sorted(path.name for path in job_dir.iterdir())

            zero_size = dict(receipt)
            zero_size["archive"] = dict(receipt["archive"], size_bytes=0)
            zero_size.pop("fingerprint")
            zero_size["fingerprint"] = source_snapshot._fingerprint(zero_size)
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "size is outside the bounded limit"):
                source_snapshot.validate_source_receipt(zero_size)

            other_spec = hashlib.sha256(b"other job spec").hexdigest()
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "different job spec"):
                source_snapshot.validate_source_receipt(receipt, expected_job_spec_sha256=other_spec)

            self.assertEqual(names_before, sorted(path.name for path in job_dir.iterdir()))
