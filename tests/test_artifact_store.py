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


if __name__ == "__main__":
    unittest.main()
