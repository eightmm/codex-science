import json
import tempfile
import unittest
from pathlib import Path

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
) -> dict[str, object]:
    return {
        "name": name,
        "description": f"Use {name} for a scientific workflow.",
        "license": "MIT",
        "path": f"vendor/scientific-agent-skills/skills/{name}",
        "status": status,
        "reasons": reasons or [],
    }


class WrapperRenderingTests(unittest.TestCase):
    def test_active_wrapper_points_to_pinned_source(self) -> None:
        wrapper = render_skill_wrapper(make_record("sympy"))

        self.assertIn("name: sympy", wrapper)
        self.assertIn("Status: `active`", wrapper)
        self.assertIn("../../../vendor/scientific-agent-skills/skills/sympy/SKILL.md", wrapper)
        self.assertIn("../../inventory.json", wrapper)
        self.assertIn("$science-provenance", wrapper)

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


class SessionContractTests(unittest.TestCase):
    def test_only_core_skills_are_registered_with_the_plugin(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        registered = {
            path.name
            for path in (repository_root / "skills").iterdir()
            if path.is_dir()
        }

        self.assertEqual(
            {"codex-science", "science-provenance", "science-review"},
            registered,
        )

    def test_coordinator_has_narrow_opt_in_and_stays_active_in_its_task(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        skill = (repository_root / "skills" / "codex-science" / "SKILL.md").read_text()
        coordinator_agent = (
            repository_root / "skills" / "codex-science" / "agents" / "openai.yaml"
        ).read_text()

        self.assertIn("remainder of the current Codex task", skill)
        self.assertIn("Do not write activation state to the project", skill)
        self.assertIn("Codex Science 종료", skill)
        self.assertIn("catalog/codex-skills/<name>/SKILL.md", skill)
        self.assertIn("Do not activate for an ordinary scientific question", skill)
        self.assertIn("allow_implicit_invocation: true", coordinator_agent)
        for name in ("science-provenance", "science-review"):
            agent = (repository_root / "skills" / name / "agents" / "openai.yaml").read_text()
            self.assertIn("allow_implicit_invocation: false", agent)


if __name__ == "__main__":
    unittest.main()
