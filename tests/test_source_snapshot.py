import hashlib
import io
import os
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


SPEC_SHA256 = hashlib.sha256(b"job spec").hexdigest()


def _preflight_check(working: Path, commit: str) -> dict:
    return source_snapshot.preflight_git_source(working, commit, [])


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


class SourceSnapshotRepositoryGuardTests(unittest.TestCase):
    def _bundle(self, working: Path, commit: str, job_dir: Path) -> dict:
        return source_snapshot.create_git_source_bundle(
            working_directory=working, commit=commit, inputs=[],
            job_spec_sha256=SPEC_SHA256, job_dir=job_dir,
        )

    def test_filter_attribute_paths_are_refused_before_status_and_unset_filters_pass(self) -> None:
        for location in ("gitattributes", "info"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                working, _ = initialize_repo(root)
                marker = root / "clean-filter-ran"
                git(working, "config", "filter.fake.smudge", "sed s/pointer/real/")
                git(working, "config", "filter.fake.clean", f"touch '{marker}'; sed s/real/pointer/")
                (working / "sub").mkdir()
                (working / "sub" / "keep.txt").write_text("kept\n", encoding="utf-8")
                (working / "data dir").mkdir()
                (working / "data dir" / "é data.bin").write_text("real\n", encoding="utf-8")
                rule = "*.bin filter=fake\nkeep.txt -filter\n"
                if location == "gitattributes":
                    (working / ".gitattributes").write_text(rule, encoding="utf-8")
                else:
                    (working / ".git" / "info" / "attributes").write_text(rule, encoding="utf-8")
                git(working, "add", ".")
                git(working, "commit", "-qm", "filtered")
                commit = git(working, "rev-parse", "HEAD")
                self.assertEqual("pointer", git(working, "cat-file", "-p", "HEAD:data dir/é data.bin"))
                marker.unlink(missing_ok=True)
                os.utime(working / "data dir" / "é data.bin", (1, 1))

                # The working directory holds only an explicitly unfiltered path.
                result = _preflight_check(working / "sub", commit)
                self.assertFalse(result["ready"])
                self.assertIn("filter attribute", result["detail"])
                self.assertIn("data dir/é data.bin", result["detail"])
                job_dir = root / "bundle"
                with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "filter attribute"):
                    self._bundle(working / "sub", commit, job_dir)
                self.assertFalse(job_dir.exists())
                self.assertFalse(marker.exists())

        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, _ = initialize_repo(root)
            (working / ".gitattributes").write_text("*.txt -filter\n", encoding="utf-8")
            git(working, "add", ".")
            git(working, "commit", "-qm", "unset filter")
            self.assertTrue(_preflight_check(working, git(working, "rev-parse", "HEAD"))["ready"])

            empty = root / "empty"
            empty.mkdir()
            git(empty, "init", "-q")
            git(empty, "-c", "user.email=fixture@example.test", "-c", "user.name=Fixture",
                "commit", "-q", "--allow-empty", "-m", "empty")
            self.assertTrue(_preflight_check(empty, git(empty, "rev-parse", "HEAD"))["ready"])

    def test_index_flags_that_hide_edits_are_refused(self) -> None:
        cases = {
            "assume-unchanged": ["update-index", "--assume-unchanged"],
            "skip-worktree": ["update-index", "--skip-worktree"],
            "ignoreStat": None,
        }
        for label, command in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tempdir:
                root = Path(tempdir)
                working, commit = initialize_repo(root)
                (working / "sub").mkdir()
                (working / "sub" / "keep.txt").write_text("kept\n", encoding="utf-8")
                git(working, "add", ".")
                git(working, "commit", "-qm", "subdirectory")
                commit = git(working, "rev-parse", "HEAD")
                if command is None:
                    git(working, "config", "core.ignoreStat", "true")
                    (working / "hidden.txt").write_text("committed\n", encoding="utf-8")
                    git(working, "add", "hidden.txt")
                    git(working, "commit", "-qm", "indexed under ignoreStat")
                    commit = git(working, "rev-parse", "HEAD")
                    flagged = "hidden.txt"
                else:
                    flagged = "source.txt"
                    git(working, *command, flagged)
                (working / flagged).write_text("edited\n", encoding="utf-8")
                self.assertEqual("", git(working, "status", "--porcelain"))

                result = _preflight_check(working / "sub", commit)
                self.assertFalse(result["ready"])
                self.assertIn(flagged, result["detail"])
                self.assertRegex(result["detail"], "assume-unchanged|skip-worktree")
                with self.assertRaises(source_snapshot.SourceSnapshotError):
                    self._bundle(working, commit, root / "bundle")

    def test_preflight_does_not_rewrite_the_index_or_run_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            marker = root / "hook-ran"
            hook = working / ".git" / "hooks" / "post-index-change"
            hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
            hook.chmod(0o755)
            os.utime(working / "source.txt", (1, 1))
            index_before = (working / ".git" / "index").read_bytes()

            self.assertTrue(_preflight_check(working, commit)["ready"])
            self.assertFalse(marker.exists())
            self.assertEqual(index_before, (working / ".git" / "index").read_bytes())

    def test_partial_and_promisor_clones_are_refused_before_reading_objects(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            server = root / "server.git"
            git(root, "clone", "-q", "--bare", str(working), str(server))
            git(server, "config", "uploadpack.allowFilter", "true")
            clone = root / "partial"
            git(root, "clone", "-q", "--no-checkout", "--filter=blob:none", server.as_uri(), str(clone))

            def missing() -> list[str]:
                listing = git(clone, "rev-list", "--objects", "--missing=print", commit)
                return [line for line in listing.splitlines() if line.startswith("?")]

            missing_before = missing()
            self.assertTrue(missing_before)
            result = _preflight_check(clone, commit)
            self.assertFalse(result["ready"])
            self.assertRegex(result["detail"], "partial clone|promisor")
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "partial clone|promisor"):
                self._bundle(clone, commit, root / "bundle")
            self.assertEqual(missing_before, missing())

            git(working, "config", "remote.origin.promisor", "false")
            self.assertTrue(_preflight_check(working, commit)["ready"])
            git(working, "config", "extensions.partialClone", "origin")
            result = _preflight_check(working, commit)
            self.assertFalse(result["ready"])
            self.assertIn("partialClone", result["detail"])

    def test_receipt_tree_is_resolved_from_the_verified_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            working, commit = initialize_repo(root)
            run_git = source_snapshot._run_git
            moved = []

            def move_head_after_verification(working_path: Path, *arguments: str, **options: object):
                output = run_git(working_path, *arguments, **options)
                if arguments == ("rev-parse", "--verify", "HEAD") and not moved:
                    (working / "source.txt").write_text("moved\n", encoding="utf-8")
                    git(working, "commit", "-qam", "concurrent move")
                    moved.append(True)
                return output

            with mock.patch.object(source_snapshot, "_run_git", side_effect=move_head_after_verification):
                result = _preflight_check(working, commit)
            self.assertTrue(moved)
            self.assertEqual(commit, result["detail"]["commit"])
            self.assertEqual(git(working, "rev-parse", f"{commit}^{{tree}}"), result["detail"]["tree"])

    def test_honest_conflicts_and_undecodable_git_output_are_labelled(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            archive = io.BytesIO()
            with tarfile.open(fileobj=archive, mode="w") as bundle:
                for name in ("f", "f/g"):
                    item = tarfile.TarInfo(name)
                    item.size = 1
                    bundle.addfile(item, io.BytesIO(b"x"))
            archive.seek(0)
            destination = root / "extract"
            destination.mkdir()
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "conflicts.*f/g"):
                source_snapshot._safe_extract(archive, destination)

            working, commit = initialize_repo(root)
            identity = source_snapshot._git_identity(working, commit)
            stage = root / "stage"
            stage.mkdir()
            (stage / "source.txt").write_text("existing\n", encoding="utf-8")
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "materialized path: source.txt"):
                source_snapshot._materialize_git_tree(identity, stage)

            git(working, "pack-refs", "--all")
            packed = working / ".git" / "packed-refs"
            packed.write_bytes(packed.read_bytes() + b"\xff\xfe broken\n")
            with self.assertRaisesRegex(source_snapshot.SourceSnapshotError, "git rev-parse"):
                self._bundle(working, commit, root / "bundle")
            self.assertTrue(_preflight_check(working, commit)["detail"].startswith("git rev-parse"))
