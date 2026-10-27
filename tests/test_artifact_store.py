import copy
import os
import tempfile
import unittest
from pathlib import Path

from codex_science.artifact_store import (
    ContentAddressedStore,
    describe_directory,
    describe_external_reference,
    describe_file,
    validate_descriptor,
)
from codex_science.artifacts import add_artifact, new_manifest, verify_bundle_artifacts


class ArtifactStoreTests(unittest.TestCase):
    def test_streaming_chunks_and_merkle_directory_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir) / "dataset"
            root.mkdir()
            (root / "a.bin").write_bytes(b"abcdef")
            (root / "nested").mkdir()
            (root / "nested" / "b.bin").write_bytes(b"ghijkl")
            first = describe_directory(root, media_type="application/x-directory")
            second = describe_directory(root, media_type="application/x-directory")
            self.assertEqual(first.root_sha256, second.root_sha256)
            self.assertEqual(2, first.entry_count)
            validate_descriptor(first.to_dict(), root)

            chunked = describe_file(root / "a.bin", chunk_size=2)
            self.assertEqual(3, len(chunked.entries[0]["chunks"]))
            validate_descriptor(chunked.to_dict(), root / "a.bin")

    def test_manifest_validates_directory_without_whole_file_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            run = Path(tempdir)
            dataset = run / "trajectory"
            dataset.mkdir()
            (dataset / "frame-0001.bin").write_bytes(b"frame-one")
            descriptor = describe_directory(dataset)
            manifest = new_manifest("run-1", "Validate a directory artifact", [])
            add_artifact(
                manifest,
                "trajectory",
                kind="trajectory",
                sha256=descriptor.root_sha256,
                artifact_type="directory-tree",
                size_bytes=descriptor.total_bytes,
                entry_count=descriptor.entry_count,
            )
            verified = verify_bundle_artifacts(manifest, run)
            self.assertEqual(dataset, verified["trajectory"])
            (dataset / "frame-0001.bin").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_bundle_artifacts(manifest, run)


    def test_external_reference_preserves_immutable_identity(self) -> None:
        descriptor = describe_external_reference(
            uri="s3://private-bucket/object",
            version="version-7",
            sha256="a" * 64,
            size_bytes=123,
            media_type="application/octet-stream",
            license="internal-restricted",
        )
        validated = validate_descriptor(descriptor.to_dict())
        self.assertEqual("external-reference", validated.artifact_type)
        self.assertEqual(123, validated.total_bytes)

    def test_symlink_escape_is_rejected_and_store_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / "source.bin"
            source.write_bytes(b"payload")
            store = ContentAddressedStore(root / "cache")
            digest, first = store.add_file(source)
            digest2, second = store.add_file(source)
            self.assertEqual((digest, first), (digest2, second))
            self.assertTrue(store.verify(digest))

            directory = root / "dir"
            directory.mkdir()
            try:
                os.symlink(source, directory / "escape")
            except (OSError, NotImplementedError):
                return
            with self.assertRaisesRegex(ValueError, "symbolic links"):
                describe_directory(directory)


class ValidateDescriptorRejectionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.file = self.root / "a.bin"
        self.file.write_bytes(b"abcdef")

    def chunked(self) -> dict:
        return copy.deepcopy(describe_file(self.file, chunk_size=2).to_dict())

    def external(self) -> dict:
        return describe_external_reference(
            uri="s3://bucket/object", version="v1", sha256="a" * 64, size_bytes=5
        ).to_dict()

    def assertRejects(self, payload: dict, message: str, path: Path | None = None) -> None:
        with self.assertRaisesRegex(ValueError, message):
            validate_descriptor(payload, path)

    def test_valid_baselines_are_accepted(self) -> None:
        validate_descriptor(self.chunked(), self.file)
        validate_descriptor(self.external())

    def test_schema_and_type_are_checked(self) -> None:
        payload = self.chunked()
        payload["schema_version"] = 2
        self.assertRejects(payload, "unsupported artifact descriptor schema")
        payload = self.chunked()
        payload["artifact_type"] = "tarball"
        self.assertRejects(payload, "unsupported artifact type: tarball")

    def test_malformed_root_digest_and_entries_container(self) -> None:
        for digest in ("short", "z" * 64, None):
            with self.subTest(digest=digest):
                payload = self.chunked()
                payload["root_sha256"] = digest
                self.assertRejects(payload, "root_sha256 must be a SHA-256 digest")
        payload = self.chunked()
        payload["entries"] = "not-a-list"
        self.assertRejects(payload, "entries must be a list")
        payload = self.chunked()
        payload["entries"].append("stray")
        self.assertRejects(payload, "every descriptor entry must be an object")

    def test_entry_fields_are_checked(self) -> None:
        cases = (
            ("path", "../escape", "safe relative path"),
            ("path", "/abs", "safe relative path"),
            ("path", "", "safe relative path"),
            ("sha256", "nothex", "entry sha256"),
            ("size", -1, "entry size must be non-negative"),
        )
        for key, value, message in cases:
            with self.subTest(key=key, value=value):
                payload = self.chunked()
                payload["entries"][0][key] = value
                self.assertRejects(payload, message)

    def test_chunk_records_are_checked(self) -> None:
        cases = {
            "chunks must be a list": lambda e: e.update(chunks="x"),
            "chunk record must be an object": lambda e: e["chunks"].__setitem__(0, 5),
            "chunk indexes must be contiguous": lambda e: e["chunks"][1].update(index=5),
            "chunk offsets must be contiguous": lambda e: e["chunks"][1].update(offset=3),
            "chunk size must be positive": lambda e: e["chunks"][0].update(size=0),
            "chunk sha256": lambda e: e["chunks"][0].update(sha256="bad"),
            "chunk sizes do not sum to entry size": lambda e: e["chunks"].pop(),
        }
        for message, fn in cases.items():
            with self.subTest(message=message):
                payload = self.chunked()
                fn(payload["entries"][0])
                self.assertRejects(payload, message)

    def test_local_counts_must_match_entries(self) -> None:
        payload = self.chunked()
        payload["entry_count"] = 2
        self.assertRejects(payload, "entry_count does not match entries")
        payload = self.chunked()
        payload["total_bytes"] = 7
        self.assertRejects(payload, "total_bytes does not match entries")

    def test_external_reference_integrity(self) -> None:
        cases = {
            "requires external metadata": lambda p: p.update(external=None),
            "external sha256": lambda p: p["external"].update(sha256="bad"),
            "does not match root_sha256": lambda p: p["external"].update(sha256="b" * 64),
            "requires uri and version": lambda p: p["external"].update(uri=" "),
            "cannot contain local entries": lambda p: p.update(entry_count=1),
            "size does not match total_bytes": lambda p: p.update(total_bytes=6),
        }
        for message, fn in cases.items():
            with self.subTest(message=message):
                payload = self.external()
                fn(payload)
                self.assertRejects(payload, message)
        payload = self.external()
        payload["external"]["version"] = ""
        self.assertRejects(payload, "requires uri and version")
        payload = self.external()
        payload["entries"] = [{"path": "x", "size": 0, "sha256": "a" * 64}]
        self.assertRejects(payload, "cannot contain local entries")

    def test_bytes_must_match_descriptor(self) -> None:
        chunked = self.chunked()
        single = describe_file(self.file).to_dict()
        self.file.write_bytes(b"abcdeX")
        self.assertRejects(chunked, "do not match descriptor", self.file)
        self.assertRejects(single, "do not match descriptor", self.file)

        dataset = self.root / "dataset"
        dataset.mkdir()
        (dataset / "f.bin").write_bytes(b"one")
        tree = describe_directory(dataset).to_dict()
        (dataset / "f.bin").write_bytes(b"two")
        self.assertRejects(tree, "do not match descriptor", dataset)

    def test_bytes_check_rejects_wrong_chunk_size(self) -> None:
        payload = describe_file(self.file, chunk_size=2).to_dict()
        validate_descriptor(payload, self.file)
        payload["entries"] = describe_file(self.file, chunk_size=3).to_dict()["entries"]
        payload["entries"][0]["chunk_size"] = 3
        payload["root_sha256"] = describe_file(self.file).root_sha256
        validate_descriptor(payload, self.file)
        payload["entries"][0]["chunks"][0]["sha256"] = "c" * 64
        self.assertRejects(payload, "do not match descriptor", self.file)


if __name__ == "__main__":
    unittest.main()
