import json
import tempfile
import unittest
from pathlib import Path

from codex_science.cli_io import load_json_object, write_text_atomic


class CliIoTests(unittest.TestCase):
    def test_load_json_object_labels_oversized_integer_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "big.json"
            path.write_text('{"n": ' + "9" * 5000 + "}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON in .*big.json"):
                load_json_object(path)

    def test_load_json_object_labels_non_utf8_input_with_path(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "latin.json"
            path.write_bytes('{"name": "café"}'.encode("latin-1"))
            with self.assertRaisesRegex(ValueError, "not valid UTF-8: .*latin.json"):
                load_json_object(path)

    def test_load_json_object_accepts_valid_object(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "ok.json"
            path.write_text(json.dumps({"a": 1}), encoding="utf-8")
            self.assertEqual({"a": 1}, load_json_object(path))

    def test_write_text_atomic_rejects_unencodable_text_before_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "sub" / "out.txt"
            with self.assertRaisesRegex(ValueError, "out.txt"):
                write_text_atomic(target, "bad \ud800 text")
            self.assertFalse(target.parent.exists())
            existing = Path(tempdir) / "keep.txt"
            existing.write_text("old", encoding="utf-8")
            with self.assertRaises(ValueError):
                write_text_atomic(existing, "\udfff")
            self.assertEqual("old", existing.read_text(encoding="utf-8"))
            self.assertEqual(["keep.txt"], sorted(p.name for p in Path(tempdir).iterdir()))

    def test_write_text_atomic_writes_valid_text(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            target = Path(tempdir) / "out.txt"
            write_text_atomic(target, "héllo\n")
            self.assertEqual("héllo\n", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
