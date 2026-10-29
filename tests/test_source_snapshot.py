import hashlib
import io
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from typing import BinaryIO
from unittest import mock

import codex_science.source_snapshot as source_snapshot
from codex_science.artifact_store import describe_directory
from tests.test_compute_backends import git, initialize_repo


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

    def test_safe_extract_preserves_whitespace_names_and_refuses_blank_names(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            entries = [(" leading.txt", b"a"), ("trailing.txt ", b"b"), (" dir / file ", b"")]
            source_snapshot._safe_extract(self._archive(entries), root)
            for name, content in entries:
                self.assertTrue((root / name).is_file(), name)
                self.assertEqual(content, (root / name).read_bytes())
            self.assertFalse((root / "leading.txt").exists())
            self.assertFalse((root / "trailing.txt").exists())
            for name in ("", " ", "\t", "../bad", "/bad", ".git/config"):
                with self.subTest(name=name), self.assertRaises(source_snapshot.SourceSnapshotError):
                    source_snapshot._safe_extract(self._archive([(name, b"")]), root)

    def test_git_bundle_and_input_paths_preserve_whitespace_names(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _ = initialize_repo(root)
            entries = [(" leading.txt", "a"), ("trailing.txt ", "b"), (" dir / file ", "")]
            for name, content in entries:
                path = working / name
                path.parent.mkdir(exist_ok=True)
                path.write_text(content, encoding="utf-8")
            git(working, "add", ".")
            git(working, "commit", "-qm", "whitespace fixture")
            commit = git(working, "rev-parse", "HEAD")
            job_dir = root / "bundle"
            expected_spec = hashlib.sha256(b"job spec").hexdigest()
            receipt = source_snapshot.create_git_source_bundle(
                working_directory=working, commit=commit, inputs=[],
                job_spec_sha256=expected_spec, job_dir=job_dir,
            )
            cwd = source_snapshot.materialize_source_bundle(
                job_dir, receipt, expected_job_spec_sha256=expected_spec,
            )
            for name, content in entries:
                self.assertTrue((cwd / name).is_file(), name)
                self.assertEqual(content, (cwd / name).read_text(encoding="utf-8"))
            self.assertFalse((cwd / "leading.txt").exists())
            verified = source_snapshot._verify_inputs(working, [{
                "id": "spaced", "path": " leading.txt", "sha256": hashlib.sha256(b"a").hexdigest(),
            }])
            self.assertEqual(" leading.txt", verified[0]["path"])
            self.assertEqual(working / " leading.txt", verified[0]["target"])

    def test_safe_relative_rejects_nul(self) -> None:
        for name in ("\0", "nested/va\0lue.txt"):
            with self.subTest(name=name), self.assertRaisesRegex(
                source_snapshot.SourceSnapshotError, "safe relative path"
            ):
                source_snapshot._safe_relative(name, "input path")

    def test_git_bundle_preserves_repository_root_whitespace(self) -> None:
        for suffix in (" ", "\t", "\n", "\r"):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                working, commit = initialize_repo(root)
                renamed = root / ("repo" + suffix)
                working.rename(renamed)
                expected_spec = hashlib.sha256(b"job spec").hexdigest()
                job_dir = root / "bundle"
                receipt = source_snapshot.create_git_source_bundle(
                    working_directory=renamed, commit=commit, inputs=[],
                    job_spec_sha256=expected_spec, job_dir=job_dir,
                )
                cwd = source_snapshot.materialize_source_bundle(
                    job_dir, receipt, expected_job_spec_sha256=expected_spec,
                )
                self.assertEqual(commit, receipt["commit"])
                self.assertEqual("committed\n", (cwd / "source.txt").read_text(encoding="utf-8"))

    def test_directory_input_archive_round_trip_preserves_names_and_checks_merkle_root(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _ = initialize_repo(root)
            (working / ".gitignore").write_text("inputs/\n", encoding="utf-8")
            git(working, "add", ".gitignore")
            git(working, "commit", "-qm", "ignored directory input")
            commit = git(working, "rev-parse", "HEAD")
            directory = working / "inputs" / " dir "
            directory.mkdir(parents=True)
            entries = [(" leading.txt", b"a"), ("trailing.txt ", b"b"), (" nested / file ", b"")]
            for name, content in entries:
                path = directory / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(content)
            empty = working / "inputs" / "empty"
            empty.mkdir()
            inputs = [
                {"id": "spaced", "path": "inputs/ dir ", "root_sha256": describe_directory(directory).root_sha256},
                {"id": "empty", "path": "inputs/empty", "root_sha256": describe_directory(empty).root_sha256},
            ]
            expected_spec = hashlib.sha256(b"job spec").hexdigest()
            job_dir = root / "bundle"
            receipt = source_snapshot.create_git_source_bundle(
                working_directory=working, commit=commit, inputs=inputs,
                job_spec_sha256=expected_spec, job_dir=job_dir,
            )
            cwd = source_snapshot.materialize_source_bundle(
                job_dir, receipt, expected_job_spec_sha256=expected_spec,
            )
            for item in inputs:
                restored = cwd / item["path"]
                self.assertEqual(item["root_sha256"], describe_directory(restored).root_sha256)
            for name, content in entries:
                self.assertEqual(content, (cwd / "inputs" / " dir " / name).read_bytes())

            extract = source_snapshot._safe_extract

            def extract_with_changed_name(archive: BinaryIO, destination: Path) -> None:
                extract(archive, destination)
                original = destination / "inputs" / " dir " / "trailing.txt "
                original.rename(original.with_name("trailing.txt"))

            failed_job = root / "failed"
            with mock.patch.object(source_snapshot, "_safe_extract", side_effect=extract_with_changed_name):
                with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "digest mismatch"):
                    source_snapshot.create_git_source_bundle(
                        working_directory=working, commit=commit, inputs=inputs,
                        job_spec_sha256=expected_spec, job_dir=failed_job,
                    )
            self.assertEqual([], list(failed_job.iterdir()))
            archive_path = job_dir / source_snapshot.SOURCE_ARCHIVE_NAME
            before = archive_path.read_bytes()
            with mock.patch.object(source_snapshot, "_safe_extract", side_effect=extract_with_changed_name):
                with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "digest mismatch"):
                    source_snapshot.create_git_source_bundle(
                        working_directory=working, commit=commit, inputs=inputs,
                        job_spec_sha256=expected_spec, job_dir=job_dir,
                    )
            self.assertEqual(before, archive_path.read_bytes())
            self.assertEqual(["source", "source.tar"], sorted(path.name for path in job_dir.iterdir()))

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
