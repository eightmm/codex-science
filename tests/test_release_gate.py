import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_science.release import manifest_runtime_version, release_version_advances


ROOT = Path(__file__).resolve().parents[1]
BASE_PLUGIN = "1.0.0+codex.20260101000000"
BASE_RUNTIME = "1.0.0+codex.20260101000000"
NEXT_PLUGIN = "1.0.0+codex.20260102000000"
NEXT_RUNTIME = "1.0.0+codex.20260102000000"


class ReleaseGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        script = ROOT / "scripts" / "validate_release.py"
        spec = importlib.util.spec_from_file_location("validate_release_script", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load validate_release.py")
        cls.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.validator)

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "release@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Release Test"],
            check=True,
        )
        self.runtime_prefixes = ["runtime/", "bootstrap/", "hooks/"]
        self.bootstrap_files = ["bootstrap/entry.py", "bootstrap/secondary.py"]
        self.bootstrap_prefixes = ["hooks/"]
        self.write_release(BASE_PLUGIN, BASE_RUNTIME)
        for relative, content in (
            ("runtime/code.py", "A\n"),
            ("bootstrap/entry.py", "A\n"),
            ("bootstrap/secondary.py", "A\n"),
            ("hooks/start.json", "A\n"),
            ("docs/guide.md", "A\n"),
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def git(self, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def commit(self, message: str) -> None:
        self.git("add", ".")
        self.git("commit", "-q", "-m", message)

    def write_release(
        self,
        plugin_version: str,
        runtime_version: str,
        *,
        schema: int = 2,
        runtime_prefixes: list[str] | None = None,
        neutral_prefixes: list[str] | None = None,
        bootstrap_files: list[str] | None = None,
        bootstrap_prefixes: list[str] | None = None,
    ) -> None:
        plugin = self.root / ".codex-plugin" / "plugin.json"
        plugin.parent.mkdir(parents=True, exist_ok=True)
        plugin.write_text(
            json.dumps({"version": plugin_version}) + "\n", encoding="utf-8"
        )
        payload = {
            "schema_version": schema,
            "plugin_version": plugin_version,
            "runtime_affecting_prefixes": (
                self.runtime_prefixes if runtime_prefixes is None else runtime_prefixes
            ),
            "cache_neutral_files": [],
            "cache_neutral_prefixes": (
                ["docs/"] if neutral_prefixes is None else neutral_prefixes
            ),
            "bootstrap_affecting_files": (
                self.bootstrap_files if bootstrap_files is None else bootstrap_files
            ),
            "bootstrap_affecting_prefixes": (
                self.bootstrap_prefixes
                if bootstrap_prefixes is None
                else bootstrap_prefixes
            ),
        }
        if schema == 2:
            payload["runtime_version"] = runtime_version
        manifest = self.root / "release" / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def errors(self) -> list[str]:
        return self.validator._base_diff_errors(self.root, self.base)

    def test_runtime_change_requires_monotonic_runtime_version(self) -> None:
        (self.root / "runtime" / "code.py").write_text("B\n", encoding="utf-8")
        self.commit("runtime without bump")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_runtime_change_with_fixed_bootstrap_and_new_runtime_passes(self) -> None:
        (self.root / "runtime" / "code.py").write_text("B\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("runtime with independent bump")
        self.assertEqual([], self.errors())

    def test_runtime_version_only_manifest_change_does_not_require_plugin_bump(self) -> None:
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("runtime identity only")
        self.assertEqual([], self.errors())

    def test_docs_only_change_does_not_require_a_version_bump(self) -> None:
        (self.root / "docs" / "guide.md").write_text("B\n", encoding="utf-8")
        self.commit("docs")
        self.assertEqual([], self.errors())

    def test_bootstrap_change_requires_independent_plugin_version(self) -> None:
        (self.root / "bootstrap" / "entry.py").write_text("B\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("bootstrap without plugin bump")
        self.assertIn("monotonic plugin version", "\n".join(self.errors()))

    def test_bootstrap_change_with_both_versions_advanced_passes(self) -> None:
        (self.root / "bootstrap" / "entry.py").write_text("B\n", encoding="utf-8")
        self.write_release(NEXT_PLUGIN, NEXT_RUNTIME)
        self.commit("bootstrap with both bumps")
        self.assertEqual([], self.errors())

    def test_runtime_downgrade_is_rejected(self) -> None:
        (self.root / "runtime" / "code.py").write_text("B\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, "0.9.9+codex.20261231000000")
        self.commit("runtime downgrade")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_plugin_downgrade_is_rejected(self) -> None:
        (self.root / "bootstrap" / "entry.py").write_text("B\n", encoding="utf-8")
        self.write_release(
            "0.9.9+codex.20261231000000",
            NEXT_RUNTIME,
        )
        self.commit("plugin downgrade")
        self.assertIn("monotonic plugin version", "\n".join(self.errors()))

    def test_schema_one_base_runtime_falls_back_to_plugin_version(self) -> None:
        self.write_release(BASE_PLUGIN, BASE_RUNTIME, schema=1)
        self.commit("schema one base")
        self.base = self.git("rev-parse", "HEAD")
        (self.root / "runtime" / "code.py").write_text("B\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("schema two independent runtime")

        self.assertEqual(BASE_PLUGIN, manifest_runtime_version({
            "schema_version": 1,
            "plugin_version": BASE_PLUGIN,
        }))
        self.assertEqual([], self.errors())

    def test_unknown_new_path_requires_runtime_version(self) -> None:
        unknown = self.root / "next" / "entry.py"
        unknown.parent.mkdir()
        unknown.write_text("new runtime\n", encoding="utf-8")
        self.commit("unknown path")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_new_neutral_policy_requires_one_runtime_bump_before_use(self) -> None:
        note = self.root / "notes" / "status.md"
        note.parent.mkdir()
        note.write_text("status\n", encoding="utf-8")
        self.write_release(
            BASE_PLUGIN,
            BASE_RUNTIME,
            neutral_prefixes=["docs/", "notes/"],
        )
        self.commit("new neutral path without bump")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_runtime_to_docs_rename_still_counts_as_runtime_deletion(self) -> None:
        self.git("mv", "runtime/code.py", "docs/code.md")
        self.commit("rename")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_current_release_cannot_remove_base_runtime_policy_without_bump(self) -> None:
        (self.root / "runtime" / "code.py").write_text("B\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, BASE_RUNTIME, runtime_prefixes=[])
        self.commit("weaken runtime policy")
        self.assertIn("monotonic runtime version", "\n".join(self.errors()))

    def test_base_and_current_bootstrap_policy_are_both_enforced(self) -> None:
        (self.root / "bootstrap" / "entry.py").write_text("B\n", encoding="utf-8")
        self.write_release(
            BASE_PLUGIN,
            NEXT_RUNTIME,
            bootstrap_files=["bootstrap/secondary.py"],
        )
        self.commit("remove old bootstrap policy")
        joined = "\n".join(self.errors())
        self.assertIn("monotonic plugin version", joined)
        self.assertIn("bootstrap/entry.py", joined)

    def test_bootstrap_policy_order_only_change_is_not_semantic(self) -> None:
        self.write_release(
            BASE_PLUGIN,
            NEXT_RUNTIME,
            bootstrap_files=list(reversed(self.bootstrap_files)),
        )
        self.commit("reorder bootstrap policy")
        self.assertEqual([], self.errors())

    def test_redundant_bootstrap_policy_entry_is_not_semantic(self) -> None:
        self.write_release(
            BASE_PLUGIN,
            BASE_RUNTIME,
            bootstrap_files=[*self.bootstrap_files, "hooks/start.json"],
        )
        self.commit("schema with redundant bootstrap file")
        self.base = self.git("rev-parse", "HEAD")
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("remove redundant bootstrap file")
        self.assertEqual([], self.errors())

    def test_bootstrap_policy_semantic_change_requires_plugin_version(self) -> None:
        self.write_release(
            BASE_PLUGIN,
            NEXT_RUNTIME,
            bootstrap_files=[*self.bootstrap_files, "bootstrap/new.py"],
        )
        self.commit("broaden bootstrap policy")
        self.assertIn("monotonic plugin version", "\n".join(self.errors()))

    def test_diverged_base_ref_uses_one_merge_base_for_diff_and_policy(self) -> None:
        self.git("checkout", "-q", "-b", "upstream")
        (self.root / "runtime" / "code.py").write_text("upstream\n", encoding="utf-8")
        self.write_release(BASE_PLUGIN, NEXT_RUNTIME)
        self.commit("upstream runtime")
        self.git("checkout", "-q", "-b", "feature", self.base)
        (self.root / "docs" / "guide.md").write_text("feature docs\n", encoding="utf-8")
        self.commit("feature docs")

        self.assertEqual([], self.validator._base_diff_errors(self.root, "upstream"))

    def test_release_order_handles_timestamp_nine_to_ten_and_downgrade(self) -> None:
        self.assertTrue(
            release_version_advances(
                "1.0.0+codex.20260101000009",
                "1.0.0+codex.20260101000010",
            )
        )
        self.assertFalse(
            release_version_advances(
                "1.0.0+codex.20260101000010",
                "1.0.0+codex.20260101000009",
            )
        )
        self.assertTrue(
            release_version_advances(
                "1.9.9+codex.20261231235959",
                "1.10.0+codex.20260101000000",
            )
        )


if __name__ == "__main__":
    unittest.main()
