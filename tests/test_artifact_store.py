import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from codex_science.artifact_store import (
    ContentAddressedStore,
    describe_directory,
    describe_external_reference,
    describe_file,
    validate_descriptor,
)
from codex_science.artifacts import add_artifact, new_manifest, validate_bundle, verify_bundle_artifacts


class ArtifactStoreTests(unittest.TestCase):
    def test_chunked_hashes_use_one_stream_during_atomic_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "data.bin"
            path.write_bytes(b"abc")
            replacement = path.with_suffix(".next")
            replacement.write_bytes(b"xyz")
            original_open = Path.open
            reads = []

            @contextmanager
            def replacing_open(target, *args, **kwargs):
                with original_open(target, *args, **kwargs) as handle:
                    yield handle
                if target == path:
                    reads.append(target)
                    if replacement.exists():
                        replacement.replace(path)

            with mock.patch.object(Path, "open", replacing_open):
                descriptor = describe_file(path, chunk_size=3)
            self.assertEqual(hashlib.sha256(b"abc").hexdigest(), descriptor.root_sha256)
            self.assertEqual(descriptor.root_sha256, descriptor.entries[0]["chunks"][0]["sha256"])
            self.assertEqual(1, len(reads))
            validate_descriptor(descriptor.to_dict())
            for content in (b"", b"a", b"abc", b"abcd"):
                path.write_bytes(content)
                descriptor = describe_file(path, chunk_size=3)
                self.assertEqual(hashlib.sha256(content).hexdigest(), descriptor.root_sha256)
                self.assertEqual(len(content), descriptor.total_bytes)
                validate_descriptor(descriptor.to_dict(), path)
            for invalid in (0, -1):
                with self.subTest(chunk_size=invalid), self.assertRaisesRegex(ValueError, "positive"):
                    describe_file(path, chunk_size=invalid)

    def test_store_verification_normalizes_digest_and_handles_missing_or_corrupt_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / "empty.bin"
            source.write_bytes(b"")
            store = ContentAddressedStore(root / "cache")
            digest, path = store.add_file(source)
            self.assertEqual(path, store.object_path(digest.upper()))
            self.assertTrue(store.verify(digest.upper()))
            self.assertFalse(store.verify("0" * 64))
            for malformed in ("", "bad"):
                with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                    store.verify(malformed)
            path.chmod(0o600)
            path.write_bytes(b"corrupt")
            self.assertFalse(store.verify(digest.upper()))

    def test_cli_verifies_external_reference_against_supplied_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            path = root / "data.bin"
            path.write_bytes(b"abc")
            descriptor_path = root / "external.json"
            script = Path(__file__).resolve().parents[1] / "scripts" / "describe_artifact.py"
            for digest, size, exists, expected in (
                ("0" * 64, 999, True, False),
                (hashlib.sha256(b"abc").hexdigest(), 3, True, True),
                (hashlib.sha256(b"abc").hexdigest(), 3, False, False),
            ):
                with self.subTest(size=size, exists=exists):
                    payload = describe_external_reference(uri="s3://bucket/data", version="v1", sha256=digest, size_bytes=size)
                    descriptor_path.write_text(json.dumps(payload.to_dict()), encoding="utf-8")
                    result = subprocess.run([sys.executable, str(script), str(path if exists else root / "missing"), "--verify", str(descriptor_path)], capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                    self.assertEqual(expected, result.returncode == 0, result.stderr)

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

    def test_chunked_entries_require_complete_chunk_lists_in_bundles(self) -> None:
        for content in (b"", b"a", b"ab", b"abc"):
            self.file.write_bytes(content)
            payload = self.chunked()
            validate_descriptor(payload)
            validate_descriptor(payload, self.file)
            for missing in (True, False):
                bad = copy.deepcopy(payload)
                if missing:
                    del bad["entries"][0]["chunks"]
                else:
                    bad["entries"][0]["chunks"] = None
                with self.subTest(content=content, missing=missing):
                    self.assertRejects(bad, "chunks must be a list")
                    self.assertRejects(bad, "chunks must be a list", self.file)
                    descriptor_path = self.root / "descriptor.json"
                    descriptor_path.write_text(json.dumps(bad))
                    manifest = new_manifest("chunk-review", "Validate chunk coverage", [])
                    add_artifact(manifest, descriptor_path.name, kind="artifact-descriptor",
                                 sha256=hashlib.sha256(descriptor_path.read_bytes()).hexdigest())
                    with self.assertRaisesRegex(ValueError, "descriptor.json.*chunks must be a list"):
                        validate_bundle(manifest, self.root)
            if content:
                for chunks in ([], payload["entries"][0]["chunks"][:-1]):
                    bad = copy.deepcopy(payload)
                    bad["entries"][0]["chunks"] = chunks
                    self.assertRejects(bad, "chunk sizes do not sum to entry size")

    def test_external_local_verification_checks_digest_size_and_existence(self) -> None:
        for content in (b"", b"abc"):
            self.file.write_bytes(content)
            payload = describe_external_reference(uri="s3://bucket/data", version="v1", sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)).to_dict()
            validate_descriptor(payload)
            validate_descriptor(payload, self.file)
            with self.assertRaises(ValueError):
                validate_descriptor(payload, self.root / "missing")
            for field, value in (("sha256", "0" * 64), ("size_bytes", len(content) + 1)):
                bad = copy.deepcopy(payload)
                bad["external"][field] = value
                bad["root_sha256" if field == "sha256" else "total_bytes"] = value
                with self.subTest(content=content, field=field):
                    self.assertRejects(bad, "do not match descriptor", self.file)
            for field in ("total_bytes", "entry_count", "size_bytes"):
                expected = 0 if field == "entry_count" else len(content)
                for value in (expected + 0.9, float(expected), bool(expected), str(expected), "", None, -1):
                    if field == "size_bytes" and value is None:
                        continue
                    bad = copy.deepcopy(payload)
                    target = bad["external"] if field == "size_bytes" else bad
                    target[field] = value
                    for path in (None, self.file):
                        with self.subTest(content=content, field=field, value=value, local=path is not None):
                            self.assertRejects(bad, "integer", path)
            unknown = copy.deepcopy(payload)
            unknown["external"]["size_bytes"] = None
            validate_descriptor(unknown)

    def test_unbound_roots_must_match_entries(self) -> None:
        dataset = self.root / "dataset"
        dataset.mkdir()
        (dataset / "a.bin").write_bytes(b"abc")
        for descriptor in (describe_file(self.file), describe_file(self.file, chunk_size=2), describe_directory(dataset)):
            payload = descriptor.to_dict()
            validate_descriptor(payload)
            payload["root_sha256"] = "0" * 64
            with self.subTest(kind=descriptor.artifact_type):
                self.assertRejects(payload, "root.*match")
        (dataset / "a.bin").unlink()
        validate_descriptor(describe_directory(dataset).to_dict())
        payload = describe_directory(dataset).to_dict()
        payload["root_sha256"] = "0" * 64
        self.assertRejects(payload, "root.*match")

    def test_duplicate_entry_aliases_and_wrong_file_cardinality_are_rejected(self) -> None:
        dataset = self.root / "dataset"
        dataset.mkdir()
        (dataset / "a.bin").write_bytes(b"abc")
        for alias in ("a.bin", "./a.bin"):
            payload = describe_directory(dataset).to_dict()
            payload["entries"].append({**payload["entries"][0], "path": alias})
            payload.update(entry_count=2, total_bytes=6)
            with self.subTest(alias=alias):
                self.assertRejects(payload, "[Dd]uplicate.*entry")
        for count in (0, 2):
            payload = describe_file(self.file).to_dict()
            payload["entries"] *= count
            payload.update(entry_count=count, total_bytes=6 * count)
            with self.subTest(count=count), self.assertRaises(ValueError):
                validate_descriptor(payload)

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
        for content in (b"", b"a", b"abcdef"):
            self.file.write_bytes(content)
            for descriptor in (describe_file(self.file), describe_file(self.file, chunk_size=2)):
                valid = descriptor.to_dict()
                validate_descriptor(valid, self.file)
                fields = [(valid, "total_bytes"), (valid, "entry_count"), (valid["entries"][0], "size")]
                if descriptor.artifact_type == "chunked-file":
                    fields.append((valid["entries"][0], "chunk_size"))
                    for chunk in valid["entries"][0]["chunks"]:
                        fields.extend((chunk, name) for name in ("size", "index", "offset"))
                for target, field in fields:
                    expected = target[field]
                    invalid = (expected + 0.9, float(expected), bool(expected), str(expected), "", None, -1)
                    if field == "chunk_size" or (field == "size" and "index" in target):
                        invalid += (0,)
                    for value in invalid:
                        target[field] = value
                        for path in (None, self.file):
                            with self.subTest(kind=descriptor.artifact_type, content=content, field=field, value=value, local=path is not None):
                                self.assertRejects(valid, "integer", path)
                    target[field] = expected

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
