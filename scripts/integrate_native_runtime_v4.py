#!/usr/bin/env python3
"""One-time idempotent integration for native runtime v4 source additions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def update_reference_index(path: Path, entry: dict[str, Any]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"reference index must be an object: {path}")
    key = "references" if "references" in payload else "entries" if "entries" in payload else "references"
    entries = payload.setdefault(key, [])
    if not isinstance(entries, list):
        raise SystemExit(f"reference index {key} must be a list: {path}")
    existing = next((item for item in entries if isinstance(item, dict) and item.get("id") == entry["id"]), None)
    if existing is None:
        entries.append(entry)
    elif existing != entry:
        existing.clear()
        existing.update(entry)
    entries.sort(key=lambda item: str(item.get("id", "")) if isinstance(item, dict) else "")
    write_json(path, payload)


def add_reference_paragraph(path: Path, marker: str, paragraph: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    heading = "## Reference usage"
    if heading in text:
        start = text.index(heading) + len(heading)
        next_heading = text.find("\n## ", start)
        if next_heading < 0:
            text = text.rstrip() + "\n\n" + paragraph + "\n"
        else:
            text = text[:next_heading].rstrip() + "\n\n" + paragraph + "\n" + text[next_heading:]
    else:
        anchor = "## Workflow"
        if anchor not in text:
            raise SystemExit(f"cannot find reference insertion point: {path}")
        text = text.replace(anchor, f"## Reference usage\n\n{paragraph}\n\n{anchor}", 1)
    path.write_text(text, encoding="utf-8")


def append_once(path: Path, marker: str, content: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"missing {label} marker in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_reference_indexes_and_skills() -> None:
    update_reference_index(
        ROOT / "skills" / "science-provenance" / "references" / "index.json",
        {
            "id": "artifact-runtime",
            "path": "references/artifact-runtime.md",
            "purpose": "Bounded native views, hash-bound selections, and non-executing transform proposals for scientific artifacts.",
            "read_when": [
                "before rendering a scientific artifact",
                "before creating an atom, residue, locus, cell, table, graph, figure, or trajectory selection",
                "before converting an annotation into a proposed edit or rerun"
            ],
            "required_before": [
                "calling scripts/render_artifact_runtime.py",
                "recording artifact-runtime-descriptor, artifact-selection, or transform-proposal sidecars"
            ],
            "search_patterns": [
                "### Describe an artifact",
                "### Create a typed selection",
                "### Propose a transform",
                "## Failure handling",
                "## Common mistakes"
            ],
            "authority": "Codex Science first-party runtime contract",
            "version": "1",
            "evidence_boundary": "A bounded runtime view improves inspection but does not validate a scientific interpretation or execute a transform."
        },
    )
    add_reference_paragraph(
        ROOT / "skills" / "science-provenance" / "SKILL.md",
        "references/artifact-runtime.md",
        "Before rendering, selecting, or proposing a change to a structure, molecule, genome track, single-cell object, table, figure, evidence graph, trajectory, or large dataset, **MUST** read [the native artifact runtime contract](references/artifact-runtime.md). Generate a hash-bound descriptor and typed selection before any transform proposal; never mutate artifact bytes from a visual annotation alone.",
    )

    update_reference_index(
        ROOT / "skills" / "codex-science" / "references" / "index.json",
        {
            "id": "project-evidence-store",
            "path": "references/project-evidence-store.md",
            "purpose": "Project-level immutable run imports, evidence assertions, hypothesis forks, comparisons, and non-executing merge plans.",
            "read_when": [
                "before importing more than one run into a project",
                "before creating a hypothesis or experiment branch",
                "before recording a quantitative evidence assertion",
                "before comparing or merging scientific branches"
            ],
            "required_before": [
                "calling scripts/science_project.py",
                "treating project-level state as scientific lineage"
            ],
            "search_patterns": [
                "## Import a reviewed run",
                "## Fork a hypothesis branch",
                "## Add a quantitative evidence assertion",
                "## Prepare a merge plan",
                "## Failure handling"
            ],
            "authority": "Codex Science first-party project lineage contract",
            "version": "1",
            "evidence_boundary": "The project store indexes immutable runs and decisions; it does not replace manifests, evidence, or independent review."
        },
    )
    add_reference_paragraph(
        ROOT / "skills" / "codex-science" / "SKILL.md",
        "references/project-evidence-store.md",
        "For a multi-run research program, hypothesis fork, quantitative evidence assertion, or branch comparison, **MUST** read [the project evidence store contract](references/project-evidence-store.md) before calling `scripts/science_project.py`. Imported manifests and artifact hashes remain authoritative; merge plans are non-executing and always require a new scientific synthesis and review.",
    )

    update_reference_index(
        ROOT / "authored-skills" / "remote-scientific-compute" / "references" / "index.json",
        {
            "id": "job-runtime",
            "path": "references/job-runtime.md",
            "purpose": "Durable local and Slurm job specs, approvals, submission, status, cancellation, checkpoint, and output collection receipts.",
            "read_when": [
                "before constructing a durable job spec",
                "before submitting, polling, cancelling, or collecting a local or Slurm job",
                "before approving a non-local resource allocation"
            ],
            "required_before": [
                "calling scripts/science_job.py",
                "submitting work through LocalBackend or SlurmBackend"
            ],
            "search_patterns": [
                "## Job spec",
                "## Local execution",
                "## Approval receipt",
                "## Slurm execution",
                "## Checkpoint and resume",
                "## Failure handling"
            ],
            "authority": "Codex Science first-party compute runtime contract",
            "version": "1",
            "evidence_boundary": "A job receipt proves execution state and collected hashes, not scientific success."
        },
    )
    add_reference_paragraph(
        ROOT / "authored-skills" / "remote-scientific-compute" / "SKILL.md",
        "references/job-runtime.md",
        "Before constructing, approving, submitting, polling, cancelling, or collecting a durable local or Slurm job, **MUST** read [the job runtime contract](references/job-runtime.md). Use argv lists, exact resource and timeout caps, hash-bound approvals for Slurm, and terminal output receipts; a zero exit code is not scientific acceptance.",
    )


def patch_source_bugs() -> None:
    replace_once(
        ROOT / "src" / "codex_science" / "artifact_runtime.py",
        "    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material), warnings=tuple(warnings))\n",
        "    material[\"warnings\"] = tuple(warnings)\n    return ArtifactRuntimeDescriptor(**material, fingerprint=_fingerprint(material))\n",
        "artifact runtime warning tuple",
    )
    project_cli = ROOT / "scripts" / "science_project.py"
    text = project_cli.read_text(encoding="utf-8")
    if "import sqlite3\n" not in text:
        text = text.replace("import json\n", "import json\nimport sqlite3\n", 1)
    text = text.replace(
        "    except (OSError, ValueError, sqlite3.Error if False else ValueError) as error:  # type: ignore[misc]\n",
        "    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:\n",
    )
    project_cli.write_text(text, encoding="utf-8")
    maturity = ROOT / "src" / "codex_science" / "skill_maturity.py"
    text = maturity.read_text(encoding="utf-8")
    text = text.replace(
        '    entries = payload.get("references")\n',
        '    entries = payload.get("references", payload.get("entries"))\n',
    )
    maturity.write_text(text, encoding="utf-8")


def patch_advanced_sidecars() -> None:
    path = ROOT / "src" / "codex_science" / "advanced_sidecars.py"
    append_once(
        path,
        "# Native artifact runtime sidecar extension v1",
        r'''
# Native artifact runtime sidecar extension v1
from codex_science.artifact_runtime import (
    stale_selection as _runtime_stale_selection,
    validate_runtime_descriptor as _validate_runtime_descriptor,
    validate_selection as _validate_runtime_selection,
    validate_transform_proposal as _validate_transform_proposal,
)

_base_validate_advanced_sidecars = validate_advanced_sidecars
_base_review_advanced_sidecars = review_advanced_sidecars


def validate_advanced_sidecars(
    manifest: dict[str, Any],
    run_dir: Path,
    verified: dict[str, Path],
    *,
    base_sidecars: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _base_validate_advanced_sidecars(
        manifest, run_dir, verified, base_sidecars=base_sidecars
    )
    result.setdefault("runtime_descriptors", [])
    result.setdefault("artifact_selections", [])
    result.setdefault("transform_proposals", [])
    result.setdefault("runtime_descriptor_stale", [])
    result.setdefault("runtime_paths", {})
    artifact_hashes = result.get("artifact_hashes", {})
    selections_by_id: dict[str, dict[str, Any]] = {}
    pending_proposals: list[dict[str, Any]] = []
    for record in manifest.get("artifacts", []):
        kind = str(record.get("kind", ""))
        relative = str(record.get("path", ""))
        if kind not in {
            "artifact-runtime-descriptor",
            "artifact-selection",
            "transform-proposal",
        }:
            continue
        payload = _load(verified[relative], kind)
        result["runtime_paths"].setdefault(kind, []).append(relative)
        if kind == "artifact-runtime-descriptor":
            _validate_runtime_descriptor(payload)
            if artifact_hashes.get(str(payload["artifact_path"])) != str(
                payload["artifact_sha256"]
            ).lower():
                result["runtime_descriptor_stale"].append(payload)
            result["runtime_descriptors"].append(payload)
        elif kind == "artifact-selection":
            _validate_runtime_selection(payload)
            selection = _runtime_stale_selection(payload, artifact_hashes)
            result["artifact_selections"].append(selection)
            selections_by_id[str(selection["selection_id"])] = selection
        else:
            pending_proposals.append(payload)
    for proposal in pending_proposals:
        selection = selections_by_id.get(str(proposal.get("selection_id", "")))
        _validate_transform_proposal(proposal, selection)
        result["transform_proposals"].append(proposal)
    return result


def review_advanced_sidecars(
    sidecars: dict[str, Any], *, registry_path: Path | None = None
) -> list[dict[str, str]]:
    findings = list(
        _base_review_advanced_sidecars(sidecars, registry_path=registry_path)
    )
    for descriptor in sidecars.get("runtime_descriptor_stale", []):
        findings.append(
            {
                "code": "stale-runtime-descriptor",
                "severity": "minor",
                "message": (
                    "Artifact runtime descriptor covers changed or missing bytes: "
                    f"{descriptor.get('artifact_path', '<unknown>')}"
                ),
            }
        )
    for selection in sidecars.get("artifact_selections", []):
        if selection.get("status") == "stale-anchor":
            findings.append(
                {
                    "code": "stale-artifact-selection",
                    "severity": "minor",
                    "message": (
                        f"Artifact selection {selection.get('selection_id')} points to "
                        "changed or missing bytes."
                    ),
                }
            )
    selection_ids = {
        str(item.get("selection_id"))
        for item in sidecars.get("artifact_selections", [])
    }
    for proposal in sidecars.get("transform_proposals", []):
        if str(proposal.get("selection_id")) not in selection_ids:
            findings.append(
                {
                    "code": "missing-transform-selection",
                    "severity": "major",
                    "message": (
                        f"Transform proposal {proposal.get('proposal_id')} references "
                        "a selection not present in the bundle."
                    ),
                }
            )
    unique = {
        (item["code"], item.get("claim_id", ""), item["message"]): item
        for item in findings
    }
    return sorted(
        unique.values(),
        key=lambda item: (
            item.get("severity", ""),
            item["code"],
            item.get("claim_id", ""),
            item["message"],
        ),
    )
''',
    )


def patch_validation_gates() -> None:
    check = ROOT / "scripts" / "check.sh"
    text = check.read_text(encoding="utf-8")
    command = "  uv run python scripts/audit_native_skill_maturity.py --require-clean\n"
    if command not in text:
        marker = "  uv run python scripts/audit_skill_references.py --require-clean\n"
        if marker in text:
            text = text.replace(marker, marker + command, 1)
        else:
            echo = '  echo "scientific contracts: ok"\n'
            if echo not in text:
                raise SystemExit("cannot locate scientific contract gate in check.sh")
            text = text.replace(echo, command + echo, 1)
    check.write_text(text, encoding="utf-8")

    candidate = ROOT / "scripts" / "candidate_contract_check.py"
    text = candidate.read_text(encoding="utf-8")
    needle = 'run([python, "scripts/audit_native_skill_maturity.py", "--require-clean"], cwd=root)'
    if needle not in text:
        marker = 'run([python, "scripts/audit_skill_references.py", "--require-clean"], cwd=root)'
        if marker in text:
            text = text.replace(marker, marker + "\n    " + needle, 1)
        else:
            marker = 'run([python, "scripts/generate_wrappers.py", "--check"], cwd=root)'
            if marker not in text:
                raise SystemExit("cannot locate candidate reference/wrapper gate")
            text = text.replace(marker, marker + "\n        " + needle, 1)
    candidate.write_text(text, encoding="utf-8")


def patch_docs() -> None:
    append_once(
        ROOT / "docs" / "PLATFORM_CONTRACTS.md",
        "## Native artifact runtime and project evidence memory",
        '''
## Native artifact runtime and project evidence memory

Codex Science separates bounded artifact views, typed selections, and non-executing transform proposals. Read `skills/science-provenance/references/artifact-runtime.md` before using `scripts/render_artifact_runtime.py`. Runtime descriptors and selections are bound to the manifest artifact SHA-256; changed bytes make them stale.

Multi-run programs use `scripts/science_project.py` and the contract in `skills/codex-science/references/project-evidence-store.md`. The SQLite database indexes immutable run manifests, branch lineage, quantitative evidence assertions, comparisons, and merge plans. Run bundles remain authoritative and merge plans never combine bytes automatically.

## Durable compute runtime

`scripts/science_job.py` implements a durable local backend and an approval-gated Slurm backend. Read `authored-skills/remote-scientific-compute/references/job-runtime.md` before constructing or submitting a job. Job state, logs, cancellation, checkpoints, and output hashes are operational provenance; process success is not scientific acceptance.

## Native skill maturity

`scripts/audit_native_skill_maturity.py --require-clean` audits first-party skills against `catalog/native-skill-policy.json`. L3 requires the full decision contract, progressive reference index, and machine-readable output declarations. L4 additionally requires checked-in acceptance fixtures, seeded failure classes, and test files. A declared level above the computed level is a blocking policy finding.
''',
    )
    append_once(
        ROOT / "docs" / "NATIVE_SKILL_STANDARD.md",
        "## Machine-readable maturity declarations",
        '''
## Machine-readable maturity declarations

A decision-bearing first-party skill may include `quality.json` beside `SKILL.md`:

```json
{
  "schema_version": 1,
  "skill": "example-skill",
  "roles": ["executor", "reviewer"],
  "declared_maturity": "L4",
  "output_schemas": ["example-result-v1"],
  "acceptance_fixtures": ["examples/example/input.json"],
  "seeded_failures": ["wrong-unit"],
  "test_files": ["tests/test_example.py"],
  "limitations": ["Fixture-only validation."]
}
```

The repository policy is `catalog/native-skill-policy.json`; the deterministic auditor is `scripts/audit_native_skill_maturity.py`. Declarations do not grant maturity. The auditor computes maturity from the actual instruction contract, progressive references, declared outputs, existing fixtures, seeded failures, and tests.
''',
    )
    append_once(
        ROOT / "skills" / "science-provenance" / "references" / "artifact-contract.md",
        "### Runtime collaboration sidecars",
        '''
### Runtime collaboration sidecars

- `artifact-runtime-descriptor`: bounded native view bound to source artifact path and SHA-256;
- `artifact-selection`: typed atom, residue, locus, cell, table, figure, graph, frame, text, or byte selection bound to artifact SHA-256;
- `transform-proposal`: non-executing operation, parameters, affected steps, expected outputs, and approval boundary bound to a selection.

Changed source bytes make descriptors and selections stale. A proposal never authorizes or executes a mutation and cannot be used as evidence that a rerun occurred.
''',
    )


def main() -> int:
    patch_reference_indexes_and_skills()
    patch_source_bugs()
    patch_advanced_sidecars()
    patch_validation_gates()
    patch_docs()
    print("native runtime v4 integration: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
