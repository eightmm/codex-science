import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from codex_science import runtime_identity


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "science_runtime_state.py"


def load_helper():
    spec = importlib.util.spec_from_file_location("science_runtime_state_contract_test", HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load runtime state helper")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STATE = load_helper()


class RuntimeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.codex_home = self.root / "codex"
        self.plugin_data = self.root / "plugin-data"
        self.environment = {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "CODEX_SCIENCE_PLUGIN_DATA": str(self.plugin_data),
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def make_source(
        self,
        name: str,
        version: str,
        *,
        runtime_text: str = "A",
        docs: str = "A",
        readme: str = "A",
        bootstrap_version: str = "0.5.0+codex.20260803040000",
    ) -> Path:
        source = self.root / name
        for directory in (
            source / ".agents" / "plugins",
            source / ".codex-plugin",
            source / "catalog",
            source / "docs",
            source / "hooks",
            source / "release",
            source / "runtime-skills" / "codex-science",
            source / "scripts",
            source / "skills",
            source / "src" / "codex_science",
        ):
            directory.mkdir(parents=True, exist_ok=True)
        (source / ".codex-plugin" / "plugin.json").write_text(
            json.dumps({"version": bootstrap_version}) + "\n", encoding="utf-8"
        )
        (source / ".mcp.json").write_text("{}\n", encoding="utf-8")
        (source / ".agents" / "plugins" / "marketplace.json").write_text(
            "{}\n", encoding="utf-8"
        )
        (source / "hooks" / "hooks.json").write_text("{}\n", encoding="utf-8")
        (source / "skills" / "host-skill.md").write_text(
            "host skill\n", encoding="utf-8"
        )
        (source / "catalog" / "inventory.json").write_text("{}\n", encoding="utf-8")
        (source / "docs" / "guide.md").write_text(docs + "\n", encoding="utf-8")
        (source / "README.md").write_text(readme + "\n", encoding="utf-8")
        (source / "release" / "manifest.json").write_text(
            json.dumps(
                {
                    "runtime_version": version,
                    "cache_neutral_files": ["README.md"],
                    "cache_neutral_prefixes": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (source / "runtime-skills" / "codex-science" / "SKILL.md").write_text(
            f"# runtime {runtime_text}\n", encoding="utf-8"
        )
        shutil.copy2(HELPER, source / "scripts" / "science_runtime_state.py")
        shutil.copy2(
            ROOT / "src" / "codex_science" / "runtime_identity.py",
            source / "src" / "codex_science" / "runtime_identity.py",
        )
        for script in (
            "python_runtime.sh",
            "science_update_entry.py",
            "science_update_hook.py",
        ):
            (source / "scripts" / script).write_text(
                f"# {script} bootstrap\n", encoding="utf-8"
            )
        for script in (
            "science_hook_dispatch.py",
            "science_mcp_proxy.py",
            "science_session_hook.py",
            "science_stop_hook.py",
        ):
            (source / "scripts" / script).write_text(
                f"# {script} {runtime_text}\n", encoding="utf-8"
            )
        (source / "scripts" / "science_mcp.py").write_text(
            f"# MCP {runtime_text}\n", encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            ["git", "-C", str(source), "config", "user.email", "state@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "config", "user.name", "State Test"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(source), "remote", "add", "origin", "https://github.com/eightmm/codex-science.git"],
            check=True,
        )
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(source), "commit", "-q", "-m", name], check=True
        )
        return source

    def clone_revision(
        self,
        source: Path,
        name: str,
        *,
        runtime_text: str | None = None,
        docs: str | None = None,
        readme: str | None = None,
    ) -> Path:
        target = self.root / name
        subprocess.run(["git", "clone", "-q", str(source), str(target)], check=True)
        subprocess.run(
            ["git", "-C", str(target), "remote", "set-url", "origin", "https://github.com/eightmm/codex-science.git"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.email", "state@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.name", "State Test"],
            check=True,
        )
        if runtime_text is not None:
            (target / "scripts" / "science_mcp.py").write_text(
                f"# MCP {runtime_text}\n", encoding="utf-8"
            )
        if docs is not None:
            (target / "docs" / "guide.md").write_text(docs + "\n", encoding="utf-8")
        if readme is not None:
            (target / "README.md").write_text(readme + "\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(target), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(target), "commit", "-q", "-m", name], check=True
        )
        return target

    def install(self, source: Path):
        runtime, reason = STATE.install_runtime_append_only(
            source, self.environment, plugin_data=self.plugin_data
        )
        self.assertIsNotNone(runtime, reason)
        return runtime

    def test_existing_only_resolution_never_mints_a_runtime_receipt(self) -> None:
        source = self.make_source(
            "source-existing-only", "0.5.0+codex.20260803052999"
        )

        missing = STATE.ensure_runtime(
            source,
            self.environment,
            plugin_data=self.plugin_data,
            allow_create=False,
        )

        self.assertIsNone(missing)
        self.assertFalse(
            STATE.receipt_path(
                self.plugin_data, "0.5.0+codex.20260803052999"
            ).exists()
        )
        installed = self.install(source)
        self.assertEqual(
            installed,
            STATE.ensure_runtime(
                source,
                self.environment,
                plugin_data=self.plugin_data,
                allow_create=False,
            ),
        )

    def test_direct_cli_recovers_the_exact_installed_runtime_pin(self) -> None:
        runtime = self.install(
            self.make_source("source-cli", "0.5.0+codex.20260803052998")
        )
        runtime_identity.current_runtime_identity.cache_clear()
        try:
            with (
                mock.patch.object(runtime_identity, "ROOT", runtime.root),
                mock.patch.dict(
                    os.environ,
                    {
                        "CODEX_SCIENCE_RUNTIME_VERSION": "9.9.9+codex.forged",
                        "CODEX_SCIENCE_RUNTIME_COMMIT": "e" * 40,
                        "CODEX_SCIENCE_RUNTIME_RECEIPT": "f" * 64,
                    },
                    clear=False,
                ),
                mock.patch(
                    "codex_science.runtime_identity.subprocess.run",
                    side_effect=AssertionError("a private runtime must not call git"),
                ),
            ):
                identity = runtime_identity.current_runtime_identity()
        finally:
            runtime_identity.current_runtime_identity.cache_clear()

        self.assertEqual(runtime.pin.runtime_version, identity["runtime_version"])
        self.assertEqual(runtime.pin.runtime_commit, identity["commit"])
        self.assertEqual(runtime.pin.receipt_sha256, identity["receipt_sha256"])

    def test_append_only_install_never_replaces_an_older_task_cache(self) -> None:
        runtime_a = self.install(
            self.make_source("source-a", "0.5.0+codex.20260803053000")
        )
        old_script = runtime_a.root / "scripts" / "science_mcp.py"
        old_bytes = old_script.read_bytes()
        old_inode = runtime_a.root.stat().st_ino

        runtime_b = self.install(
            self.make_source(
                "source-b", "0.5.0+codex.20260803053001", runtime_text="B"
            )
        )

        self.assertNotEqual(runtime_a.root, runtime_b.root)
        self.assertEqual(old_inode, runtime_a.root.stat().st_ino)
        self.assertEqual(old_bytes, old_script.read_bytes())
        self.assertIsNotNone(
            STATE.verify_runtime_pin(
                runtime_a.pin, self.environment, plugin_data=self.plugin_data
            )
        )

    def test_codex_plugin_cache_pruning_cannot_remove_private_runtime_pin(self) -> None:
        runtime = self.install(
            self.make_source("source-private", "0.5.0+codex.20260803053002")
        )
        host_cache = self.codex_home / "plugins" / "cache" / "codex-science" / "codex-science"
        (host_cache / "old-host-version").mkdir(parents=True)
        shutil.rmtree(host_cache)

        verified = STATE.verify_runtime_pin(
            runtime.pin, self.environment, plugin_data=self.plugin_data
        )
        self.assertIsNotNone(verified)
        assert verified is not None
        self.assertTrue(verified.root.is_relative_to(self.plugin_data))

    def test_same_version_runtime_consumed_docs_change_is_rejected(self) -> None:
        source = self.make_source("source-a", "0.5.0+codex.20260803053100")
        runtime_a = self.install(source)
        receipt = STATE.receipt_path(self.plugin_data, runtime_a.pin.runtime_version)
        before_receipt = receipt.read_bytes()
        before_tree = STATE._tree_manifest(runtime_a.root)
        docs_revision = self.clone_revision(source, "source-docs", docs="B")

        runtime_again, reason = STATE.install_runtime_append_only(
            docs_revision, self.environment, plugin_data=self.plugin_data
        )

        self.assertIsNone(runtime_again)
        self.assertIn("different runtime content", reason)
        self.assertEqual(before_receipt, receipt.read_bytes())
        self.assertEqual(before_tree, STATE._tree_manifest(runtime_a.root))
        self.assertEqual("A", (runtime_a.root / "docs" / "guide.md").read_text().strip())

    def test_same_version_runtime_collision_fails_without_mutation(self) -> None:
        source = self.make_source("source-a", "0.5.0+codex.20260803053200")
        runtime_a = self.install(source)
        before = STATE._tree_manifest(runtime_a.root)
        collision = self.clone_revision(source, "source-runtime", runtime_text="different")

        runtime, reason = STATE.install_runtime_append_only(
            collision, self.environment, plugin_data=self.plugin_data
        )

        self.assertIsNone(runtime)
        self.assertIn("different runtime content", reason)
        self.assertEqual(before, STATE._tree_manifest(runtime_a.root))

    def test_exact_orphan_cache_is_repaired_after_interrupted_receipt_write(self) -> None:
        version = "0.5.0+codex.20260803053201"
        source = self.make_source("source-orphan", version)
        target = STATE.runtime_store_root(self.plugin_data) / version
        target.mkdir(parents=True)
        files = STATE.tracked_manifest(source)
        self.assertIsNotNone(files)
        assert files is not None
        self.assertTrue(STATE._copy_manifest(source, target, files))
        self.assertFalse(STATE.receipt_path(self.plugin_data, version).exists())

        runtime, reason = STATE.install_runtime_append_only(
            source, self.environment, plugin_data=self.plugin_data
        )

        self.assertIsNotNone(runtime, reason)
        assert runtime is not None
        self.assertEqual(target.resolve(), runtime.root)
        self.assertIsNotNone(
            STATE.verify_runtime_pin(
                runtime.pin, self.environment, plugin_data=self.plugin_data
            )
        )

    def test_unreceipted_neutral_stale_orphan_is_replaced_on_retry(self) -> None:
        version = "0.5.0+codex.20260803053203"
        source = self.make_source("source-orphan-a", version, docs="A")
        target = STATE.runtime_store_root(self.plugin_data) / version
        target.mkdir(parents=True)
        files = STATE.tracked_manifest(source)
        self.assertIsNotNone(files)
        assert files is not None
        self.assertTrue(STATE._copy_manifest(source, target, files))
        updated = self.clone_revision(source, "source-orphan-b", readme="B")

        runtime, reason = STATE.install_runtime_append_only(
            updated, self.environment, plugin_data=self.plugin_data
        )

        self.assertIsNotNone(runtime, reason)
        self.assertEqual("B", (target / "README.md").read_text().strip())

    def test_explicit_install_repairs_corrupt_tree_from_exact_receipt_bytes(self) -> None:
        source = self.make_source(
            "source-repair", "0.5.0+codex.20260803053204"
        )
        runtime = self.install(source)
        marker = STATE.activation_path(self.plugin_data, "active-during-repair")
        activation = STATE.claim_runtime_activation(marker, runtime.pin)
        receipt = STATE.receipt_path(
            self.plugin_data, runtime.pin.runtime_version
        ).read_bytes()
        damaged = runtime.root / "scripts" / "science_mcp.py"
        damaged.unlink()

        refused, reason = STATE.install_runtime_append_only(
            source,
            self.environment,
            plugin_data=self.plugin_data,
        )
        self.assertIsNone(refused)
        self.assertIn("no valid receipt", reason)

        repaired, reason = STATE.install_runtime_append_only(
            source,
            self.environment,
            plugin_data=self.plugin_data,
            repair_existing=True,
        )

        self.assertIsNotNone(repaired, reason)
        assert repaired is not None
        self.assertEqual(runtime.pin, repaired.pin)
        self.assertEqual(receipt, STATE.receipt_path(
            self.plugin_data, runtime.pin.runtime_version
        ).read_bytes())
        self.assertTrue(damaged.is_file())
        self.assertEqual(
            activation,
            STATE.read_activation_record(marker),
        )
        self.assertIsNotNone(
            STATE.verify_runtime_pin(
                runtime.pin, self.environment, plugin_data=self.plugin_data
            )
        )

    def test_runtime_verification_rejects_symlinked_critical_root(self) -> None:
        runtime = self.install(
            self.make_source("source-symlink", "0.5.0+codex.20260803053202")
        )
        scripts = runtime.root / "scripts"
        outside = self.root / "outside-scripts"
        scripts.rename(outside)
        scripts.symlink_to(outside, target_is_directory=True)

        self.assertIsNone(
            STATE.verify_runtime_pin(
                runtime.pin, self.environment, plugin_data=self.plugin_data
            )
        )

    def test_activation_claim_is_single_winner_and_remove_is_generation_cas(self) -> None:
        runtime_a = self.install(
            self.make_source("source-a", "0.5.0+codex.20260803053300")
        )
        runtime_b = self.install(
            self.make_source("source-b", "0.5.0+codex.20260803053301", runtime_text="B")
        )
        path = STATE.activation_path(self.plugin_data, "private-session")
        first = STATE.claim_runtime_activation(path, runtime_a.pin)
        second = STATE.claim_runtime_activation(path, runtime_b.pin)

        self.assertEqual(first, second)
        self.assertEqual(runtime_a.pin, second.runtime_pin)
        self.assertFalse(STATE.remove_activation_record(path, "f" * 64))
        self.assertTrue(path.is_file())
        self.assertTrue(STATE.remove_activation_record(path, first.generation))
        self.assertFalse(path.exists())

    def test_expired_valid_marker_rotates_but_corrupt_marker_is_never_overwritten(self) -> None:
        runtime = self.install(
            self.make_source("source-a", "0.5.0+codex.20260803053400")
        )
        path = STATE.activation_path(self.plugin_data, "session")
        first = STATE.claim_runtime_activation(path, runtime.pin)
        expired = time.time() - STATE.PIN_TTL_SECONDS - 1
        os.utime(path, (expired, expired))
        second = STATE.claim_runtime_activation(path, runtime.pin)
        self.assertNotEqual(first.generation, second.generation)

        path.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid"):
            STATE.claim_runtime_activation(path, runtime.pin)
        self.assertEqual("not-json", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
