import importlib.util
import fcntl
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class ScienceUpdateHookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[1]
        cls.script = cls.repository_root / "scripts" / "science_update_hook.py"
        spec = importlib.util.spec_from_file_location("science_update_hook", cls.script)
        if spec is None or spec.loader is None:
            raise RuntimeError("Unable to load update hook")
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.plugin_data = self.root / "plugin-data"
        self.home = self.root / "managed-checkout"
        self.home.mkdir()
        self.environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CODEX_SCIENCE_HOME": str(self.home),
            "CODEX_SCIENCE_AUTO_UPDATE": "notify",
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def status(self, *, available: bool = True):
        return self.module.UpdateStatus(
            local_commit="a" * 40,
            remote_commit=("b" if available else "a") * 40,
            checked_at=int(time.time()),
            checkout=str(self.home.resolve()),
            remote_url="https://github.com/eightmm/codex-science.git",
        )

    def installer_environment(self, target: Path) -> dict[str, str]:
        fake_bin = self.root / "installer-bin"
        fake_bin.mkdir(exist_ok=True)
        codex = fake_bin / "codex"
        codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        codex.chmod(0o755)
        return {
            **os.environ,
            "CODEX_SCIENCE_HOME": str(target),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        }

    def test_update_prompt_patterns_are_narrow(self) -> None:
        positives = (
            "Codex Science 업데이트",
            "Codex Science를 최신화해줘",
            "Update Codex Science",
        )
        negatives = (
            "Codex Science 업데이트 방식이 뭐야?",
            "업데이트라는 단어를 설명해줘",
            "Start Codex Science",
        )

        for prompt in positives:
            self.assertTrue(self.module.is_update_request(prompt), prompt)
        for prompt in negatives:
            self.assertFalse(self.module.is_update_request(prompt), prompt)

    def test_private_cache_round_trips_and_expires(self) -> None:
        cache = self.plugin_data / "update-check.json"
        status = self.status()
        self.module.write_cache(cache, status)

        self.assertEqual(0o600, stat.S_IMODE(cache.stat().st_mode))
        self.assertEqual(status, self.module.read_cache(cache, now=status.checked_at + 60))
        self.assertIsNone(
            self.module.read_cache(
                cache,
                now=status.checked_at + self.module.CHECK_TTL_SECONDS + 1,
            )
        )
        serialized = cache.read_text(encoding="utf-8").lower()
        self.assertNotIn("token", serialized)
        self.assertNotIn("password", serialized)

    def test_notify_mode_reports_update_without_installing(self) -> None:
        payload = {"hook_event_name": "SessionStart", "source": "startup"}
        with (
            mock.patch.object(self.module, "get_status", return_value=self.status()),
            mock.patch.object(self.module, "install_update") as install,
        ):
            context = self.module.handle(payload, self.environment)

        self.assertIn("update is available", context)
        self.assertIn("Codex Science 업데이트", context)
        install.assert_not_called()

    def test_plain_language_update_bypasses_off_mode(self) -> None:
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Codex Science 업데이트",
        }
        plugin_root = self.root / "loaded-plugin"
        plugin_root.mkdir()
        environment = {
            **self.environment,
            "CODEX_SCIENCE_AUTO_UPDATE": "off",
            "PLUGIN_ROOT": str(plugin_root),
        }
        status = self.status()
        with (
            mock.patch.object(self.module, "get_advertised_status", return_value=status),
            mock.patch.object(self.module, "get_status") as refresh,
            mock.patch.object(self.module, "install_update", return_value=(True, "updated")) as install,
        ):
            context = self.module.handle(payload, environment)

        install.assert_called_once_with(self.home, "main", status.remote_commit, plugin_root)
        refresh.assert_not_called()
        self.assertIn("next new Codex task", context)

    def test_first_explicit_request_advertises_before_installing(self) -> None:
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Codex Science 업데이트"}
        environment = {**self.environment, "PLUGIN_ROOT": str(self.root / "loaded-plugin")}
        discovered = self.status()._replace(remote_commit="c" * 40)
        with (
            mock.patch.object(self.module, "get_advertised_status", return_value=None),
            mock.patch.object(self.module, "get_status", return_value=discovered),
            mock.patch.object(self.module, "install_update") as install,
        ):
            context = self.module.handle(payload, environment)

        self.assertIn(discovered.remote_commit[:8], context)
        self.assertIn("again", context)
        install.assert_not_called()

    def test_only_official_repository_is_eligible_for_automatic_update(self) -> None:
        self.assertTrue(
            self.module.is_official_remote("https://github.com/eightmm/codex-science.git")
        )
        self.assertTrue(self.module.is_official_remote("git@github.com:eightmm/codex-science.git"))
        self.assertFalse(self.module.is_official_remote("https://example.com/codex-science.git"))
        self.assertFalse(
            self.module.is_official_remote("https://github.com/attacker/codex-science.git")
        )

    def test_install_refuses_dirty_managed_checkout(self) -> None:
        (self.home / ".git").mkdir()
        with mock.patch.object(
            self.module,
            "_git_output",
            side_effect=[
                "https://github.com/eightmm/codex-science.git",
                " M research-output.dat",
            ],
        ):
            success, reason = self.module.install_update(
                self.home, "main", "b" * 40, self.root / "loaded-plugin"
        )

        self.assertFalse(success)
        self.assertIn("dirty", reason)

    def test_install_refuses_local_commit_divergence(self) -> None:
        (self.home / ".git").mkdir()
        with mock.patch.object(
            self.module,
            "_git_output",
            side_effect=[
                "https://github.com/eightmm/codex-science.git",
                "",
                "a" * 40,
                "b" * 40,
            ],
        ):
            success, reason = self.module.install_update(
                self.home, "main", "b" * 40, self.root / "loaded-plugin"
            )

        self.assertFalse(success)
        self.assertIn("diverged", reason)

    def test_concurrent_update_is_rejected(self) -> None:
        lock_path = self.home.parent / ".codex-science-update.lock"
        lock_path.touch()
        with lock_path.open("r+") as lock_handle:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            success, reason = self.module.install_update(
                self.home, "main", "b" * 40, self.root / "loaded-plugin"
            )

        self.assertFalse(success)
        self.assertIn("already running", reason)

    def test_malformed_cache_and_unknown_mode_fail_safe(self) -> None:
        cache = self.plugin_data / "update-check.json"
        cache.parent.mkdir(parents=True)
        cache.write_text('{"local_commit":"not-a-commit"}', encoding="utf-8")
        self.assertIsNone(self.module.read_cache(cache))

        payload = {"hook_event_name": "SessionStart", "source": "startup"}
        environment = {**self.environment, "CODEX_SCIENCE_AUTO_UPDATE": "apply"}
        with mock.patch.object(self.module, "get_status") as status:
            self.assertIsNone(self.module.handle(payload, environment))
        status.assert_not_called()

    def test_failed_network_check_is_throttled_for_24_hours(self) -> None:
        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(
                self.module,
                "_run",
                return_value=subprocess.CompletedProcess([], 1, "", "network failed"),
            ) as network,
        ):
            self.assertIsNone(self.module.get_status(self.home, self.plugin_data, "main"))
            self.assertIsNone(self.module.get_status(self.home, self.plugin_data, "main"))

        self.assertEqual(1, network.call_count)
        self.assertTrue((self.plugin_data / "update-attempt.json").is_file())

    def test_cached_status_is_bound_to_checkout_and_current_head(self) -> None:
        stale = self.status()
        stale = stale._replace(checkout="/different/checkout")
        self.module.write_cache(self.plugin_data / "update-check.json", stale)
        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(
                self.module,
                "_run",
                return_value=subprocess.CompletedProcess(
                    [], 0, f"{'b' * 40}\trefs/heads/main\n", ""
                ),
            ) as network,
        ):
            refreshed = self.module.get_status(self.home, self.plugin_data, "main")

        self.assertEqual(1, network.call_count)
        self.assertEqual(str(self.home.resolve()), refreshed.checkout)

    def test_branch_movement_after_approval_is_rejected(self) -> None:
        plugin_root = self.root / "loaded-plugin"
        plugin_root.mkdir()
        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_plugin_version", return_value="old-version"),
            mock.patch.object(
                self.module,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, "", ""),
            ),
            mock.patch.object(self.module, "_git_output", return_value="c" * 40),
        ):
            success, reason = self.module.install_update(
                self.home, "main", "b" * 40, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("branch moved", reason)

    def test_registration_failure_rolls_back_source_and_preserves_loaded_cache(self) -> None:
        (self.home / "old-source.txt").write_text("old", encoding="utf-8")
        plugin_root = self.root / "loaded-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        (plugin_root / "loaded.txt").write_text("keep", encoding="utf-8")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                (candidate / ".codex-plugin").mkdir(parents=True)
                (candidate / ".codex-plugin" / "plugin.json").write_text(
                    '{"version":"new-version"}', encoding="utf-8"
                )
                return subprocess.CompletedProcess(command, 0, "", "")
            if command[:3] == ["codex", "plugin", "add"]:
                return subprocess.CompletedProcess(command, 1, "", "registration failed")
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("registration", reason)
        self.assertEqual("old", (self.home / "old-source.txt").read_text())
        self.assertEqual("keep", (plugin_root / "loaded.txt").read_text())

    def test_second_rename_failure_restores_previous_checkout(self) -> None:
        (self.home / "old-source.txt").write_text("old", encoding="utf-8")
        plugin_root = self.root / "loaded-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        expected = "b" * 40
        original_rename = Path.rename

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                (candidate / ".codex-plugin").mkdir(parents=True)
                (candidate / ".codex-plugin" / "plugin.json").write_text(
                    '{"version":"new-version"}', encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        def rename(path, target):
            if path.name == "candidate" and Path(target) == self.home:
                raise OSError("simulated candidate rename failure")
            return original_rename(path, target)

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(Path, "rename", autospec=True, side_effect=rename),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("rename failure", reason)
        self.assertEqual("old", (self.home / "old-source.txt").read_text())

    def test_checkout_change_during_validation_is_rejected(self) -> None:
        plugin_root = self.root / "loaded-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                (candidate / ".codex-plugin").mkdir(parents=True)
                (candidate / ".codex-plugin" / "plugin.json").write_text(
                    '{"version":"new-version"}', encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                side_effect=[
                    ("a" * 40, "https://github.com/eightmm/codex-science.git"),
                    None,
                ],
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("changed during validation", reason)
        self.assertTrue(self.home.is_dir())

    def test_checkout_mutation_during_cache_backup_is_revalidated(self) -> None:
        plugin_root = self.root / "loaded-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        expected = "b" * 40
        original_copytree = shutil.copytree

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                (candidate / ".codex-plugin").mkdir(parents=True)
                (candidate / ".codex-plugin" / "plugin.json").write_text(
                    '{"version":"new-version"}', encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        def copytree(source, destination, *args, **kwargs):
            result = original_copytree(source, destination, *args, **kwargs)
            if Path(source) == plugin_root:
                (self.home / "late-user-change").write_text("dirty", encoding="utf-8")
            return result

        def eligible(*args):
            if (self.home / "late-user-change").exists():
                return None
            return "a" * 40, "https://github.com/eightmm/codex-science.git"

        with (
            mock.patch.object(self.module, "_eligible_checkout", side_effect=eligible),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(shutil, "copytree", side_effect=copytree),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("changed during validation", reason)
        self.assertTrue((self.home / "late-user-change").is_file())

    def test_successful_update_removes_transaction_directory(self) -> None:
        plugin_root = self.root / "loaded-plugin"
        (plugin_root / ".codex-plugin").mkdir(parents=True)
        (plugin_root / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                (candidate / ".codex-plugin").mkdir(parents=True)
                (candidate / ".codex-plugin" / "plugin.json").write_text(
                    '{"version":"new-version"}', encoding="utf-8"
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_installed_cache_matches", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertTrue(success, reason)
        self.assertEqual([], list(self.root.glob(".codex-science-update-*")))

    def test_installed_cache_verification_covers_all_tracked_files(self) -> None:
        source = self.root / "source"
        source.mkdir()
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        (source / ".codex-plugin").mkdir()
        (source / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"new-version"}', encoding="utf-8"
        )
        (source / "skills").mkdir()
        (source / "skills" / "SKILL.md").write_text("runtime skill", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", "."], check=True)
        codex_home = self.root / "codex-home"
        cache = codex_home / "plugins/cache/codex-science/codex-science/new-version"
        cache.parent.mkdir(parents=True)
        shutil.copytree(source, cache)

        with mock.patch.dict(os.environ, {"CODEX_HOME": str(codex_home)}):
            self.assertTrue(self.module._installed_cache_matches(source))
            (cache / "skills" / "SKILL.md").write_text("corrupt", encoding="utf-8")
            self.assertFalse(self.module._installed_cache_matches(source))

    def test_restore_tree_replaces_partially_modified_loaded_cache(self) -> None:
        backup = self.root / "backup"
        loaded = self.root / "loaded"
        backup.mkdir()
        loaded.mkdir()
        (backup / "file").write_text("expected", encoding="utf-8")
        (loaded / "file").write_text("modified", encoding="utf-8")
        (loaded / "extra").write_text("remove", encoding="utf-8")

        self.assertTrue(self.module._restore_tree(backup, loaded))
        self.assertEqual(self.module._directory_manifest(backup), self.module._directory_manifest(loaded))

    def test_installer_self_check_exercises_update_primitives(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.script), "--self-check"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("update hook self-check: ok", result.stdout)

        with mock.patch.object(self.module, "_restore_previous", return_value=False):
            self.assertEqual(1, self.module.self_check())

    def test_malformed_hook_input_does_not_block_task_start(self) -> None:
        result = subprocess.run(
            [sys.executable, str(self.script)],
            input="not-json",
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "CODEX_SCIENCE_AUTO_UPDATE": "off"},
        )

        self.assertEqual(0, result.returncode)
        self.assertEqual("", result.stdout)

    def test_hook_configuration_runs_update_check_on_start_and_prompt(self) -> None:
        config = json.loads(
            (self.repository_root / "hooks" / "hooks.json").read_text(encoding="utf-8")
        )
        serialized = json.dumps(config)

        self.assertIn("$PLUGIN_ROOT/scripts/science_update_hook.py", serialized)
        self.assertIn("SessionStart", config["hooks"])
        self.assertIn("UserPromptSubmit", config["hooks"])

    def test_installer_uses_staging_and_transactional_reruns(self) -> None:
        installer = (self.repository_root / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("--manual-update", installer)
        self.assertIn("--candidate-check", installer)
        self.assertNotIn("git -C \"$INSTALL_DIR\" pull", installer)
        self.assertNotIn("codex plugin add codex-science@codex-science >/dev/null 2>&1 || true", installer)

    def test_fresh_installer_rejects_existing_non_git_target(self) -> None:
        target = self.root / "existing-target"
        target.mkdir()
        (target / "untrusted").write_text("do not execute", encoding="utf-8")
        result = subprocess.run(
            ["bash", str(self.repository_root / "scripts" / "install.sh")],
            capture_output=True,
            text=True,
            check=False,
            env=self.installer_environment(target),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("not a managed Git checkout", result.stderr)
        self.assertTrue((target / "untrusted").is_file())

    def test_fresh_installer_rejects_concurrent_activation(self) -> None:
        target = self.root / "new-target"
        lock_path = self.root / ".codex-science-update.lock"
        lock_path.touch()
        with lock_path.open("r+") as lock_handle:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run(
                ["bash", str(self.repository_root / "scripts" / "install.sh")],
                capture_output=True,
                text=True,
                check=False,
                env=self.installer_environment(target),
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("another Codex Science install or update is running", result.stderr)
        self.assertFalse(target.exists())

    def test_fresh_installer_rejects_symlink_lock_without_modifying_target(self) -> None:
        target = self.root / "new-target"
        victim = self.root / "victim"
        victim.write_text("protected-data", encoding="utf-8")
        lock_path = self.root / ".codex-science-update.lock"
        lock_path.symlink_to(victim)

        result = subprocess.run(
            ["bash", str(self.repository_root / "scripts" / "install.sh")],
            capture_output=True,
            text=True,
            check=False,
            env=self.installer_environment(target),
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("lock path is unsafe", result.stderr)
        self.assertEqual("protected-data", victim.read_text(encoding="utf-8"))
        self.assertTrue(lock_path.is_symlink())

    def test_successful_fresh_installer_releases_lock(self) -> None:
        fixture = self.root / "fixture"
        scripts = fixture / "scripts"
        catalog = fixture / "catalog"
        scripts.mkdir(parents=True)
        catalog.mkdir()
        (catalog / "inventory.json").write_text("{}", encoding="utf-8")
        (scripts / "bootstrap.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (scripts / "science_update_hook.py").write_text(
            "import sys\n"
            "def _installed_cache_matches(root): return True\n"
            "if __name__ == '__main__': raise SystemExit(0)\n",
            encoding="utf-8",
        )
        (scripts / "science_mcp.py").write_text(
            "print('science_search_skills')\n", encoding="utf-8"
        )
        (scripts / "science_session_hook.py").write_text(
            "print('Codex Science is active')\n", encoding="utf-8"
        )
        for path in scripts.iterdir():
            path.chmod(0o755)

        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        (fake_bin / "git").write_text(
            "#!/bin/sh\n"
            "for value in \"$@\"; do destination=\"$value\"; done\n"
            "cp -a \"$FAKE_CANDIDATE\" \"$destination\"\n",
            encoding="utf-8",
        )
        (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        for path in fake_bin.iterdir():
            path.chmod(0o755)

        target = self.root / "installed"
        result = subprocess.run(
            ["bash", str(self.repository_root / "scripts" / "install.sh")],
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "CODEX_SCIENCE_HOME": str(target),
                "FAKE_CANDIDATE": str(fixture),
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        lock_path = self.root / ".codex-science-update.lock"
        with lock_path.open("r+") as lock_handle:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertTrue((target / "scripts" / "science_update_hook.py").is_file())


if __name__ == "__main__":
    unittest.main()
