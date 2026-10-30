import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.catalog import CatalogPolicy, audit_catalog


class CLITests(unittest.TestCase):
    def test_audit_cli_writes_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root / "skills" / "sympy"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                "---\nname: sympy\ndescription: Symbolic mathematics\nlicense: BSD-3-Clause\n---\n",
                encoding="utf-8",
            )
            output = root / "inventory.json"

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/audit_skills.py",
                    "--catalog",
                    str(root / "skills"),
                    "--commit",
                    "abc123",
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            inventory = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(1, inventory["summary"]["total"])
            self.assertIn("total=1 active=1 inactive=0", result.stdout)

            expected = output.read_bytes()
            alias = root / "alias"
            alias.symlink_to(root / "skills", target_is_directory=True)
            for named_root in (root / "skills", alias):
                with self.subTest(root=named_root):
                    self.assertEqual(inventory, audit_catalog(named_root, "abc123", CatalogPolicy.default()))
                    result = subprocess.run(
                        [sys.executable, "scripts/audit_skills.py", "--catalog", str(named_root),
                         "--commit", "abc123", "--output", str(output)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertEqual(expected, output.read_bytes())

            link = skill / "linked.md"
            link.symlink_to(root / "missing")
            for named_root in (root / "skills", alias):
                with self.subTest(root=named_root):
                    with self.assertRaisesRegex(ValueError, "Symlink in catalog tree:"):
                        audit_catalog(named_root, "abc123", CatalogPolicy.default())
                    result = subprocess.run(
                        [sys.executable, "scripts/audit_skills.py", "--catalog", str(named_root),
                         "--commit", "abc123", "--output", str(output)],
                        capture_output=True, text=True, check=False,
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("Symlink in catalog tree:", result.stderr)
                    self.assertIn(str(link.parent.resolve() / link.name), result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertEqual(expected, output.read_bytes())

    def test_mcp_stdio_initializes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp) / "inventory.json"
            inventory.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": {"commit": "abc"},
                        "summary": {"total": 0, "active": 0, "inactive": 0},
                        "skills": [],
                    }
                ),
                encoding="utf-8",
            )
            request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})

            result = subprocess.run(
                [sys.executable, "scripts/science_mcp.py", "--inventory", str(inventory)],
                input=request + "\n",
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            response = json.loads(result.stdout)
            self.assertEqual("codex-science", response["result"]["serverInfo"]["name"])


if __name__ == "__main__":
    unittest.main()
