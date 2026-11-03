import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from codex_science.release import load_release_manifest, manifest_runtime_version, release_version_advances, validate_release
from codex_science.version import PACKAGE_VERSION


ROOT = Path(__file__).resolve().parents[1]
BASE_PLUGIN = "1.0.0+codex.20260101000000"
BASE_RUNTIME = "1.0.0+codex.20260101000000"
NEXT_PLUGIN = "1.0.0+codex.20260102000000"
NEXT_RUNTIME = "1.0.0+codex.20260102000000"


class ReleasePathRefusalTests(unittest.TestCase):
    def test_candidate_root_must_be_a_directory(self) -> None:
        self.check_invalid_roots("candidate_contract_check.py", include_empty=False)

    def test_release_root_must_contain_release_files(self) -> None:
        self.check_invalid_roots("validate_release.py", include_empty=True)

    def check_invalid_roots(self, script: str, *, include_empty: bool) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            regular = root / "file"
            regular.write_bytes(b"preserve")
            empty = root / "empty"
            empty.mkdir()
            loop = root / "loop"
            loop.symlink_to(loop.name)
            paths = [loop, loop / "child", root / "missing", regular]
            if include_empty:
                paths.append(empty)
            for path in paths:
                with self.subTest(script=script, path=path.name):
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "scripts" / script), "--root", str(path)],
                        cwd=root, capture_output=True, text=True,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertIn("error: ", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)
                    self.assertEqual(b"preserve", regular.read_bytes())
                    self.assertEqual([], list(empty.iterdir()))
                    self.assertEqual({"file", "empty", "loop"}, {item.name for item in root.iterdir()})


class ReleaseLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        for relative in (".codex-plugin/plugin.json", "pyproject.toml", "release/manifest.json"):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes())

    def test_lock_root_version_and_optional_file(self) -> None:
        lock = self.root / "uv.lock"
        self.assertEqual([], validate_release(self.root))
        for source in ("editable", "virtual"):
            for version in (PACKAGE_VERSION, "9.9.9", "", "0", 0, [], None):
                with self.subTest(source=source, version=version):
                    version_line = "" if version is None else f'version = {json.dumps(version)}\n'
                    lock.write_text(
                        '[[package]]\nname = "dependency"\nversion = "9.9.9"\n'
                        'source = { registry = "index" }\n'
                        '[[package]]\nname = "codex-science"\n' + version_line
                        + f'source = {{ {source} = "." }}\n', encoding="utf-8",
                    )
                    errors = validate_release(self.root)
                    if version == PACKAGE_VERSION:
                        self.assertEqual([], errors)
                    else:
                        self.assertTrue(any("uv.lock" in error and "mismatch" in error for error in errors), errors)
        lock.unlink()
        self.assertEqual([], validate_release(self.root))

    def test_lock_malformed_toml_is_labelled(self) -> None:
        (self.root / "uv.lock").write_text("[[package]\n", encoding="utf-8")
        errors = validate_release(self.root)
        self.assertTrue(any("uv.lock" in error and "TOML" in error for error in errors), errors)

    def test_lock_requires_one_root_package(self) -> None:
        valid = ('[[package]]\nname = "codex-science"\n'
                 f'version = "{PACKAGE_VERSION}"\nsource = {{ editable = "." }}\n')
        for content in ("", "package = 0\n", "package = {}\n", "package = [0]\n",
                        valid.replace("codex-science", "dependency"),
                        valid.replace('source = { editable = "." }', 'source = 0'),
                        valid.replace('source = { editable = "." }', ''),
                        valid.replace('editable = "."', 'editable = "subdir"'),
                        valid.replace('editable = "."', 'registry = "index"'), valid + valid):
            with self.subTest(content=content):
                (self.root / "uv.lock").write_text(content, encoding="utf-8")
                errors = validate_release(self.root)
                self.assertTrue(any("uv.lock" in error for error in errors), errors)


    def test_non_object_release_inputs_are_labelled(self) -> None:
        sources = {relative: (self.root / relative).read_bytes()
                   for relative in (".codex-plugin/plugin.json", "pyproject.toml", "release/manifest.json")}
        cases = [(".codex-plugin/plugin.json", content, "plugin.json must be a JSON object")
                 for content in ("[]", "0", "null", '"text"')]
        cases += [("pyproject.toml", content, "pyproject.toml project must be a table")
                  for content in ('project = "x"\n', "project = 0\n", "project = []\n")]
        cases += [("release/manifest.json", content, "release manifest must be a JSON object")
                  for content in ("[]", "0", "null", '"text"')]
        for relative, content, message in cases:
            with self.subTest(relative=relative, content=content):
                (self.root / relative).write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(ValueError, message):
                    validate_release(self.root)
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/validate_release.py"), "--root", str(self.root)],
                    capture_output=True, text=True, timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")))
                self.assertEqual(1, result.returncode, result.stderr)
                self.assertEqual(f"error: {message}\n", result.stderr)
                (self.root / relative).write_bytes(sources[relative])
        (self.root / "pyproject.toml").write_text("", encoding="utf-8")
        self.assertTrue(any("package_version mismatch" in error for error in validate_release(self.root)))

    def test_schema_version_must_be_an_integer(self) -> None:
        manifest = self.root / "release" / "manifest.json"
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        current = payload["schema_version"]
        self.assertEqual([], [error for error in validate_release(self.root) if "schema" in error])
        for schema in (True, float(current), str(current)):
            with self.subTest(schema=schema):
                manifest.write_text(json.dumps({**payload, "schema_version": schema}), encoding="utf-8")
                for check in (validate_release, load_release_manifest):
                    with self.assertRaisesRegex(ValueError, "unsupported release manifest schema"):
                        check(self.root)

    def test_release_version_requires_ascii_digits(self) -> None:
        from codex_science.release import RELEASE_VERSION_RE
        self.assertIsNotNone(RELEASE_VERSION_RE.fullmatch("1.0.0+codex." + "0" * 14))
        for version in ("1.0.0+codex." + "0" * 13, "1.0.0+codex." + "0" * 15,
                        "1.0.0+codex." + "\u0660" * 14, "1.0.0+codex." + "0" * 13 + "\u0661",
                        "\u0661.0.0+codex." + "0" * 14, "1.0.\uff10+codex." + "0" * 14):
            with self.subTest(version=version):
                self.assertIsNone(RELEASE_VERSION_RE.fullmatch(version))
                self.assertFalse(release_version_advances(BASE_RUNTIME, version))


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


