import importlib.util
import fcntl
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


class ScienceUpdateHookTests(unittest.TestCase):
    BOOTSTRAP_A = "0.5.0+codex.20260803040000"
    BOOTSTRAP_B = "0.5.0+codex.20260803040001"
    RUNTIME_A = "0.5.0+codex.20260803050000"
    RUNTIME_B = "0.5.0+codex.20260803050001"
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
        self.codex_home = self.root / "codex-home"
        self.environment_patch = mock.patch.dict(
            os.environ,
            {"CODEX_HOME": str(self.codex_home)},
        )
        self.environment_patch.start()
        self.plugin_data = self.root / "plugin-data"
        self.home = self.root / "managed-checkout"
        self.home.mkdir()
        self.environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "CODEX_SCIENCE_HOME": str(self.home),
            "CODEX_SCIENCE_AUTO_UPDATE": "notify",
        }

    def tearDown(self) -> None:
        self.environment_patch.stop()
        self.tempdir.cleanup()

    def status(self, *, available: bool = True):
        return self.module.UpdateStatus(
            local_commit="a" * 40,
            remote_commit=("b" if available else "a") * 40,
            checked_at=int(time.time()),
            checkout=str(self.home.resolve()),
            remote_url="https://github.com/eightmm/codex-science.git",
        )

    @classmethod
    def write_plugin_version(
        cls, root: Path, version: str, *, runtime_version: str | None = None
    ) -> None:
        aliases = {
            "same-version": cls.BOOTSTRAP_A,
            "old-version": cls.BOOTSTRAP_A,
            "loaded-v1": cls.BOOTSTRAP_A,
            "home-v2": cls.BOOTSTRAP_B,
            "new-version": cls.BOOTSTRAP_B,
        }
        version = aliases.get(version, version)
        runtime_version = runtime_version or cls.RUNTIME_A
        plugin = root / ".codex-plugin"
        plugin.mkdir(parents=True, exist_ok=True)
        (plugin / "plugin.json").write_text(
            json.dumps({"version": version}) + "\n", encoding="utf-8"
        )
        release = root / "release"
        release.mkdir(parents=True, exist_ok=True)
        (release / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "plugin_version": version,
                    "runtime_version": runtime_version,
                    "cache_neutral_files": ["README.md"],
                    "cache_neutral_prefixes": ["tests/"],
                    "bootstrap_affecting_files": [],
                    "bootstrap_affecting_prefixes": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def installer_environment(self, target: Path) -> dict[str, str]:
        fake_bin = self.root / "installer-bin"
        fake_bin.mkdir(exist_ok=True)
        codex = fake_bin / "codex"
        codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        codex.chmod(0o755)
        real_git = shutil.which("git")
        assert real_git is not None
        git = fake_bin / "git"
        git.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = ls-remote ] && [ -n \"${FAKE_OFFICIAL_MAIN_COMMIT:-}\" ]; then\n"
            "  printf '%s\\trefs/heads/main\\n' \"$FAKE_OFFICIAL_MAIN_COMMIT\"\n"
            "  exit 0\n"
            "fi\n"
            f"exec {real_git} \"$@\"\n",
            encoding="utf-8",
        )
        git.chmod(0o755)
        return {
            **os.environ,
            "CODEX_SCIENCE_HOME": str(target),
            "CODEX_SCIENCE_RUNTIME_FILE": str(self.root / "runtime-python"),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        }

    @staticmethod
    def make_trusted_checkout(target: Path) -> None:
        subprocess.run(["git", "init", "-q", str(target)], check=True)
        subprocess.run(
            ["git", "-C", str(target), "config", "user.email", "install@test.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(target), "config", "user.name", "Installer Test"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(target),
                "remote",
                "add",
                "origin",
                "https://github.com/eightmm/codex-science.git",
            ],
            check=True,
        )
        subprocess.run(["git", "-C", str(target), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(target), "commit", "-q", "-m", "fixture"],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(target),
                "update-ref",
                "refs/remotes/origin/main",
                "HEAD",
            ],
            check=True,
        )

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

    def test_activation_patterns_include_prefix_and_postfix_english_forms(self) -> None:
        for prompt in (
            "Start Codex Science",
            "Codex Science start",
            "Codex Science activate",
            "Codex Science 시작",
        ):
            self.assertTrue(self.module.is_activation_request(prompt), prompt)

    def test_update_state_is_fsynced_before_a_transaction_phase_is_trusted(
        self,
    ) -> None:
        path = self.plugin_data / "update-check.json"
        with mock.patch.object(
            self.module.os, "fsync", wraps=os.fsync
        ) as fsync:
            self.module.write_cache(path, self.status())

        self.assertGreaterEqual(fsync.call_count, 2)
        self.assertIsNotNone(self.module.read_cache(path))

    def test_same_cachebuster_requires_both_release_policies_to_admit_every_path(self) -> None:
        base = (frozenset({"README.md"}), ("docs/", "benchmarks/"))
        candidate = (frozenset({"README.md"}), ("docs/", "benchmarks/", "notes/"))

        cases = (
            ((), True),
            (("README.md", "docs/guide.md", "benchmarks/result.json"), True),
            (("notes/new.md",), False),
            (("unclassified/new.py",), False),
            (("scripts/science_update_hook.py", "docs/guide.md"), False),
            (("release/manifest.json",), False),
        )
        for paths, expected in cases:
            with self.subTest(paths=paths):
                self.assertEqual(
                    expected,
                    self.module._cache_neutral_change(paths, base, candidate),
                )

    def test_release_neutral_policy_rejects_malformed_paths(self) -> None:
        malformed = (
            {"cache_neutral_files": ["../README.md"], "cache_neutral_prefixes": []},
            {"cache_neutral_files": ["/README.md"], "cache_neutral_prefixes": []},
            {"cache_neutral_files": [], "cache_neutral_prefixes": ["docs"]},
            {"cache_neutral_files": [], "cache_neutral_prefixes": ["../docs/"]},
        )
        for payload in malformed:
            with self.subTest(payload=payload), mock.patch.object(
                self.module,
                "_run",
                return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
            ):
                self.assertIsNone(
                    self.module._release_neutral_policy(self.home, "a" * 40)
                )

    def test_managed_marketplace_replaces_legacy_development_source(self) -> None:
        managed = self.root / "managed"
        development = self.root / "development"
        managed.mkdir()
        development.mkdir()
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[-2:] == ["list", "--json"]:
                payload = {
                    "marketplaces": [
                        {
                            "name": "codex-science",
                            "root": str(development),
                            "marketplaceSource": {
                                "sourceType": "local",
                                "source": str(development),
                            },
                        }
                    ]
                }
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.module, "_run", side_effect=run):
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertTrue(success, reason)
        self.assertEqual(
            [
                ["codex", "plugin", "marketplace", "list", "--json"],
                ["codex", "plugin", "marketplace", "remove", "codex-science"],
                ["codex", "plugin", "marketplace", "add", str(managed.resolve())],
            ],
            commands,
        )

    def test_managed_marketplace_keeps_matching_source(self) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        payload = {
            "marketplaces": [
                {
                    "name": "codex-science",
                    "root": str(managed),
                    "marketplaceSource": {
                        "sourceType": "local",
                        "source": str(managed),
                    },
                }
            ]
        }

        with mock.patch.object(
            self.module,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
        ) as run:
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertTrue(success, reason)
        run.assert_called_once_with(
            ["codex", "plugin", "marketplace", "list", "--json"], timeout=30
        )

    def test_managed_marketplace_adds_missing_source(self) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[-2:] == ["list", "--json"]:
                return subprocess.CompletedProcess(
                    command, 0, json.dumps({"marketplaces": []}), ""
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.module, "_run", side_effect=run):
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertTrue(success, reason)
        self.assertEqual(
            ["codex", "plugin", "marketplace", "add", str(managed.resolve())],
            commands[-1],
        )

    def test_managed_marketplace_uses_config_when_cli_list_fails(self) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        self.codex_home.mkdir(parents=True)
        (self.codex_home / "config.toml").write_text(
            "[marketplaces.codex-science]\n"
            'source_type = "local"\n'
            f'source = "{managed}"\n',
            encoding="utf-8",
        )

        with mock.patch.object(
            self.module,
            "_run",
            return_value=subprocess.CompletedProcess([], 1, "", ""),
        ) as run:
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertTrue(success, reason)
        self.assertIn("already registered", reason)
        run.assert_called_once_with(
            ["codex", "plugin", "marketplace", "list", "--json"], timeout=30
        )

    def test_managed_marketplace_adds_when_cli_list_fails_and_config_is_missing(
        self,
    ) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[-2:] == ["list", "--json"]:
                return subprocess.CompletedProcess(command, 1, "", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.module, "_run", side_effect=run):
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertTrue(success, reason)
        self.assertEqual(
            [
                ["codex", "plugin", "marketplace", "list", "--json"],
                ["codex", "plugin", "marketplace", "add", str(managed.resolve())],
            ],
            commands,
        )

    def test_managed_marketplace_reports_cli_and_config_failures(self) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        self.codex_home.mkdir(parents=True)
        (self.codex_home / "config.toml").write_text(
            "[marketplaces.codex-science\n",
            encoding="utf-8",
        )

        with mock.patch.object(
            self.module,
            "_run",
            return_value=subprocess.CompletedProcess(
                [], 1, "list failed on stdout", ""
            ),
        ):
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertFalse(success)
        self.assertIn("list failed on stdout", reason)
        self.assertIn("config.toml", reason)

    def test_managed_marketplace_does_not_replace_nonlocal_source(self) -> None:
        managed = self.root / "managed"
        managed.mkdir()
        payload = {
            "marketplaces": [
                {
                    "name": "codex-science",
                    "root": "/tmp/codex-science",
                    "marketplaceSource": {
                        "sourceType": "git",
                        "source": "https://example.invalid/codex-science.git",
                    },
                }
            ]
        }
        with mock.patch.object(
            self.module,
            "_run",
            return_value=subprocess.CompletedProcess([], 0, json.dumps(payload), ""),
        ) as run:
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertFalse(success)
        self.assertIn("not a local source", reason)
        run.assert_called_once()

    def test_managed_marketplace_restores_previous_source_when_add_fails(self) -> None:
        managed = self.root / "managed"
        development = self.root / "development"
        managed.mkdir()
        development.mkdir()
        commands = []

        def run(command, **kwargs):
            commands.append(command)
            if command[-2:] == ["list", "--json"]:
                payload = {
                    "marketplaces": [
                        {
                            "name": "codex-science",
                            "root": str(development),
                            "marketplaceSource": {
                                "sourceType": "local",
                                "source": str(development),
                            },
                        }
                    ]
                }
                return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
            if command == [
                "codex",
                "plugin",
                "marketplace",
                "add",
                str(managed.resolve()),
            ]:
                return subprocess.CompletedProcess(command, 1, "", "add failed")
            return subprocess.CompletedProcess(command, 0, "", "")

        with mock.patch.object(self.module, "_run", side_effect=run):
            success, reason = self.module.ensure_managed_marketplace(managed)

        self.assertFalse(success)
        self.assertIn("add failed", reason)
        self.assertIn("previous source restored", reason)
        self.assertEqual(
            ["codex", "plugin", "marketplace", "add", str(development.resolve())],
            commands[-1],
        )

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

        self.assertIn("새 버전", context)
        self.assertIn("자동 적용을 끈 상태", context)
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
            mock.patch.object(self.module, "get_status", return_value=status) as refresh,
            mock.patch.object(self.module, "install_update", return_value=(True, "updated")) as install,
        ):
            context = self.module.handle(payload, environment)

        install.assert_called_once_with(
            self.home,
            "main",
            status.remote_commit,
            plugin_root,
            lock_timeout=self.module.DISPATCH_LOCK_WAIT_SECONDS,
            plugin_data=self.plugin_data,
        )
        refresh.assert_called_once_with(self.home, self.plugin_data, "main", force=True)
        self.assertIn("이 작업부터 새 runtime", context)

    def test_first_explicit_request_installs_verified_commit_immediately(self) -> None:
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": "Codex Science 업데이트"}
        environment = {**self.environment, "PLUGIN_ROOT": str(self.root / "loaded-plugin")}
        discovered = self.status()._replace(remote_commit="c" * 40)
        with (
            mock.patch.object(self.module, "get_status", return_value=discovered),
            mock.patch.object(
                self.module, "install_update", return_value=(True, "updated")
            ) as install,
        ):
            context = self.module.handle(payload, environment)

        self.assertIn(discovered.remote_commit[:8], context)
        self.assertIn("이 작업부터", context)
        install.assert_called_once()

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

    def test_waiting_updater_follows_the_winner_runtime(self) -> None:
        self.write_plugin_version(self.home, "same-version")
        loaded = self.root / "loaded-plugin"
        self.write_plugin_version(loaded, "same-version")
        expected = "b" * 40
        lock_path = self.home.parent / ".codex-science-update.lock"
        lock_path.touch()
        lock_handle = lock_path.open("r+")
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)

        def release_winner() -> None:
            time.sleep(0.15)
            fcntl.flock(lock_handle, fcntl.LOCK_UN)
            lock_handle.close()

        releaser = threading.Thread(target=release_winner)
        releaser.start()
        try:
            with (
                mock.patch.object(
                    self.module,
                    "_eligible_checkout",
                    return_value=(expected, self.module.OFFICIAL_HTTPS_REMOTE),
                ),
                mock.patch.object(
                    self.module,
                    "_bootstrap_manifest",
                    return_value={"host": "same"},
                ),
                mock.patch.object(
                    self.module,
                    "install_runtime_append_only",
                    return_value=(object(), "runtime present"),
                ),
            ):
                success, reason = self.module.install_update(
                    self.home,
                    "main",
                    expected,
                    loaded,
                    lock_timeout=1,
                )
        finally:
            releaser.join(timeout=2)

        self.assertTrue(success, reason)
        self.assertIn("another process", reason)

    def test_malformed_cache_and_unknown_mode_fail_safe(self) -> None:
        cache = self.plugin_data / "update-check.json"
        cache.parent.mkdir(parents=True)
        cache.write_text('{"local_commit":"not-a-commit"}', encoding="utf-8")
        self.assertIsNone(self.module.read_cache(cache))

        payload = {"hook_event_name": "SessionStart", "source": "startup"}
        environment = {**self.environment, "CODEX_SCIENCE_AUTO_UPDATE": "surprise"}
        with mock.patch.object(self.module, "get_status") as status:
            self.assertIsNone(self.module.handle(payload, environment))
        status.assert_not_called()

    def test_failed_network_check_uses_short_retry_backoff(self) -> None:
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
            self.assertIsNone(
                self.module.get_status(
                    self.home, self.plugin_data, "main", force=True
                )
            )

        self.assertEqual(2, network.call_count)
        self.assertTrue((self.plugin_data / "update-attempt.json").is_file())

    def test_default_activation_auto_applies_and_resolves_live_runtime(self) -> None:
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Start Codex Science",
        }
        plugin_root = self.root / "loaded-plugin"
        plugin_root.mkdir()
        environment = {
            "PLUGIN_DATA": str(self.plugin_data),
            "PLUGIN_ROOT": str(plugin_root),
            "CODEX_SCIENCE_HOME": str(self.home),
        }
        status = self.status()
        with (
            mock.patch.object(
                self.module, "get_status", return_value=status
            ) as status_check,
            mock.patch.object(
                self.module,
                "install_update",
                return_value=(True, "updated"),
            ) as install,
        ):
            resolution = self.module.resolve_runtime(payload, environment)

        self.assertEqual("updated", resolution.status)
        self.assertEqual(str(self.home.resolve()), resolution.runtime_root)
        self.assertEqual(status.remote_commit, resolution.runtime_commit)
        self.assertTrue(resolution.updated)
        status_check.assert_called_once_with(
            self.home, self.plugin_data, "main", force=True
        )
        install.assert_called_once_with(
            self.home,
            "main",
            status.remote_commit,
            plugin_root,
            lock_timeout=self.module.DISPATCH_LOCK_WAIT_SECONDS,
            plugin_data=self.plugin_data,
        )

    def test_offline_activation_continues_with_clean_last_good_runtime(self) -> None:
        payload = {
            "hook_event_name": "UserPromptSubmit",
            "prompt": "Codex Science 시작",
        }
        with (
            mock.patch.object(self.module, "get_status", return_value=None),
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
        ):
            resolution = self.module.resolve_runtime(payload, self.environment)

        self.assertEqual("offline-last-good", resolution.status)
        self.assertEqual("a" * 40, resolution.runtime_commit)
        self.assertIn("계속합니다", resolution.message)

    def test_interrupted_candidate_is_rolled_back_before_dispatch(self) -> None:
        (self.home / "release.txt").write_text("candidate", encoding="utf-8")
        transaction = self.home.parent / ".codex-science-update-crash"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("last-good", encoding="utf-8")
        self.module._journal(transaction, "candidate_active", self.home)

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(
                self.module,
                "ensure_managed_marketplace",
                return_value=(True, "registered"),
            ),
            mock.patch.object(
                self.module,
                "register_plugin_preserving_caches",
                return_value=(True, "registered"),
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
        ):
            success, reason = self.module.repair_interrupted_update(
                self.home,
                None,
            )

        self.assertTrue(success, reason)
        self.assertEqual("last-good", (self.home / "release.txt").read_text())
        self.assertFalse(transaction.exists())

    def test_interrupted_bootstrap_registration_repairs_previous_host(self) -> None:
        for phase in ("registration_started", "host_registered"):
            with self.subTest(phase=phase):
                case_root = self.root / phase
                home = case_root / "home"
                home.mkdir(parents=True)
                (home / "release.txt").write_text("candidate", encoding="utf-8")
                transaction = case_root / ".codex-science-update-crash"
                previous = transaction / "previous"
                previous.mkdir(parents=True)
                (previous / "release.txt").write_text(
                    "last-good", encoding="utf-8"
                )
                self.module._journal(transaction, phase, home)
                plugin_data = case_root / "plugin-data"

                def eligible(root, _branch):
                    if Path(root) == previous:
                        return "a" * 40, self.module.OFFICIAL_HTTPS_REMOTE
                    return None

                with (
                    mock.patch.dict(
                        os.environ,
                        {
                            "CODEX_SCIENCE_MIGRATION_ACK": (
                                self.module.MIGRATION_ACK_VALUE
                            )
                        },
                    ),
                    mock.patch.object(
                        self.module, "_eligible_checkout", side_effect=eligible
                    ),
                    mock.patch.object(
                        self.module,
                        "_host_registration_matches",
                        return_value=(False, "candidate host unavailable"),
                    ),
                    mock.patch.object(
                        self.module,
                        "_register_host_now",
                        return_value=(True, "previous host restored"),
                    ) as register,
                    mock.patch.object(
                        self.module,
                        "install_runtime_append_only",
                        return_value=(object(), "runtime present"),
                    ),
                ):
                    success, reason = self.module.repair_interrupted_update(
                        home,
                        None,
                        plugin_data=plugin_data,
                        allow_host_repair=True,
                    )

                self.assertTrue(success, reason)
                self.assertEqual(
                    "last-good", (home / "release.txt").read_text(encoding="utf-8")
                )
                register.assert_called_once_with(home)
                self.assertFalse(transaction.exists())

    def test_host_registered_recovery_rechecks_external_registration(self) -> None:
        case_root = self.root / "host-registered-recheck"
        home = case_root / "home"
        home.mkdir(parents=True)
        (home / "release.txt").write_text("candidate", encoding="utf-8")
        transaction = case_root / ".codex-science-update-crash"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("last-good", encoding="utf-8")
        self.module._journal(transaction, "host_registered", home)
        plugin_data = case_root / "plugin-data"

        with (
            mock.patch.dict(
                os.environ,
                {"CODEX_SCIENCE_MIGRATION_ACK": self.module.MIGRATION_ACK_VALUE},
            ),
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(
                self.module,
                "_host_registration_matches",
                return_value=(False, "external registration was not durable"),
            ) as registration_check,
            mock.patch.object(
                self.module,
                "_register_host_now",
                return_value=(True, "previous host restored"),
            ) as register,
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
        ):
            success, reason = self.module.repair_interrupted_update(
                home,
                None,
                plugin_data=plugin_data,
                allow_host_repair=True,
            )

        self.assertTrue(success, reason)
        registration_check.assert_called_once_with(home)
        register.assert_called_once_with(home)
        self.assertEqual(
            "last-good", (home / "release.txt").read_text(encoding="utf-8")
        )
        self.assertFalse(transaction.exists())

    def test_acknowledged_activation_retirement_fsyncs_directory(self) -> None:
        sessions = self.plugin_data / "science-sessions"
        sessions.mkdir(parents=True)
        marker = sessions / ("a" * 64)
        marker.write_text("{}", encoding="utf-8")

        with (
            mock.patch.dict(
                os.environ,
                {"CODEX_SCIENCE_MIGRATION_ACK": self.module.MIGRATION_ACK_VALUE},
            ),
            mock.patch.object(self.module, "_fsync_directory") as fsync_directory,
        ):
            allowed, reason = self.module._activation_migration_gate(
                self.plugin_data, require_ack=True
            )

        self.assertTrue(allowed, reason)
        self.assertFalse(marker.exists())
        fsync_directory.assert_called_once_with(sessions)

    def test_manual_update_stops_when_interrupted_bootstrap_cannot_be_repaired(
        self,
    ) -> None:
        with (
            mock.patch.object(
                self.module,
                "repair_interrupted_update",
                return_value=(False, "acknowledgement required"),
            ) as repair,
            mock.patch.object(self.module, "get_status") as status,
            mock.patch.object(sys, "stderr", new_callable=io.StringIO),
        ):
            result = self.module.manual_update(self.home, "main")

        self.assertEqual(1, result)
        repair.assert_called_once_with(
            self.home,
            None,
            lock_timeout=self.module.DISPATCH_LOCK_WAIT_SECONDS,
            plugin_data=self.module.canonical_plugin_data(os.environ),
            allow_host_repair=True,
        )
        status.assert_not_called()

    def test_completed_transaction_is_cleaned_without_rollback(self) -> None:
        (self.home / "release.txt").write_text("current", encoding="utf-8")
        transaction = self.home.parent / ".codex-science-update-complete"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("old", encoding="utf-8")
        self.module._journal(transaction, "complete", self.home)

        with mock.patch.object(
            self.module,
            "_eligible_checkout",
            return_value=("b" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
        ):
            success, reason = self.module.repair_interrupted_update(self.home, None)

        self.assertTrue(success, reason)
        self.assertEqual("current", (self.home / "release.txt").read_text())
        self.assertFalse(transaction.exists())

    def test_completed_transaction_restores_previous_if_active_checkout_is_missing(self) -> None:
        self.home.rmdir()
        transaction = self.home.parent / ".codex-science-update-complete-missing"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("last-good", encoding="utf-8")
        self.module._journal(transaction, "complete", self.home)

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                side_effect=lambda root, _branch: (
                    ("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE)
                    if Path(root) == previous
                    else None
                ),
            ),
            mock.patch.object(
                self.module,
                "ensure_managed_marketplace",
                return_value=(True, "registered"),
            ),
            mock.patch.object(
                self.module,
                "register_plugin_preserving_caches",
                return_value=(True, "registered"),
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
        ):
            success, reason = self.module.repair_interrupted_update(self.home, None)

        self.assertTrue(success, reason)
        self.assertEqual("last-good", (self.home / "release.txt").read_text())
        self.assertFalse(transaction.exists())

    def test_interrupted_update_never_promotes_an_untrusted_previous_tree(self) -> None:
        transaction = self.home.parent / ".codex-science-update-untrusted"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("untrusted", encoding="utf-8")
        self.module._journal(transaction, "candidate_active", self.root / "other-home")

        success, reason = self.module.repair_interrupted_update(self.home, None)

        self.assertFalse(success)
        self.assertIn("journal is untrusted", reason)
        self.assertTrue(previous.is_dir())

    def test_interrupted_update_retains_current_when_previous_is_not_verified(self) -> None:
        (self.home / "release.txt").write_text("verified-current", encoding="utf-8")
        transaction = self.home.parent / ".codex-science-update-corrupt-previous"
        previous = transaction / "previous"
        previous.mkdir(parents=True)
        (previous / "release.txt").write_text("corrupt-previous", encoding="utf-8")
        self.module._journal(transaction, "candidate_active", self.home)

        with mock.patch.object(self.module, "_eligible_checkout", return_value=None):
            success, reason = self.module.repair_interrupted_update(self.home, None)

        self.assertFalse(success)
        self.assertIn("previous checkout is not verified", reason)
        self.assertEqual("verified-current", (self.home / "release.txt").read_text())
        self.assertTrue(previous.is_dir())

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
            mock.patch.object(
                self.module, "_plugin_version", return_value=self.BOOTSTRAP_A
            ),
            mock.patch.object(
                self.module, "_runtime_version", return_value=self.RUNTIME_A
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ) as runtime_install,
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
        runtime_install.assert_not_called()

    def test_cache_neutral_update_can_advance_without_replacing_loaded_cache(self) -> None:
        (self.home / "old-source.txt").write_text("old", encoding="utf-8")
        self.write_plugin_version(self.home, "same-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "same-version")
        (plugin_root / "loaded.txt").write_text("keep", encoding="utf-8")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(candidate, "same-version")
                (candidate / "README.md").write_text("new", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")
            if "--name-only" in command:
                return subprocess.CompletedProcess(command, 0, "README.md\0", "")
            if "show" in command and str(command[-1]).endswith(":release/manifest.json"):
                return subprocess.CompletedProcess(
                    command,
                    0,
                    json.dumps(
                        {
                            "cache_neutral_files": ["README.md"],
                            "cache_neutral_prefixes": [],
                            "bootstrap_affecting_files": [],
                            "bootstrap_affecting_prefixes": [],
                        }
                    ),
                    "",
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module, "_mcp_discovery_contract", return_value={"tools": []}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(self.module, "ensure_managed_marketplace") as marketplace,
            mock.patch.object(self.module, "register_plugin_preserving_caches") as register,
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertTrue(success, reason)
        self.assertEqual("new", (self.home / "README.md").read_text())
        self.assertEqual("keep", (plugin_root / "loaded.txt").read_text())
        marketplace.assert_not_called()
        register.assert_not_called()

    def test_runtime_update_with_same_cachebuster_is_rejected(self) -> None:
        self.write_plugin_version(self.home, "same-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "same-version")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(candidate, "same-version")
                return subprocess.CompletedProcess(command, 0, "", "")
            if "--name-only" in command:
                return subprocess.CompletedProcess(
                    command, 0, "scripts/science_mcp.py\0", ""
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("without a new runtime version", reason)
        self.assertTrue(self.home.is_dir())

    def test_static_candidate_gates_precede_candidate_self_check(self) -> None:
        plugin_root = self.root / "loaded-plugin"
        expected = "b" * 40
        cases = (
            (
                "bootstrap drift",
                self.RUNTIME_A,
                self.RUNTIME_B,
                ("scripts/science_update_hook.py",),
                "bootstrap files changed without a new bootstrap version",
            ),
            (
                "runtime downgrade",
                self.RUNTIME_B,
                self.RUNTIME_A,
                ("runtime-skills/codex-science/SKILL.md",),
                "runtime version is not a monotonic advance",
            ),
        )

        for label, home_runtime, candidate_runtime, changed_paths, expected_reason in cases:
            with self.subTest(label=label):
                self.write_plugin_version(
                    self.home,
                    self.BOOTSTRAP_A,
                    runtime_version=home_runtime,
                )
                self.write_plugin_version(
                    plugin_root,
                    self.BOOTSTRAP_A,
                    runtime_version=home_runtime,
                )

                def run(command, **kwargs):
                    if command[:2] == ["git", "clone"]:
                        candidate = Path(command[-1])
                        self.write_plugin_version(
                            candidate,
                            self.BOOTSTRAP_A,
                            runtime_version=candidate_runtime,
                        )
                    return subprocess.CompletedProcess(command, 0, "", "")

                with (
                    mock.patch.object(
                        self.module,
                        "_eligible_checkout",
                        return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
                    ),
                    mock.patch.object(self.module, "_git_output", return_value=expected),
                    mock.patch.object(
                        self.module, "_changed_paths", return_value=changed_paths
                    ),
                    mock.patch.object(
                        self.module,
                        "_release_neutral_policy",
                        return_value=(frozenset({"README.md"}), ("tests/",)),
                    ),
                    mock.patch.object(
                        self.module,
                        "_release_bootstrap_policy",
                        return_value=(frozenset(), ()),
                    ),
                    mock.patch.object(
                        self.module, "_bootstrap_manifest", return_value={"host": "same"}
                    ),
                    mock.patch.object(
                        self.module,
                        "install_runtime_append_only",
                        return_value=(object(), "runtime present"),
                    ),
                    mock.patch.object(self.module, "_run", side_effect=run),
                    mock.patch.object(self.module, "_candidate_self_check") as self_check,
                ):
                    success, reason = self.module.install_update(
                        self.home, "main", expected, plugin_root
                    )

                self.assertFalse(success)
                self.assertIn(expected_reason, reason)
                self_check.assert_not_called()

    def test_incompatible_mcp_contract_precedes_candidate_self_check(self) -> None:
        self.write_plugin_version(self.home, self.BOOTSTRAP_A)
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, self.BOOTSTRAP_A)
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(
                    candidate,
                    self.BOOTSTRAP_A,
                    runtime_version=self.RUNTIME_B,
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(
                self.module,
                "_changed_paths",
                return_value=("runtime-skills/codex-science/SKILL.md",),
            ),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module,
                "_mcp_discovery_contract",
                side_effect=(
                    {"initialize": {"protocolVersion": "2025-06-18"}, "tools": []},
                    {
                        "initialize": {"protocolVersion": "2025-06-18"},
                        "tools": [{"name": "new-tool"}],
                    },
                ),
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(self.module, "_candidate_self_check") as self_check,
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("changes the MCP discovery contract", reason)
        self_check.assert_not_called()

    def test_older_loaded_cache_cannot_bypass_same_cachebuster_runtime_check(self) -> None:
        self.write_plugin_version(self.home, "home-v2")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "loaded-v1")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(candidate, "home-v2")
                return subprocess.CompletedProcess(command, 0, "", "")
            if "--name-only" in command:
                return subprocess.CompletedProcess(
                    command, 0, "scripts/science_mcp.py\0", ""
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, self.module.OFFICIAL_HTTPS_REMOTE),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(self.module, "ensure_managed_marketplace") as marketplace,
            mock.patch.object(self.module, "register_plugin_preserving_caches") as register,
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("curl bootstrap migration", reason)
        marketplace.assert_not_called()
        register.assert_not_called()

    def test_registration_failure_rolls_back_source_and_preserves_loaded_cache(self) -> None:
        (self.home / "old-source.txt").write_text("old", encoding="utf-8")
        self.write_plugin_version(self.home, "old-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "old-version")
        (plugin_root / "loaded.txt").write_text("keep", encoding="utf-8")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(
                    candidate,
                    "new-version",
                    runtime_version=self.RUNTIME_B,
                )
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        with (
            mock.patch.dict(
                os.environ,
                {
                    "CODEX_SCIENCE_MIGRATION_ACK": self.module.MIGRATION_ACK_VALUE,
                    "CODEX_HOME": str(self.codex_home),
                },
            ),
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(
                self.module,
                "_changed_paths",
                return_value=(
                    ".codex-plugin/plugin.json",
                    "scripts/science_hook_dispatch.py",
                ),
            ),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
            mock.patch.object(
                self.module,
                "_activation_migration_gate",
                return_value=(True, "acknowledged"),
            ),
            mock.patch.object(
                self.module,
                "_register_host_now",
                side_effect=[
                    (False, "registration failed"),
                    (True, "previous host restored"),
                ],
            ),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home,
                "main",
                expected,
                None,
                plugin_data=self.plugin_data,
                allow_bootstrap_change=True,
            )

        self.assertFalse(success)
        self.assertIn("registration", reason)
        self.assertEqual("old", (self.home / "old-source.txt").read_text())
        self.assertEqual("keep", (plugin_root / "loaded.txt").read_text())

    def test_second_rename_failure_restores_previous_checkout(self) -> None:
        (self.home / "old-source.txt").write_text("old", encoding="utf-8")
        self.write_plugin_version(self.home, "old-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "old-version")
        expected = "b" * 40
        original_rename = Path.rename

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(
                    candidate,
                    "same-version",
                    runtime_version=self.RUNTIME_B,
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
            mock.patch.object(
                self.module,
                "_changed_paths",
                return_value=("scripts/science_session_hook.py",),
            ),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module, "_mcp_discovery_contract", return_value={"tools": []}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
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
        self.write_plugin_version(self.home, "old-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "old-version")
        expected = "b" * 40

        def run(command, **kwargs):
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(
                    candidate,
                    "same-version",
                    runtime_version=self.RUNTIME_B,
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
            mock.patch.object(
                self.module,
                "_changed_paths",
                return_value=("scripts/science_session_hook.py",),
            ),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module, "_mcp_discovery_contract", return_value={"tools": []}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ),
            mock.patch.object(self.module, "_run", side_effect=run),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertFalse(success)
        self.assertIn("changed during validation", reason)
        self.assertTrue(self.home.is_dir())

    def test_automatic_runtime_update_prepares_runtime_before_swap_without_codex_cli(
        self,
    ) -> None:
        self.write_plugin_version(self.home, "old-version")
        plugin_root = self.root / "loaded-plugin"
        self.write_plugin_version(plugin_root, "old-version")
        expected = "b" * 40
        commands: list[list[str]] = []
        events: list[tuple[str, str]] = []
        original_rename = Path.rename

        def run(command, **kwargs):
            commands.append(list(command))
            if command[:2] == ["git", "clone"]:
                candidate = Path(command[-1])
                self.write_plugin_version(
                    candidate,
                    "same-version",
                    runtime_version=self.RUNTIME_B,
                )
            return subprocess.CompletedProcess(command, 0, "", "")

        def install_runtime(root, environment, *, plugin_data):
            events.append(("install", Path(root).name))
            return object(), "runtime present"

        def rename(path, target):
            events.append(("rename", Path(path).name))
            return original_rename(path, target)

        with (
            mock.patch.object(
                self.module,
                "_eligible_checkout",
                return_value=("a" * 40, "https://github.com/eightmm/codex-science.git"),
            ),
            mock.patch.object(self.module, "_git_output", return_value=expected),
            mock.patch.object(self.module, "_candidate_self_check", return_value=True),
            mock.patch.object(
                self.module,
                "_changed_paths",
                return_value=("scripts/science_session_hook.py",),
            ),
            mock.patch.object(
                self.module,
                "_release_neutral_policy",
                return_value=(frozenset({"README.md"}), ("tests/",)),
            ),
            mock.patch.object(
                self.module,
                "_release_bootstrap_policy",
                return_value=(frozenset(), ()),
            ),
            mock.patch.object(
                self.module, "_bootstrap_manifest", return_value={"host": "same"}
            ),
            mock.patch.object(
                self.module, "_mcp_discovery_contract", return_value={"tools": []}
            ),
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                side_effect=install_runtime,
            ),
            mock.patch.object(
                self.module,
                "ensure_managed_marketplace",
                return_value=(True, "managed marketplace already registered"),
            ) as ensure_marketplace,
            mock.patch.object(
                self.module,
                "register_plugin_preserving_caches",
                return_value=(True, "registered cache added"),
            ) as register,
            mock.patch.object(self.module, "_run", side_effect=run),
            mock.patch.object(Path, "rename", autospec=True, side_effect=rename),
        ):
            success, reason = self.module.install_update(
                self.home, "main", expected, plugin_root
            )

        self.assertTrue(success, reason)
        ensure_marketplace.assert_not_called()
        register.assert_not_called()
        self.assertFalse(
            any(command[:2] == ["codex", "plugin"] for command in commands),
            commands,
        )
        self.assertLess(
            events.index(("install", "candidate")),
            events.index(("rename", self.home.name)),
            events,
        )
        self.assertEqual([], list(self.root.glob(".codex-science-update-*")))

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

    def test_partial_registration_requires_explicit_all_tasks_closed_ack(self) -> None:
        cache_root = (
            self.codex_home / "plugins/cache/codex-science/codex-science"
        )
        old_cache = cache_root / "old-version"
        (old_cache / ".codex-plugin").mkdir(parents=True)
        (old_cache / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"old-version"}', encoding="utf-8"
        )
        (old_cache / "scripts").mkdir()
        (old_cache / "scripts" / "science_stop_hook.py").write_text(
            "old hook", encoding="utf-8"
        )
        source = self.root / "new-source"
        (source / ".codex-plugin").mkdir(parents=True)
        (source / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"new-version"}', encoding="utf-8"
        )
        (source / "scripts").mkdir()
        (source / "scripts" / "science_stop_hook.py").write_text(
            "new hook", encoding="utf-8"
        )

        with (
            mock.patch.object(self.module, "_run") as run,
            mock.patch.object(
                self.module,
                "install_runtime_append_only",
                return_value=(object(), "runtime present"),
            ) as install_runtime,
            mock.patch.object(
                self.module,
                "_host_registration_matches",
                return_value=(False, "not registered"),
            ),
            mock.patch.object(self.module, "_existing_host_state", return_value=True),
        ):
            success, reason = self.module.register_plugin_preserving_caches(source)

        self.assertFalse(success)
        self.assertIn("CODEX_SCIENCE_MIGRATION_ACK", reason)
        self.assertTrue(install_runtime.call_args.kwargs["repair_existing"])
        run.assert_not_called()
        self.assertEqual(
            "old hook",
            (old_cache / "scripts" / "science_stop_hook.py").read_text(encoding="utf-8"),
        )
        self.assertFalse((cache_root / "new-version").exists())

    def test_registration_failure_reports_stdout_when_stderr_is_empty(self) -> None:
        source = self.root / "new-source"
        (source / ".codex-plugin").mkdir(parents=True)
        (source / ".codex-plugin" / "plugin.json").write_text(
            '{"version":"new-version"}', encoding="utf-8"
        )

        with mock.patch.object(
            self.module,
            "_run",
            return_value=subprocess.CompletedProcess(
                [], 1, "registration failed on stdout", ""
            ),
        ), mock.patch.object(
            self.module,
            "install_runtime_append_only",
            return_value=(object(), "runtime present"),
        ), mock.patch.object(
            self.module,
            "_host_registration_matches",
            return_value=(False, "not registered"),
        ), mock.patch.object(
            self.module, "_existing_host_state", return_value=False
        ), mock.patch.object(
            self.module,
            "ensure_managed_marketplace",
            return_value=(True, "marketplace ready"),
        ):
            success, reason = self.module.register_plugin_preserving_caches(source)

        self.assertFalse(success)
        self.assertEqual("registration failed on stdout", reason)

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

        self.assertIn("$PLUGIN_ROOT/scripts/science_hook_dispatch.py", serialized)
        self.assertIn("$PLUGIN_ROOT/scripts/python_runtime.sh", serialized)
        self.assertNotIn("python3", serialized)
        self.assertIn("SessionStart", config["hooks"])
        self.assertIn("UserPromptSubmit", config["hooks"])

    def test_candidate_self_check_reuses_the_running_interpreter(self) -> None:
        candidate = self.root / "candidate"
        for relative in (
            ".codex-plugin/plugin.json",
            ".mcp.json",
            "skills/codex-science/SKILL.md",
            "skills/codex-science/agents/openai.yaml",
            "skills/science-provenance/SKILL.md",
            "skills/science-provenance/agents/openai.yaml",
            "skills/science-review/SKILL.md",
            "skills/science-review/agents/openai.yaml",
            "hooks/hooks.json",
            "scripts/python_runtime.sh",
            "scripts/science_hook_dispatch.py",
            "scripts/science_mcp.py",
            "scripts/science_mcp_proxy.py",
            "scripts/science_runtime_state.py",
            "scripts/science_session_hook.py",
            "scripts/science_stop_hook.py",
            "scripts/science_update_entry.py",
            "scripts/science_update_hook.py",
            "runtime-skills/codex-science/SKILL.md",
            "runtime-skills/codex-science/agents/openai.yaml",
            "runtime-skills/science-provenance/SKILL.md",
            "runtime-skills/science-provenance/agents/openai.yaml",
            "runtime-skills/science-review/SKILL.md",
            "runtime-skills/science-review/agents/openai.yaml",
        ):
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")

        for parent in ("skills", "runtime-skills"):
            for name, implicit in (
                ("codex-science", "true"),
                ("science-provenance", "false"),
                ("science-review", "false"),
            ):
                (candidate / parent / name / "agents" / "openai.yaml").write_text(
                    "interface:\n"
                    f'  display_name: "{name}"\n'
                    '  short_description: "valid metadata"\n'
                    f'  default_prompt: "Use ${name}."\n'
                    "policy:\n"
                    f"  allow_implicit_invocation: {implicit}\n",
                    encoding="utf-8",
                )

        commands = []

        def run(command, **kwargs):
            commands.append(command)
            stdout = ""
            if "science_mcp.py" in " ".join(command):
                stdout = "science_search_skills"
            elif "science_session_hook.py" in " ".join(command):
                stdout = "Codex Science is active"
            elif "--self-check" in command:
                stdout = "self-check: ok"
            return subprocess.CompletedProcess(command, 0, stdout, "")

        with mock.patch.object(self.module, "_run", side_effect=run):
            self.assertTrue(self.module._candidate_self_check(candidate))

        python_commands = [
            command
            for command in commands
            if any(str(value).endswith(".py") for value in command)
        ]
        self.assertTrue(python_commands)
        self.assertTrue(
            all(command[0] == sys.executable for command in python_commands),
            python_commands,
        )

        (candidate / "skills" / "science-review" / "agents" / "openai.yaml").unlink()
        self.assertFalse(self.module._candidate_self_check(candidate))

    def test_updater_and_release_gate_share_cache_neutral_policy(self) -> None:
        from codex_science.version import CACHE_NEUTRAL_FILES, CACHE_NEUTRAL_PREFIXES

        self.assertEqual(tuple(CACHE_NEUTRAL_FILES), self.module.CACHE_NEUTRAL_FILES)
        self.assertEqual(tuple(CACHE_NEUTRAL_PREFIXES), self.module.CACHE_NEUTRAL_PREFIXES)

    def test_installer_uses_staging_and_transactional_reruns(self) -> None:
        installer = (self.repository_root / "scripts" / "install.sh").read_text(encoding="utf-8")

        self.assertIn("--manual-update", installer)
        self.assertIn("--candidate-check", installer)
        self.assertIn("--register-plugin", installer)
        self.assertIn("install_runtime_append_only", installer)
        self.assertIn('"CODEX_SCIENCE_STOP_MODE": "block"', installer)
        self.assertNotIn("git -C \"$INSTALL_DIR\" pull", installer)
        self.assertNotIn("codex plugin marketplace add \"$INSTALL_DIR\"", installer)
        self.assertNotIn("codex plugin add codex-science@codex-science >/dev/null", installer)
        self.assertNotIn("codex plugin add codex-science@codex-science >/dev/null 2>&1 || true", installer)
        self.assertIn("RUNNING_INSTALLER_SHA256", installer)
        self.assertIn("CODEX_SCIENCE_INSTALLER_HANDOFF_COUNT", installer)
        self.assertNotIn("cmp -s \"$RUNNING_INSTALLER\"", installer)

    def test_streamed_installer_hands_off_to_managed_checkout(self) -> None:
        target = self.root / "installed"
        scripts = target / "scripts"
        scripts.mkdir(parents=True)
        (target / ".git").mkdir()
        (scripts / "science_update_hook.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        record = self.root / "handoff"
        (scripts / "install.sh").write_text(
            "#!/bin/sh\n"
            "printf '%s' \"$CODEX_SCIENCE_INSTALLER_HANDOFF\" > \"$HANDOFF_RECORD\"\n",
            encoding="utf-8",
        )
        (scripts / "science_runtime_state.py").write_text(
            "def install_runtime_append_only(root, environment, *, plugin_data, repair_existing=False):\n"
            "    return object(), 'runtime present'\n",
            encoding="utf-8",
        )
        self.make_trusted_checkout(target)
        installer = (self.repository_root / "scripts" / "install.sh").read_text(
            encoding="utf-8"
        )
        head = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        result = subprocess.run(
            ["bash"],
            input=installer,
            capture_output=True,
            text=True,
            check=False,
            env={
                **self.installer_environment(target),
                "FAKE_OFFICIAL_MAIN_COMMIT": head,
                "HANDOFF_RECORD": str(record),
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("1", record.read_text(encoding="utf-8"))

    def test_local_installer_handoff_uses_preupdate_bytes(self) -> None:
        target = self.root / "installed-local"
        scripts = target / "scripts"
        scripts.mkdir(parents=True)
        shutil.copy2(self.repository_root / "scripts" / "install.sh", scripts / "install.sh")
        (scripts / "science_update_entry.py").write_text(
            "import os, pathlib, shutil, sys\n"
            "if sys.argv[1] == '--self-check': raise SystemExit(0)\n"
            "if sys.argv[1] == '--manual-update':\n"
            "    target = pathlib.Path(sys.argv[2]) / 'scripts' / 'install.sh'\n"
            "    replacement = target.with_suffix('.next')\n"
            "    shutil.copy2(os.environ['NEW_INSTALLER_SOURCE'], replacement)\n"
            "    os.replace(replacement, target)\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )
        self.make_trusted_checkout(target)
        head = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        handoff_record = self.root / "local-handoff"
        replacement = self.root / "replacement-installer.sh"
        replacement.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s' \"${CODEX_SCIENCE_INSTALLER_HANDOFF_COUNT:-}\" "
            "> \"$HANDOFF_RECORD\"\n",
            encoding="utf-8",
        )

        result = subprocess.run(
            ["bash", str(scripts / "install.sh")],
            capture_output=True,
            text=True,
            check=False,
            env={
                **self.installer_environment(target),
                "FAKE_OFFICIAL_MAIN_COMMIT": head,
                "HANDOFF_RECORD": str(handoff_record),
                "NEW_INSTALLER_SOURCE": str(replacement),
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("1", handoff_record.read_text(encoding="utf-8"))

    def test_streamed_installer_uses_exact_main_helper_before_legacy_updater(self) -> None:
        target = self.root / "installed"
        scripts = target / "scripts"
        scripts.mkdir(parents=True)
        (target / ".git").mkdir()
        (scripts / "science_update_hook.py").write_text(
            "import os, pathlib, sys\n"
            "if sys.argv[1] == '--ensure-marketplace':\n"
            "    print('legacy marketplace listing failed', file=sys.stderr)\n"
            "    raise SystemExit(1)\n"
            "if sys.argv[1] == '--manual-update':\n"
            "    pathlib.Path(os.environ['LEGACY_UPDATE_RECORD']).touch()\n"
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        handoff_record = self.root / "handoff"
        (scripts / "install.sh").write_text(
            "#!/bin/sh\n"
            "printf '%s' \"$CODEX_SCIENCE_INSTALLER_HANDOFF\" > \"$HANDOFF_RECORD\"\n",
            encoding="utf-8",
        )
        self.make_trusted_checkout(target)

        environment = self.installer_environment(target)
        fake_bin = Path(environment["PATH"].split(":", 1)[0])
        marketplace_record = self.root / "marketplace-repaired"
        legacy_update_record = self.root / "legacy-update"
        modern_update_record = self.root / "modern-update"
        recovery_helper = self.root / "recovery-helper.py"
        recovery_helper.write_text(
            "import os, pathlib, subprocess, sys\n"
            "if sys.argv[1] == '--self-check':\n"
            "    raise SystemExit(0)\n"
            "if sys.argv[1] == '--ensure-marketplace':\n"
            "    raise SystemExit(subprocess.run([\n"
            "        'codex', 'plugin', 'marketplace', 'add', sys.argv[2]\n"
            "    ]).returncode)\n"
            "if sys.argv[1] == '--manual-update':\n"
            "    pathlib.Path(os.environ['MODERN_UPDATE_RECORD']).touch()\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )
        (fake_bin / "codex").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = plugin ] && [ \"$2\" = marketplace ] && [ \"$3\" = list ]; then\n"
            "  printf '%s\\n' '{\"marketplaces\":[]}'\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = plugin ] && [ \"$2\" = marketplace ] && [ \"$3\" = add ]; then\n"
            "  printf '%s' \"$4\" > \"$MARKETPLACE_RECORD\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 0\n",
            encoding="utf-8",
        )
        (fake_bin / "curl").write_text(
            "#!/bin/sh\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = -o ]; then\n"
            "    cp \"$RECOVERY_HELPER_SOURCE\" \"$2\"\n"
            "    exit 0\n"
            "  fi\n"
            "  shift\n"
            "done\n"
            "exit 1\n",
            encoding="utf-8",
        )
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        (fake_bin / "git").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = ls-remote ]; then\n"
            f"  printf '%s\\trefs/heads/main\\n' '{'c' * 40}'\n"
            "  exit 0\n"
            "fi\n"
            f"exec {real_git} \"$@\"\n",
            encoding="utf-8",
        )
        for path in fake_bin.iterdir():
            path.chmod(0o755)

        installer = (self.repository_root / "scripts" / "install.sh").read_text(
            encoding="utf-8"
        )
        result = subprocess.run(
            ["bash"],
            input=installer,
            capture_output=True,
            text=True,
            check=False,
            env={
                **environment,
                "HANDOFF_RECORD": str(handoff_record),
                "LEGACY_UPDATE_RECORD": str(legacy_update_record),
                "MARKETPLACE_RECORD": str(marketplace_record),
                "MODERN_UPDATE_RECORD": str(modern_update_record),
                "RECOVERY_HELPER_SOURCE": str(recovery_helper),
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertFalse(marketplace_record.exists())
        self.assertFalse(legacy_update_record.exists())
        self.assertTrue(modern_update_record.is_file())
        self.assertEqual("1", handoff_record.read_text(encoding="utf-8"))

    def test_streamed_installer_never_executes_a_dirty_managed_updater(self) -> None:
        target = self.root / "dirty-installed"
        scripts = target / "scripts"
        scripts.mkdir(parents=True)
        (scripts / "science_update_hook.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8"
        )
        self.make_trusted_checkout(target)
        execution_marker = self.root / "dirty-updater-executed"
        (scripts / "science_update_hook.py").write_text(
            "import os, pathlib\n"
            "pathlib.Path(os.environ['DIRTY_EXECUTION_MARKER']).touch()\n",
            encoding="utf-8",
        )

        environment = self.installer_environment(target)
        fake_bin = Path(environment["PATH"].split(":", 1)[0])
        recovery_helper = self.root / "reject-dirty-helper.py"
        recovery_helper.write_text(
            "import sys\n"
            "if sys.argv[1] in {'--self-check', '--ensure-marketplace'}:\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(1)\n",
            encoding="utf-8",
        )
        (fake_bin / "curl").write_text(
            "#!/bin/sh\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = -o ]; then cp \"$RECOVERY_HELPER_SOURCE\" \"$2\"; exit 0; fi\n"
            "  shift\n"
            "done\n"
            "exit 1\n",
            encoding="utf-8",
        )
        real_git = shutil.which("git")
        self.assertIsNotNone(real_git)
        (fake_bin / "git").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = ls-remote ]; then\n"
            f"  printf '%s\\trefs/heads/main\\n' '{'d' * 40}'\n"
            "  exit 0\n"
            "fi\n"
            f"exec {real_git} \"$@\"\n",
            encoding="utf-8",
        )
        for path in fake_bin.iterdir():
            path.chmod(0o755)

        result = subprocess.run(
            ["bash"],
            input=(self.repository_root / "scripts" / "install.sh").read_text(
                encoding="utf-8"
            ),
            capture_output=True,
            text=True,
            check=False,
            env={
                **environment,
                "DIRTY_EXECUTION_MARKER": str(execution_marker),
                "RECOVERY_HELPER_SOURCE": str(recovery_helper),
            },
        )

        self.assertNotEqual(0, result.returncode)
        self.assertFalse(execution_marker.exists())

    def test_streamed_installer_provisions_uv_python_when_python3_is_too_old(self) -> None:
        target = self.root / "installed"
        scripts = target / "scripts"
        scripts.mkdir(parents=True)
        (target / ".git").mkdir()
        update_record = self.root / "update-python"
        (scripts / "science_update_hook.py").write_text(
            "import os, pathlib, sys\n"
            "pathlib.Path(os.environ['UPDATE_RECORD']).write_text(sys.executable)\n",
            encoding="utf-8",
        )
        handoff_record = self.root / "handoff"
        (scripts / "install.sh").write_text(
            "#!/bin/sh\n"
            "printf '%s' \"$CODEX_SCIENCE_INSTALLER_HANDOFF\" > \"$HANDOFF_RECORD\"\n",
            encoding="utf-8",
        )
        self.make_trusted_checkout(target)

        fake_bin = self.root / "python38-bin"
        fake_bin.mkdir()
        (fake_bin / "codex").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (fake_bin / "python3").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        head = subprocess.run(
            ["git", "-C", str(target), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        (fake_bin / "git").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = ls-remote ]; then\n"
            f"  printf '%s\\trefs/heads/main\\n' '{head}'\n"
            "  exit 0\n"
            "fi\n"
            "exec /usr/bin/git \"$@\"\n",
            encoding="utf-8",
        )
        uv_marker = self.root / "uv-installed"
        (fake_bin / "uv").write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = python ] && [ \"$2\" = install ]; then\n"
            "  : > \"$UV_MARKER\"\n"
            "  exit 0\n"
            "fi\n"
            "if [ \"$1\" = python ] && [ \"$2\" = find ] && [ -f \"$UV_MARKER\" ]; then\n"
            "  printf '%s\\n' \"$MANAGED_PYTHON\"\n"
            "  exit 0\n"
            "fi\n"
            "exit 1\n",
            encoding="utf-8",
        )
        for path in fake_bin.iterdir():
            path.chmod(0o755)

        installer = (self.repository_root / "scripts" / "install.sh").read_text(
            encoding="utf-8"
        )
        result = subprocess.run(
            ["bash"],
            input=installer,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "CODEX_SCIENCE_HOME": str(target),
                "CODEX_SCIENCE_RUNTIME_FILE": str(self.root / "runtime-python"),
                "HANDOFF_RECORD": str(handoff_record),
                "MANAGED_PYTHON": sys.executable,
                "UPDATE_RECORD": str(update_record),
                "UV_MARKER": str(uv_marker),
                "PATH": f"{fake_bin}:/usr/bin:/bin",
            },
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue(uv_marker.is_file())
        self.assertEqual(sys.executable, update_record.read_text(encoding="utf-8"))
        self.assertEqual("1", handoff_record.read_text(encoding="utf-8"))

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
        (scripts / "python_runtime.sh").write_text("#!/bin/sh\nexec python3 \"$@\"\n", encoding="utf-8")
        (scripts / "science_update_hook.py").write_text(
            "import sys\n"
            "def _installed_cache_matches(root): return True\n"
            "if __name__ == '__main__': raise SystemExit(0)\n",
            encoding="utf-8",
        )
        (scripts / "science_runtime_state.py").write_text(
            "def install_runtime_append_only(root, environment, *, plugin_data, repair_existing=False):\n"
            "    return object(), 'runtime present'\n",
            encoding="utf-8",
        )
        (scripts / "science_mcp.py").write_text(
            "print('science_search_skills')\n", encoding="utf-8"
        )
        (scripts / "science_mcp_proxy.py").write_text(
            "import json, sys\n"
            "for raw in sys.stdin:\n"
            "    request = json.loads(raw)\n"
            "    if 'id' in request:\n"
            "        result = ({'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, "
            "'serverInfo': {'name': 'fixture', 'version': '1'}} "
            "if request.get('method') == 'initialize' else "
            "{'tools': [{'name': 'science_search_skills'}]})\n"
            "        print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], "
            "'result': result}), flush=True)\n",
            encoding="utf-8",
        )
        (scripts / "science_session_hook.py").write_text(
            "import hashlib, json, os, pathlib, sys\n"
            "payload = json.load(sys.stdin)\n"
            "session_id = payload['session_id']\n"
            "generation = 'b' * 64\n"
            "owner = hashlib.sha256((session_id + '\\0' + generation).encode()).hexdigest()\n"
            "goal_key = hashlib.sha256(session_id.encode()).hexdigest()\n"
            "marker = pathlib.Path(os.environ['PLUGIN_DATA']) / 'science-sessions' / hashlib.sha256(session_id.encode()).hexdigest()\n"
            "marker.parent.mkdir(parents=True, exist_ok=True)\n"
            "marker.write_text(json.dumps({'schema_version': 2, 'generation': generation, "
            "'runtime_pin': {'runtime_version': '0.5.0+codex.20260803054000', "
            "'runtime_commit': 'a' * 40, 'receipt_sha256': 'c' * 64}}))\n"
            "context = 'Codex Science is active --session-key ' + owner + ' --goal-task-key ' + goal_key\n"
            "print(json.dumps({'hookSpecificOutput': {'additionalContext': context}}))\n",
            encoding="utf-8",
        )
        (scripts / "science_checkpoint.py").write_text(
            "import json, pathlib, sys\n"
            "command, run_dir = sys.argv[1], pathlib.Path(sys.argv[2])\n"
            "path = run_dir / 'checkpoint.json'\n"
            "if command == 'init':\n"
            "    run_dir.mkdir(parents=True, exist_ok=True)\n"
            "    goal_key = sys.argv[sys.argv.index('--goal-task-key') + 1]\n"
            "    value = {'state': 'active', 'schema_version': 4, 'outer_goal': {'task_key': goal_key}}\n"
            "elif command == 'wait':\n"
            "    value = json.loads(path.read_text())\n"
            "    value['state'] = 'waiting_external'\n"
            "else:\n"
            "    raise SystemExit(2)\n"
            "path.write_text(json.dumps(value))\n"
            "print(json.dumps(value))\n",
            encoding="utf-8",
        )
        (scripts / "science_stop_hook.py").write_text(
            "import json, pathlib, sys\n"
            "payload = json.load(sys.stdin)\n"
            "paths = list((pathlib.Path(payload['cwd']) / 'artifacts').glob('*/checkpoint.json'))\n"
            "if paths and json.loads(paths[0].read_text()).get('state') == 'active':\n"
            "    print(json.dumps({'decision': 'block'}))\n",
            encoding="utf-8",
        )
        (scripts / "science_hook_dispatch.py").write_text(
            "import json, os, pathlib, subprocess, sys\n"
            "payload = json.load(sys.stdin)\n"
            "name = 'science_stop_hook.py' if payload.get('hook_event_name') == 'Stop' else 'science_session_hook.py'\n"
            "script = pathlib.Path(__file__).with_name(name)\n"
            "result = subprocess.run([sys.executable, str(script)], input=json.dumps(payload), text=True, capture_output=True, env=os.environ)\n"
            "sys.stdout.write(result.stdout)\n"
            "raise SystemExit(result.returncode)\n",
            encoding="utf-8",
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
                "CODEX_SCIENCE_RUNTIME_FILE": str(self.root / "runtime-python"),
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
