import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlsplit

from codex_science.artifacts import new_manifest, write_manifest
from codex_science.review import review_manifest
from codex_science.wrappers import (
    check_wrappers,
    generate_wrappers,
    render_agent_manifest,
    render_skill_wrapper,
)


def make_record(
    name: str,
    *,
    status: str = "active",
    reasons: list[str] | None = None,
    physical_lab: bool = False,
    instruction_line_count: int = 10,
) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Use {name} for a scientific workflow.",
        "license": "MIT",
        "path": f"vendor/scientific-agent-skills/skills/{name}",
        "status": status,
        "reasons": reasons or [],
        "physical_lab": physical_lab,
        "instruction_line_count": instruction_line_count,
    }


def authored_markdown_link_offenders(root: Path) -> list[str]:
    root = root.resolve()
    offenders = []
    for markdown_file in sorted((root / "authored-skills").rglob("*.md")):
        text = markdown_file.read_text(encoding="utf-8")
        for match in re.finditer(r"\]\(([^)]*)\)", text):
            target = match.group(1).strip()
            if not target or urlsplit(target).scheme or target.startswith("#"):
                continue
            relative_target = target.split("#", 1)[0]
            if not relative_target:
                continue
            resolved = (markdown_file.parent / relative_target).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                offenders.append(f"{markdown_file.relative_to(root)}: {target}")
                continue
            if not resolved.exists():
                offenders.append(f"{markdown_file.relative_to(root)}: {target}")
    return offenders


class WrapperRenderingTests(unittest.TestCase):
    def test_active_wrapper_points_to_pinned_source(self) -> None:
        wrapper = render_skill_wrapper(make_record("sympy"))

        self.assertIn("name: sympy", wrapper)
        self.assertIn("Status: `active`", wrapper)
        self.assertIn("../../../vendor/scientific-agent-skills/skills/sympy/SKILL.md", wrapper)
        self.assertIn("../../inventory.json", wrapper)
        self.assertIn("$science-provenance", wrapper)
        self.assertIn('"<plugin-root>/scripts/search_skills.py" --name sympy`', wrapper)
        self.assertNotIn("Read the matching inventory record", wrapper)

    def test_inactive_wrapper_preserves_every_blocking_reason(self) -> None:
        wrapper = render_skill_wrapper(
            make_record(
                "remote-lab",
                status="inactive",
                reasons=["credentials-required", "executable-content"],
            )
        )

        self.assertIn("credentials-required", wrapper)
        self.assertIn("executable-content", wrapper)
        self.assertIn("explicit acknowledgement", wrapper)
        self.assertIn("Do not read the upstream instructions", wrapper)

    def test_every_generated_skill_requires_explicit_invocation(self) -> None:
        manifest = render_agent_manifest(make_record("sympy"))

        self.assertIn('default_prompt: "Use $sympy', manifest)
        self.assertIn("allow_implicit_invocation: false", manifest)

    def test_long_upstream_description_is_bounded_for_codex(self) -> None:
        record = make_record("long-description")
        record["description"] = "scientific workflow " * 80

        wrapper = render_skill_wrapper(record)
        description_line = next(line for line in wrapper.splitlines() if line.startswith("description: "))
        description = json.loads(description_line.removeprefix("description: "))

        self.assertLessEqual(len(description), 1024)
        self.assertTrue(description.endswith("…"))

    def test_physical_lab_wrapper_requires_device_and_biosafety_approval(self) -> None:
        wrapper = render_skill_wrapper(make_record("pylabrobot", physical_lab=True))

        self.assertIn("real laboratory hardware", wrapper)
        self.assertIn("explicit user approval", wrapper)
        self.assertIn("Simulate or dry-run first", wrapper)
        self.assertIn("biosafety/containment level", wrapper)
        self.assertIn("emergency-stop/abort path", wrapper)

    def test_oversized_upstream_skill_uses_progressive_loading(self) -> None:
        wrapper = render_skill_wrapper(
            make_record("large-skill", instruction_line_count=501)
        )

        self.assertIn("501 lines", wrapper)
        self.assertIn("Inspect its headings first", wrapper)
        self.assertIn("only the sections relevant", wrapper)


class WrapperGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.output = self.root / "skills"
        self.inventory = {
            "schema_version": 1,
            "skills": [
                make_record("sympy"),
                make_record("remote-lab", status="inactive", reasons=["credentials-required"]),
            ],
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_generation_is_complete_and_deterministic(self) -> None:
        core = self.output / "core-skill"
        core.mkdir(parents=True)
        (core / "SKILL.md").write_text("preserve me\n", encoding="utf-8")

        summary = generate_wrappers(self.inventory, self.output)
        first = (self.output / "sympy" / "SKILL.md").read_bytes()
        generate_wrappers(self.inventory, self.output)

        self.assertEqual({"generated": 2, "active": 1, "inactive": 1}, summary)
        self.assertEqual(first, (self.output / "sympy" / "SKILL.md").read_bytes())
        self.assertEqual("preserve me\n", (core / "SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual([], check_wrappers(self.inventory, self.output))

    def test_check_reports_modified_and_missing_wrappers(self) -> None:
        generate_wrappers(self.inventory, self.output)
        (self.output / "sympy" / "SKILL.md").write_text("modified\n", encoding="utf-8")
        (self.output / "remote-lab" / "SKILL.md").unlink()

        errors = check_wrappers(self.inventory, self.output)

        self.assertTrue(any("sympy/SKILL.md is stale" in error for error in errors))
        self.assertTrue(any("remote-lab/SKILL.md is missing" in error for error in errors))

    def test_repository_contains_one_wrapper_per_inventory_record(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())

        self.assertEqual([], check_wrappers(inventory, repository_root / "catalog" / "codex-skills"))

    def test_unsafe_names_are_refused_without_output(self) -> None:
        for name in (
            "", ".", "..", "../escaped", "a/b", "a\\b", "/escaped",
            ".hidden", "bad\x00name", None, 0, [],
        ):
            record = make_record("safe")
            record["name"] = name
            for operation in (generate_wrappers, check_wrappers):
                with self.subTest(name=name, operation=operation.__name__):
                    with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                        output = Path(temporary) / "out"
                        with self.assertRaisesRegex(ValueError, "[Ss]kill record.*name"):
                            operation({"skills": [record]}, output)
                        self.assertFalse(output.exists())
                        self.assertFalse((Path(temporary) / "escaped").exists())

    def test_symlink_destinations_are_refused_before_any_write(self) -> None:
        record = make_record("z-linked")
        for relative in (
            "z-linked", "z-linked/agents", "z-linked/SKILL.md",
            "z-linked/agents/openai.yaml",
        ):
            for target_kind in ("outside", "inside", "dangling"):
                with self.subTest(relative=relative, target_kind=target_kind):
                    with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                        base = Path(temporary)
                        output = base / "out"
                        link = output / relative
                        link.parent.mkdir(parents=True, exist_ok=True)
                        target = (
                            output / "target" if target_kind == "inside" else base / "target"
                        )
                        is_file = link.name in {"SKILL.md", "openai.yaml"}
                        if target_kind != "dangling":
                            if is_file:
                                target.write_text(render_skill_wrapper(record), encoding="utf-8")
                            else:
                                target.mkdir()
                        link.symlink_to(target, target_is_directory=not is_file)
                        before = target.read_bytes() if target.is_file() else None
                        for operation in (generate_wrappers, check_wrappers):
                            with self.subTest(operation=operation.__name__):
                                with self.assertRaisesRegex(ValueError, "[Uu]nsafe wrapper destination"):
                                    operation(
                                        {"skills": [make_record("a-first"), record]}, output
                                    )
                                self.assertFalse((output / "a-first").exists())
                                if target.is_file():
                                    self.assertEqual(before, target.read_bytes())
                                elif target.exists():
                                    self.assertEqual([], list(target.iterdir()))
        for relative_output in (False, True):
            for root_link in (False, True):
                for existing in (False, True):
                    for records in ([], [record]):
                        with self.subTest(
                            relative_output=relative_output, root_link=root_link,
                            existing=existing, records=bool(records),
                        ):
                            with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                                base = Path(temporary)
                                target = base / "real"
                                if existing:
                                    target.mkdir()
                                alias = base / "alias"
                                alias.symlink_to("real", target_is_directory=True)
                                output = alias if root_link else alias / "out"
                                expected = target if root_link else target / "out"
                                if relative_output:
                                    output = Path(os.path.relpath(output))
                                inventory = {"skills": records}
                                summary = generate_wrappers(inventory, output)
                                self.assertEqual(len(records), summary["generated"])
                                self.assertEqual([], check_wrappers(inventory, output))
                                self.assertTrue(expected.is_dir())
                                if records:
                                    self.assertEqual(
                                        render_skill_wrapper(record),
                                        (expected / "z-linked/SKILL.md").read_text(encoding="utf-8"),
                                    )
                                (expected / "redirected").symlink_to(
                                    base / "outside", target_is_directory=True
                                )
                                linked_inventory = {"skills": [*records, make_record("redirected")]}
                                for operation in (generate_wrappers, check_wrappers):
                                    with self.assertRaisesRegex(ValueError, "[Uu]nsafe wrapper destination"):
                                        operation(linked_inventory, output)
                                self.assertFalse((base / "outside").exists())
        loop = self.root / "loop"
        loop.symlink_to("loop", target_is_directory=True)
        root_file = self.root / "root-file"
        root_file.write_text("preserve me\n", encoding="utf-8")
        file_link = self.root / "file-link"
        file_link.symlink_to(root_file)
        for output in (loop, file_link, self.root / "bad\x00root"):
            for operation in (generate_wrappers, check_wrappers):
                with self.subTest(operation=operation.__name__, invalid_root=output.name):
                    with self.assertRaisesRegex(ValueError, "[Uu]nsafe wrapper destination"):
                        operation({"skills": []}, output)
        self.assertEqual("preserve me\n", root_file.read_text(encoding="utf-8"))

    def test_all_records_are_rendered_before_creating_or_updating_outputs(self) -> None:
        first = make_record("a-first")
        invalid = make_record("z-invalid")
        for existing in (False, True):
            for count in (True, -1, 1.5, "1", None):
                with self.subTest(existing=existing, count=count):
                    with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                        output = Path(temporary) / "out"
                        if existing:
                            generate_wrappers({"skills": [first, make_record("stale")]}, output)
                        before = {
                            path.relative_to(output): path.read_bytes()
                            for path in output.rglob("*") if path.is_file()
                        }
                        invalid["instruction_line_count"] = count
                        changed = dict(first, description="Changed description")
                        with self.assertRaisesRegex(ValueError, "z-invalid.*instruction line count"):
                            generate_wrappers({"skills": [changed, invalid]}, output)
                        after = {
                            path.relative_to(output): path.read_bytes()
                            for path in output.rglob("*") if path.is_file()
                        }
                        self.assertEqual(before, after)
                        self.assertEqual(existing, output.exists())
        for count in (0, 500, 501):
            first["instruction_line_count"] = count
            generate_wrappers({"skills": [first]}, self.output)
            self.assertEqual([], check_wrappers({"skills": [first]}, self.output))
        self.assertEqual(
            {"generated": 0, "active": 0, "inactive": 0},
            generate_wrappers({"skills": []}, self.output),
        )
        self.assertEqual([], list(self.output.iterdir()))

    def test_late_destination_conflicts_preserve_earlier_outputs(self) -> None:
        first = make_record("a-first")
        last = make_record("z-last")
        for relative in (
            ".", "z-last", "z-last/SKILL.md", "z-last/agents", "z-last/agents/openai.yaml",
        ):
            with self.subTest(relative=relative):
                with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                    output = Path(temporary) / "out"
                    conflict = output / relative
                    conflict.parent.mkdir(parents=True, exist_ok=True)
                    if conflict.name == "SKILL.md":
                        conflict.write_text("handwritten\n", encoding="utf-8")
                        error_type = FileExistsError
                    elif relative in (".", "z-last", "z-last/agents"):
                        conflict.write_text("not a directory\n", encoding="utf-8")
                        error_type = ValueError
                    else:
                        conflict.mkdir()
                        error_type = ValueError
                    with self.assertRaises(error_type):
                        generate_wrappers({"skills": [first, last]}, output)
                    self.assertFalse((output / "a-first").exists())

    def test_stale_symlink_is_refused_without_cleanup(self) -> None:
        outside = self.root / "outside"
        generate_wrappers({"skills": [make_record("old")]}, outside)
        self.output.mkdir()
        (self.output / "old").symlink_to(outside / "old", target_is_directory=True)
        for operation in (generate_wrappers, check_wrappers):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(ValueError, "[Uu]nsafe wrapper destination"):
                    operation({"skills": []}, self.output)
                self.assertTrue((outside / "old" / "SKILL.md").is_file())

    def test_cli_refuses_escaping_destinations(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory_path = self.root / "inventory.json"
        record = make_record("../escaped")
        record["path"] = "runtime-skills/science-review"
        for linked in (False, True):
            if linked:
                record["name"] = "linked"
                self.output.mkdir(exist_ok=True)
                (self.output / "linked").symlink_to(self.root / "outside", target_is_directory=True)
            inventory_path.write_text(
                json.dumps({"schema_version": 1, "skills": [record]}), encoding="utf-8"
            )
            for flags in ([], ["--check"]):
                with self.subTest(linked=linked, flags=flags):
                    result = subprocess.run(
                        [
                            sys.executable, str(repository_root / "scripts" / "generate_wrappers.py"),
                            "--inventory", str(inventory_path), "--output", str(self.output), *flags,
                        ],
                        capture_output=True, text=True,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")),
                    )
                    self.assertNotEqual(0, result.returncode)
                    self.assertIn("ValueError", result.stderr)
                    self.assertFalse((self.root / "escaped").exists())
                    self.assertFalse((self.root / "outside").exists())
        (self.root / "real").mkdir()
        (self.root / "alias").symlink_to("real", target_is_directory=True)
        record["name"] = "safe"
        inventory_path.write_text(
            json.dumps({"schema_version": 1, "skills": [record]}), encoding="utf-8"
        )
        for flags in ([], ["--check"]):
            with self.subTest(trusted_alias=True, flags=flags):
                result = subprocess.run(
                    [
                        sys.executable, str(repository_root / "scripts/generate_wrappers.py"),
                        "--inventory", "inventory.json", "--output", "alias/out", *flags,
                    ],
                    cwd=self.root, env=dict(os.environ, PYTHONPATH=str(repository_root / "src")),
                    capture_output=True, text=True,
                    timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "30")),
                )
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual(
                    render_skill_wrapper(record),
                    (self.root / "real/out/safe/SKILL.md").read_text(encoding="utf-8"),
                )


    def test_cli_refuses_malformed_inventory_without_writing(self) -> None:
        from loader_cases import assert_refused, malformed_json, nested_values
        path = self.root / "inventory.json"
        payloads = malformed_json() + [json.dumps({"schema_version": 2, "sources": [], "skills": [value]}).encode() for value in nested_values()]
        record = make_record("demo")
        record["status"] = []
        payloads.append(json.dumps({"schema_version": 2, "skills": [record]}).encode())
        record = make_record("demo")
        record["path"] = "runtime-skills/science-review"
        record["description"] = "\ud800"
        payloads.append(json.dumps({"schema_version": 2, "skills": [record]}).encode())
        for contents in payloads:
            path.write_bytes(contents)
            for flags in ([], ["--check"]):
                with self.subTest(contents=contents, flags=flags):
                    assert_refused(self, "generate_wrappers.py", ["--inventory", path, "--output", self.output, *flags], 1, self.output)
        self.output.mkdir()
        (self.output / "keep").write_bytes(b"preserve")
        for candidate in (path, self.root / "missing.json", self.root):
            for flags in ([], ["--check"]):
                assert_refused(self, "generate_wrappers.py", ["--inventory", candidate, "--output", self.output, *flags], 1, self.output)


class PromotionProvenanceTests(unittest.TestCase):
    def test_cli_preserves_provenance_before_creating_draft_or_receipt(self) -> None:
        script = Path(__file__).resolve().parents[1] / "scripts" / "promote_run_to_skill.py"
        for field in ("code", "executions", "superseded_executions", "journal"):
            for alias in ("direct", "symlink", "hardlink", "case", "scheme"):
                if alias == "scheme" and field not in ("executions", "superseded_executions"):
                    continue
                with self.subTest(field=field, alias=alias), tempfile.TemporaryDirectory() as tempdir:
                    root = Path(tempdir)
                    run = root / "run"
                    run.mkdir()
                    source = run / ("execution-log.jsonl" if field == "journal" else "source.log")
                    content = b'{"id":"E1"}\n' if field == "journal" else b"recorded provenance\n"
                    source.write_bytes(content)
                    manifest = new_manifest("promotion", "Can the workflow be reused?", [])
                    manifest["review"] = {"status": "passed", "findings": []}
                    manifest["code"] = [{"path": value, "sha256": "0" * 64}
                                        for value in ("", "missing.py", "https://example.test/code.py")]
                    digest = hashlib.sha256(content).hexdigest()
                    if field == "code":
                        manifest[field] = [{"path": source.name, "sha256": digest}]
                    else:
                        record = {"id": "E1", "exit_code": 0}
                        if field != "journal":
                            relative = f"unused://../{source.name}" if alias == "scheme" else source.name
                            record.update(log_path=relative, log_sha256=digest)
                        manifest["executions" if field == "journal" else field] = [record]
                    manifest_path = run / "manifest.json"
                    write_manifest(manifest, manifest_path)
                    receipt = source
                    if alias in ("symlink", "hardlink"):
                        receipt = root / "receipt.json"
                        if alias == "symlink":
                            receipt.symlink_to(source)
                        else:
                            os.link(source, receipt)
                    elif alias == "case":
                        receipt = source.with_name(source.name.upper())
                    draft = root / "draft"
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
                    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
                    command = [sys.executable, str(script), str(manifest_path), str(draft),
                               "--name", "fixture-workflow", "--description", "Bounded workflow.", "--receipt"]
                    result = subprocess.run(
                        [*command, str(receipt)], capture_output=True, text=True,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(1, result.returncode, result.stderr)
                    self.assertIn("output path would overwrite input", result.stderr)
                    self.assertEqual("", result.stdout)
                    self.assertFalse(draft.exists())
                    self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()})
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])
                    result = subprocess.run(
                        [*command, str(root / "safe-receipt.json")], capture_output=True, text=True,
                        timeout=float(os.environ.get("OMS_TEST_CALL_TIMEOUT", "120")),
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertTrue((draft / "SKILL.md").is_file())
                    self.assertTrue((root / "safe-receipt.json").is_file())
                    self.assertEqual(content, source.read_bytes())
                    self.assertEqual("passed", review_manifest(manifest, run)["status"])


class SessionContractTests(unittest.TestCase):
    def test_only_core_skills_are_registered_with_the_plugin(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (repository_root / ".codex-plugin" / "plugin.json").read_text()
        )
        registered = {
            path.name
            for path in (repository_root / "skills").iterdir()
            if path.is_dir()
        }

        self.assertEqual(
            {"codex-science", "science-provenance", "science-review"},
            registered,
        )
        self.assertEqual("./skills/", manifest["skills"])
        for name in registered:
            bootstrap = (repository_root / "skills" / name / "SKILL.md").read_text()
            self.assertIn(f"runtime-skills/{name}/SKILL.md", bootstrap)
            self.assertTrue(
                (repository_root / "runtime-skills" / name / "SKILL.md").is_file()
            )

    def test_runtime_skill_names_generic_mcp_script_fallback(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        text = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()

        self.assertIn("scripts/science_tool.py", text)
        self.assertIn("scripts/search_skills.py", text)
        self.assertIn("scripts/plan_life_science_research.py", text)

    def test_every_authored_skill_has_ui_metadata(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        missing = [
            path.name
            for path in sorted((repository_root / "authored-skills").iterdir())
            if (path / "SKILL.md").is_file()
            and not (path / "agents" / "openai.yaml").is_file()
        ]

        self.assertEqual([], missing)

    def test_coordinator_has_narrow_opt_in_and_stays_active_in_its_task(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        skill = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        references = repository_root / "runtime-skills" / "codex-science" / "references"
        activation = (references / "activation-and-updates.md").read_text()
        goal = (references / "goal-loop-contract.md").read_text()
        coordinator_agent = (
            repository_root / "skills" / "codex-science" / "agents" / "openai.yaml"
        ).read_text()

        self.assertIn("references/activation-and-updates.md", skill)
        self.assertIn("references/goal-loop-contract.md", skill)
        self.assertIn("remainder of the current Codex task", activation)
        self.assertIn("session-scoped marker", activation)
        self.assertIn("implicitly invoke `$codex-science`", activation)
        self.assertIn("resume or context compaction", activation)
        self.assertIn("scripts/science_checkpoint.py", skill)
        self.assertIn("completion, a genuine blocker, or an approval gate", skill)
        self.assertIn("Do not ask for non-blocking preferences", skill)
        self.assertIn("batch", skill)
        self.assertIn("Stop guard", goal)
        self.assertIn("heartbeat", skill)
        self.assertIn("native Goal mode", goal)
        self.assertIn("get_goal", goal)
        self.assertIn("--outer-goal native", skill)
        self.assertIn("--outer-goal native", goal)
        self.assertIn("completion_pending", goal)
        self.assertIn("update_goal", goal)
        self.assertIn("confirm-goal-complete", goal)
        self.assertIn("generic Stop-loop", goal)
        self.assertIn("openai/codex#20783", goal)
        self.assertIn("CODEX_SCIENCE_STOP_MODE=block", goal)
        self.assertIn("Codex Science 종료", activation)
        self.assertIn("hookless", skill)
        self.assertIn("catalog/codex-skills/<name>/SKILL.md", skill)
        self.assertIn("<plugin-root>/runtime-skills/<name>/SKILL.md", skill)
        named = set(re.findall(r"\$(science-[a-z-]+|codex-science)\b", skill))
        self.assertTrue({"codex-science", "science-provenance", "science-review"} <= named)
        for name in named:
            self.assertTrue((repository_root / "runtime-skills" / name / "SKILL.md").is_file(), name)
        self.assertIn("Do not activate for an ordinary scientific question", skill)
        self.assertIn(
            "prefer Codex Science MCP tools and `status: active` catalog skills",
            skill,
        )
        catalog_policy = (references / "catalog-policy.md").read_text()
        self.assertIn("Fall back to general-purpose tools", skill)
        self.assertIn("Fall back to general-purpose tools or skills only when", catalog_policy)
        self.assertIn("does not override the activation gate", catalog_policy)
        self.assertIn("never select an inactive skill silently", catalog_policy)
        self.assertIn("allow_implicit_invocation: true", coordinator_agent)
        for name in ("science-provenance", "science-review"):
            agent = (repository_root / "skills" / name / "agents" / "openai.yaml").read_text()
            self.assertIn("allow_implicit_invocation: false", agent)

    def test_plugin_starter_prompts_explicitly_activate_science_mode(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        manifest = json.loads(
            (repository_root / ".codex-plugin" / "plugin.json").read_text()
        )

        prompts = manifest["interface"]["defaultPrompt"]
        self.assertTrue(prompts)
        self.assertTrue(all("Start Codex Science" in prompt for prompt in prompts))

    def test_user_facing_message_contract_is_language_matched_and_indexed(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        skill = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        progress = skill.split("## Human-facing progress", 1)[1].split(
            "## Lane delegation and synthesis", 1
        )[0]
        reference = repository_root / "runtime-skills" / "codex-science" / "references" / "user-facing-messages.md"
        activation_text = (
            repository_root / "runtime-skills" / "codex-science" / "references" / "activation-and-updates.md"
        ).read_text()
        index = json.loads(
            (repository_root / "runtime-skills" / "codex-science" / "references" / "index.json").read_text()
        )
        indexed = {entry["path"]: entry for entry in index["references"]}

        self.assertNotIn("Codex Science is active for this task.", skill)
        self.assertIn("Write in the user's language", progress)
        reference_text = reference.read_text(encoding="utf-8")
        self.assertIn("Do not expose internal tier names", progress)
        self.assertIn("(references/user-facing-messages.md)", progress)
        for phrase in (
            "Do not expose internal tier names",
            "clickable links with readable link text",
            "use absolute paths when the host renders",
            "Local file links alone are not citations",
            "Show primary raster results inline when available",
            "visible persistent identifier (DOI, PMID, PMCID, or arXiv ID)",
            "rests on published sources",
            "link computation-only findings to the saved output",
            "rests on public database or dataset records, name the record identifiers",
        ):
            self.assertIn(phrase, reference_text)
        self.assertIn("in the user's language and plain words only when useful", activation_text)
        self.assertIn(
            "Only say progress is saved in files when a standard or full run record exists",
            activation_text,
        )
        self.assertIn("progress is saved in files", activation_text)
        self.assertIn("quick answer without a run record", activation_text)
        self.assertTrue(reference.is_file())
        self.assertIn("references/user-facing-messages.md", indexed)
        self.assertEqual(
            "repository-contract",
            indexed["references/user-facing-messages.md"]["authority"],
        )
        self.assertEqual("1", indexed["references/user-facing-messages.md"]["version"])
        self.assertTrue(indexed["references/user-facing-messages.md"]["required_before"])
        self.assertTrue(indexed["references/user-facing-messages.md"]["search_patterns"])


class ScientificComputerUseCoverageTests(unittest.TestCase):
    def test_local_and_remote_compute_skills_are_active_and_routed(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {"cx-compute-environment", "cx-remote-scientific-compute"}

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))

        local = (
            repository_root / "authored-skills" / "compute-environment" / "SKILL.md"
        ).read_text()
        for capability in ("Python", "R", "Julia", "Jupyter", "container", "GPU"):
            self.assertIn(capability, local)
        self.assertIn("scripts/compute_probe.py", local)
        self.assertIn("approval packet", local)
        self.assertIn("cancellation", local)
        self.assertIn("two directories above", local)
        for project_marker in ("pyproject.toml", "renv.lock", "Project.toml", "Jupyter kernel"):
            self.assertIn(project_marker, local)

        remote = (
            repository_root
            / "authored-skills"
            / "remote-scientific-compute"
            / "SKILL.md"
        ).read_text()
        for capability in ("SSH", "Slurm", "cloud GPU", "object storage"):
            self.assertIn(capability, remote)
        self.assertIn("login node", remote)
        self.assertIn("explicit approval", remote)
        self.assertIn("Never persist credentials", remote)
        self.assertIn("host fingerprint", remote)
        self.assertIn("monitoring cadence", remote)

        coordinator = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        self.assertIn("$cx-compute-environment", coordinator)
        self.assertIn("$cx-remote-scientific-compute", coordinator)

    def test_readme_documents_human_trust_and_compute_boundaries(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        english = (repository_root / "README.md").read_text()
        korean = (repository_root / "README.ko.md").read_text()

        for text in (english, korean):
            self.assertIn("/hooks", text)
            self.assertIn("Start Codex Science", text)
            self.assertIn("SSH", text)
            self.assertIn("Slurm", text)
            self.assertIn("Julia", text)
            self.assertIn("GPU", text)
            self.assertIn("/goal", text)
            self.assertIn("codex plugin list", text)
            self.assertIn("science_checkpoint.py", text)
            self.assertIn("scripts/install.sh | bash", text)
            self.assertIn("~/.codex-science", text)
        self.assertIn("does **not** run in the background", english)
        self.assertIn("openai/codex#20783", english)
        self.assertIn("CODEX_SCIENCE_STOP_MODE=block", english)
        self.assertIn("Do not register the development checkout", english)
        self.assertIn("백그라운드에서 실행되지", korean)
        self.assertIn("openai/codex#20783", korean)
        self.assertIn("CODEX_SCIENCE_STOP_MODE=block", korean)
        self.assertIn("개발 checkout을 Codex marketplace로 등록하지 마세요", korean)

    def test_readme_documents_safe_update_modes_and_examples(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        for name in ("README.md", "README.ko.md"):
            text = (repository_root / name).read_text()
            self.assertIn("CODEX_SCIENCE_AUTO_UPDATE", text)
            self.assertIn("`apply`", text)
            self.assertIn("`notify`", text)
            self.assertIn("`off`", text)
            self.assertIn("Codex Science 업데이트", text)
            self.assertIn("last-known-good", text)
        self.assertIn("same task", (repository_root / "README.md").read_text())
        self.assertIn("같은 작업", (repository_root / "README.ko.md").read_text())

    def test_provenance_renders_and_surfaces_visual_results(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        provenance = (repository_root / "runtime-skills" / "science-provenance" / "SKILL.md").read_text()

        self.assertIn("render_artifact_index.py", provenance)
        self.assertIn("index.md", provenance)
        self.assertIn("index.html", provenance)
        self.assertIn("absolute local path", provenance)
        self.assertIn("display", provenance)
        self.assertIn("claim evidence", provenance)
        self.assertIn("data-derived", provenance)
        self.assertIn("units", provenance)
        self.assertIn("Do not invent", provenance)


class FeaturedScienceSkillCoverageTests(unittest.TestCase):
    def test_agentic_life_science_skills_are_active_and_composable(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {
            "cx-biomedical-entity-normalization",
            "cx-biomedical-evidence-reconciliation",
            "cx-cancer-genomics-evidence",
            "cx-expression-cell-context",
            "cx-gene-burden-evidence",
            "cx-life-science-research-routing",
            "cx-locus-to-gene-prioritization",
            "cx-metabolomics-proteomics-context",
            "cx-ncbi-integrated-research",
            "cx-phewas-replication-analysis",
            "cx-public-omics-dataset-discovery",
            "cx-translational-pharmacology-evidence",
            "cx-variant-evidence-synthesis",
        }

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))
        for name in expected:
            text = (repository_root / records[name]["path"] / "SKILL.md").read_text().lower()
            self.assertIn("provenance", text)
            self.assertTrue("review" in text or "$science-review" in text)

        coordinator = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        self.assertIn("$cx-life-science-research-routing", coordinator)
        self.assertIn("science_plan_life_science_research", coordinator)

    def test_new_life_science_source_skills_use_bundled_read_only_tools(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        expected = {
            "mygene-search": "science_search_mygene",
            "gwas-catalog-search": "science_search_gwas_catalog",
            "bgee-expression-search": "science_search_bgee",
            "biostudies-search": "science_search_biostudies",
            "cbioportal-search": "science_search_cbioportal",
            "chebi-search": "science_search_chebi",
            "rhea-search": "science_search_rhea",
            "pride-search": "science_search_pride",
            "proteomexchange-search": "science_search_proteomexchange",
            "mgnify-search": "science_search_mgnify",
            "rnacentral-search": "science_search_rnacentral",
            "ncbi-gene-search": "science_search_ncbi_gene",
        }

        for folder, tool in expected.items():
            text = (repository_root / "authored-skills" / folder / "SKILL.md").read_text()
            self.assertIn(tool, text)
            self.assertIn("$science-provenance", text)

    def test_analytical_chemistry_skills_are_active_sourced_and_composable(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {
            "cx-spectroscopy-spectral-inference",
            "cx-nmr-structure-analysis",
            "cx-mass-spectrometry-identification",
            "cx-xray-diffraction-scattering",
            "cx-chromatography-quantification",
            "cx-chemical-structure-elucidation",
        }

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))
        for name in expected:
            source = repository_root / records[name]["path"] / "SKILL.md"
            text = source.read_text(encoding="utf-8").lower()
            self.assertIn("source basis", text)
            self.assertIn("verify", text)
            self.assertIn("$cx-experimental-uncertainty-propagation", text)

        spectroscopy = repository_root / "authored-skills" / "spectroscopy-spectral-inference"
        self.assertTrue((spectroscopy / "references" / "modalities.md").is_file())
        mass_spec = (repository_root / records["cx-mass-spectrometry-identification"]["path"] / "SKILL.md").read_text()
        self.assertIn("$kdense-matchms", mass_spec)
        self.assertIn("$kdense-pyopenms", mass_spec)
        diffraction = (repository_root / records["cx-xray-diffraction-scattering"]["path"] / "SKILL.md").read_text()
        self.assertIn("$kdense-pymatgen", diffraction)

        sources = (repository_root / "docs" / "ANALYTICAL_SOURCES.md").read_text()
        for name in expected:
            self.assertIn(name.removeprefix("cx-"), sources)

        coordinator = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        routing = (repository_root / "runtime-skills" / "codex-science" / "references" / "routing.md").read_text()
        self.assertIn("experimental spectrum or analytical chemistry dataset", coordinator)
        self.assertIn("$cx-chemical-structure-elucidation", coordinator)
        self.assertIn("experimental spectrum or analytical chemistry dataset", routing)
        self.assertIn("$cx-chemical-structure-elucidation", routing)

    def test_extended_math_physics_skills_are_active_and_sourced(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {
            "cx-probability-stochastic-processes",
            "cx-statistical-inference-experimental-design",
            "cx-optimization-variational-methods",
            "cx-asymptotic-perturbation-methods",
            "cx-complex-fourier-analysis",
            "cx-experimental-uncertainty-propagation",
            "cx-continuum-mechanics",
            "cx-relativity-spacetime",
            "cx-computational-physics-validation",
            "cx-control-dynamical-systems",
            "cx-geometry-topology",
            "cx-formal-theorem-proving",
            "cx-optics-wave-physics",
            "cx-condensed-matter-solid-state",
            "cx-nuclear-particle-physics",
            "cx-inverse-problems-regularization",
            "cx-chaos-nonlinear-dynamics",
            "cx-tensor-calculus-differential-geometry",
        }

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))
        for name in expected:
            source = repository_root / records[name]["path"] / "SKILL.md"
            text = source.read_text(encoding="utf-8").lower()
            self.assertIn("source basis", text)
            self.assertIn("verify", text)

        sources = (repository_root / "docs" / "TEXTBOOK_SOURCES.md").read_text()
        self.assertIn("probability-stochastic-processes", sources)
        self.assertIn("tensor-calculus-differential-geometry", sources)

    def test_authored_skill_markdown_links_resolve_inside_repository(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        offenders = authored_markdown_link_offenders(repository_root)

        self.assertFalse(offenders, "Broken or escaping authored-skill links:\n" + "\n".join(offenders))

    def test_authored_markdown_link_checker_reports_broken_and_escaping_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repository_root = Path(tempdir)
            skill_dir = repository_root / "authored-skills" / "sample"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "[missing](references/missing.md) [escape](../../../outside.md) "
                "[external](https://example.com) [anchor](#section)\n",
                encoding="utf-8",
            )

            offenders = authored_markdown_link_offenders(repository_root)

        self.assertEqual(
            [
                "authored-skills/sample/SKILL.md: references/missing.md",
                "authored-skills/sample/SKILL.md: ../../../outside.md",
            ],
            offenders,
        )

    def test_textbook_grounded_math_physics_skills_are_active_and_routed(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {
            "cx-mathematical-problem-execution",
            "cx-proof-and-counterexample",
            "cx-linear-algebra-problem-solving",
            "cx-ode-pde-solving",
            "cx-numerical-analysis-error-control",
            "cx-dimensional-analysis-units",
            "cx-classical-mechanics",
            "cx-electromagnetism",
            "cx-thermodynamics-statistical-mechanics",
            "cx-quantum-mechanics",
        }

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))
        for name in expected:
            source = repository_root / records[name]["path"] / "SKILL.md"
            self.assertIn("source basis", source.read_text(encoding="utf-8").lower())

        coordinator = (repository_root / "runtime-skills" / "codex-science" / "SKILL.md").read_text()
        self.assertIn("$cx-mathematical-problem-execution", coordinator)
        routing = (repository_root / "runtime-skills" / "codex-science" / "references" / "routing.md").read_text()
        self.assertIn("concrete mathematics or physics problem", routing)
        self.assertIn("$cx-mathematical-problem-execution", routing)
        self.assertIn(".cache/textbooks/", (repository_root / ".gitignore").read_text())

    def test_claude_featured_model_workflows_have_active_native_skills(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        inventory = json.loads((repository_root / "catalog" / "inventory.json").read_text())
        records = {item["name"]: item for item in inventory["skills"]}
        expected = {
            "cx-alphafold3-structure-prediction",
            "cx-alphafold2-structure-prediction",
            "cx-bindcraft-binder-design",
            "cx-borzoi-regulatory-prediction",
            "cx-chai1-structure-prediction",
            "cx-esm2-protein-embeddings",
            "cx-esmc-protein-modeling",
            "cx-esmfold-structure-prediction",
            "cx-esmfold2-structure-prediction",
            "cx-evo2-genome-modeling",
            "cx-indication-dossier",
            "cx-modeling-problem-execution",
            "cx-openfold3-structure-prediction",
            "cx-protenix-structure-prediction",
            "cx-proteinmpnn-sequence-design",
            "cx-rfdiffusion-protein-design",
            "cx-rosettafold-all-atom",
            "cx-scgpt-single-cell",
            "cx-scvi-tools-analysis",
            "cx-simplefold-structure-prediction",
        }

        self.assertTrue(expected <= records.keys())
        self.assertTrue(all(records[name]["status"] == "active" for name in expected))

    def test_new_compute_skills_keep_execution_and_provenance_gates(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        compute_skills = (
            "alphafold2-structure-prediction",
            "alphafold3-structure-prediction",
            "bindcraft-binder-design",
            "borzoi-regulatory-prediction",
            "chai1-structure-prediction",
            "esm2-protein-embeddings",
            "esmc-protein-modeling",
            "esmfold-structure-prediction",
            "esmfold2-structure-prediction",
            "evo2-genome-modeling",
            "openfold3-structure-prediction",
            "protenix-structure-prediction",
            "proteinmpnn-sequence-design",
            "rfdiffusion-protein-design",
            "rosettafold-all-atom",
            "scgpt-single-cell",
            "scvi-tools-analysis",
            "simplefold-structure-prediction",
        )

        for name in compute_skills:
            with self.subTest(name=name):
                text = (repository_root / "authored-skills" / name / "SKILL.md").read_text().lower()
                self.assertIn("ask once", text)
                self.assertIn("pin", text)
                self.assertIn("artifacts/<run-id>/", text)
                self.assertIn("$science-provenance", text)

    def test_scvi_skill_protects_treatment_from_batch_correction(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        text = (
            repository_root / "authored-skills" / "scvi-tools-analysis" / "SKILL.md"
        ).read_text().lower()

        self.assertIn("confounded", text)
        self.assertIn("nuisance covariate", text)

    def test_concrete_modeling_problem_continues_to_reviewed_execution(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        runner = (
            repository_root / "authored-skills" / "modeling-problem-execution" / "SKILL.md"
        ).read_text().lower()
        coordinator = (
            repository_root / "runtime-skills" / "codex-science" / "SKILL.md"
        ).read_text().lower()

        for marker in (
            "concrete problem",
            "smallest falsifying",
            "ask once",
            "continue through execution",
            "retry",
            "downstream",
            "artifacts/<run-id>/",
            "$science-review",
        ):
            self.assertIn(marker, runner)
        self.assertIn("$cx-modeling-problem-execution", coordinator)
        self.assertIn("concrete modeling", coordinator)

    def test_execution_runner_chains_docking_without_affinity_overclaim(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        runner = (
            repository_root / "authored-skills" / "modeling-problem-execution" / "SKILL.md"
        ).read_text().lower()

        for marker in (
            "$cx-molecular-input-preparation",
            "$cx-docking-validation",
            "$cx-plip-interaction-analysis",
            "intended bound ligand",
            "highest-priority predicted",
            "exploratory",
        ):
            self.assertIn(marker, runner)

    def test_esmfold2_has_authoritative_runtime_and_downstream_contract(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        text = (
            repository_root / "authored-skills" / "esmfold2-structure-prediction" / "SKILL.md"
        ).read_text().lower()

        for marker in (
            "https://github.com/biohub/esm",
            "biohub/esmfold2",
            "mg",
            "$cx-pymol-visualize",
            "$cx-plip-interaction-analysis",
            "$cx-protenix-structure-prediction",
        ):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
