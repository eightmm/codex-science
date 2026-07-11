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
        skill = (repository_root / "skills" / "codex-science" / "SKILL.md").read_text()
        coordinator_agent = (
            repository_root / "skills" / "codex-science" / "agents" / "openai.yaml"
        ).read_text()

        self.assertIn("remainder of the current Codex task", skill)
        self.assertIn("session-scoped marker", skill)
        self.assertIn("implicitly invoke `$codex-science`", skill)
        self.assertIn("resume or context compaction", skill)
        self.assertIn("Codex Science 종료", skill)
        self.assertIn("catalog/codex-skills/<name>/SKILL.md", skill)
        self.assertIn("Do not activate for an ordinary scientific question", skill)
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

        coordinator = (repository_root / "skills" / "codex-science" / "SKILL.md").read_text()
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


class FeaturedScienceSkillCoverageTests(unittest.TestCase):
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

        coordinator = (repository_root / "skills" / "codex-science" / "SKILL.md").read_text()
        self.assertIn("experimental spectrum or analytical chemistry dataset", coordinator)
        self.assertIn("$cx-chemical-structure-elucidation", coordinator)

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

        coordinator = (repository_root / "skills" / "codex-science" / "SKILL.md").read_text()
        self.assertIn("$cx-mathematical-problem-execution", coordinator)
        self.assertIn("concrete mathematics or physics problem", coordinator)
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
            repository_root / "skills" / "codex-science" / "SKILL.md"
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