STUB_MCP_SERVER = """\
import json, pathlib, sys
description = pathlib.Path(__file__).resolve().parents[1].joinpath(
    "src", "codex_science", "mcp_server.py").read_text().strip()
for line in sys.stdin:
    request = json.loads(line)
    if request.get("method") == "initialize":
        result = {"protocolVersion": "1", "capabilities": {}, "serverInfo": {"name": "stub"}}
    elif request.get("method") == "tools/list":
        result = {"tools": [{"name": "tool", "description": description, "inputSchema": {}}]}
    else:
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}), flush=True)
"""


class McpContractGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        script = ROOT / "scripts" / "validate_release.py"
        spec = importlib.util.spec_from_file_location("validate_release_mcp_script", script)
        if spec is None or spec.loader is None:
            raise RuntimeError("could not load validate_release.py")
        cls.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.validator)

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.git("config", "user.email", "release@test.invalid")
        self.git("config", "user.name", "Release Test")
        self.write_release(BASE_PLUGIN)
        for relative, content in (
            ("scripts/science_mcp.py", STUB_MCP_SERVER),
            ("catalog/inventory.json", "{}\n"),
            ("src/codex_science/mcp_server.py", "description A\n"),
            ("docs/guide.md", "A\n"),
        ):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.commit("base")
        self.base = self.git("rev-parse", "HEAD")

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.root), *arguments],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def commit(self, message: str) -> None:
        self.git("add", ".")
        self.git("commit", "-q", "-m", message)

    def write_release(self, plugin_version: str) -> None:
        plugin = self.root / ".codex-plugin" / "plugin.json"
        plugin.parent.mkdir(parents=True, exist_ok=True)
        plugin.write_text(json.dumps({"version": plugin_version}) + "\n", encoding="utf-8")
        manifest = self.root / "release" / "manifest.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "schema_version": 2, "plugin_version": plugin_version,
            "runtime_version": plugin_version, "runtime_affecting_prefixes": [],
        }) + "\n", encoding="utf-8")

    def errors(self) -> list[str]:
        return self.validator._mcp_contract_errors(self.root, self.base)

    def test_description_change_without_plugin_bump_fails(self) -> None:
        (self.root / "src/codex_science/mcp_server.py").write_text("description B\n", encoding="utf-8")
        self.commit("describe tool")
        errors = self.errors()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("tool tool changed description", errors[0])
        self.assertIn("bootstrap version and curl migration", errors[0])

    def test_description_change_with_plugin_bump_passes(self) -> None:
        (self.root / "src/codex_science/mcp_server.py").write_text("description B\n", encoding="utf-8")
        self.write_release(NEXT_PLUGIN)
        self.commit("describe tool with bootstrap bump")
        self.assertEqual([], self.errors())

    def test_change_outside_mcp_surface_passes(self) -> None:
        (self.root / "docs/guide.md").write_text("B\n", encoding="utf-8")
        self.commit("docs")
        self.assertEqual([], self.errors())

    def test_uncomputable_contract_is_an_error(self) -> None:
        (self.root / "scripts/science_mcp.py").unlink()
        self.commit("drop server")
        errors = self.errors()
        self.assertEqual(1, len(errors), errors)
        self.assertIn("could not verify the MCP discovery contract", errors[0])

    def test_root_without_base_ref_does_not_probe_the_server(self) -> None:
        def refuse() -> None:
            raise AssertionError("MCP probe must not run without --base-ref")

        original = self.validator._load_mcp_contract_probe
        self.validator._load_mcp_contract_probe = refuse
        self.addCleanup(setattr, self.validator, "_load_mcp_contract_probe", original)
        argv = sys.argv
        sys.argv = ["validate_release.py", "--root", str(self.root)]
        self.addCleanup(setattr, sys, "argv", argv)
        try:
            self.validator.main()
        except SystemExit:  # the fixture's own verdict is irrelevant; only the probe matters
            pass


if __name__ == "__main__":
    unittest.main()
