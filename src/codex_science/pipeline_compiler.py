"""Promote a passed scientific run into a reviewable skill draft.

The compiler creates a draft only. It never modifies the audited catalog,
activates a skill, copies private inputs, or claims that one successful run is a
validated reusable method.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from codex_science.artifact_store import stream_sha256
from codex_science.artifacts import validate_bundle
from codex_science.review import review_manifest


SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text(value: Any, label: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _artifact_summary(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "path": str(item.get("path", "")),
            "kind": str(item.get("kind", "artifact")),
            "sha256": str(item.get("sha256", "")),
            "artifact_type": str(item.get("artifact_type", "file")),
        }
        for item in manifest.get("artifacts", [])
        if isinstance(item, Mapping)
    ]


def _schema_inputs(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "input.schema.json",
        "title": "Reusable scientific pipeline input",
        "type": "object",
        "properties": {
            "question": {"type": "string", "minLength": 1},
            "parameters": {"type": "object", "additionalProperties": True},
            "inputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "path": {"type": "string"},
                        "identifier": {"type": "string"},
                        "sha256": {"type": "string", "pattern": "^[0-9a-fA-F]{64}$"},
                        "source": {"type": "string"},
                        "release": {"type": "string"}
                    },
                    "required": ["id"],
                    "anyOf": [{"required": ["path"]}, {"required": ["identifier"]}],
                    "additionalProperties": True
                }
            },
            "acceptance": {
                "type": "object",
                "properties": {
                    "criteria": {"type": "array", "items": {"type": "object"}},
                    "review_required": {"const": True}
                },
                "required": ["criteria", "review_required"],
                "additionalProperties": False
            }
        },
        "required": ["question", "parameters", "inputs", "acceptance"],
        "additionalProperties": False,
        "x-source-run-inputs": list(manifest.get("inputs", []))
    }


def _schema_outputs() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "output.schema.json",
        "title": "Reusable scientific pipeline output",
        "type": "object",
        "properties": {
            "run_id": {"type": "string", "minLength": 1},
            "manifest_path": {"type": "string", "minLength": 1},
            "manifest_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "claims": {"type": "array", "items": {"type": "object"}},
            "artifacts": {"type": "array", "items": {"type": "object"}},
            "review": {
                "type": "object",
                "properties": {"status": {"const": "passed"}},
                "required": ["status"],
                "additionalProperties": True
            },
            "limitations": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["run_id", "manifest_path", "manifest_sha256", "claims", "artifacts", "review", "limitations"],
        "additionalProperties": False
    }


def _skill_text(name: str, description: str, source_run: str, workflow_steps: list[dict[str, Any]]) -> str:
    step_lines = []
    for index, step in enumerate(workflow_steps, 1):
        step_id = str(step.get("id", f"step-{index}"))
        detail = str(step.get("description", step_id)).strip()
        step_lines.append(f"{index}. `{step_id}` — {detail}")
    steps = "\n".join(step_lines) or "1. Reconstruct the approved workflow from a new decision contract."
    return f'''---
name: {name}
description: "{description.replace('"', "'")}"
---

# {name}

> Draft generated from reviewed run `{source_run}`. It is not active, cataloged, or validated for new inputs until its fixtures, seeded failures, environment, and independent review pass.

## Decision contract

Record the new question, intended decision, population or system, input identities and hashes, parameter boundaries, primary acceptance criteria, uncertainty rule, non-goals, model/source revisions, cost and approval boundaries, and what would falsify each material claim. Do not inherit the source run's conclusion.

## Reference usage

Before executing, **MUST** read [the generated pipeline contract](references/pipeline.md). Do not guess commands, input fields, environment, or output semantics from this summary. The source run is precedent for structure only, not evidence for a new run.

## Workflow

{steps}

Create a new run ID, initialize provenance, execute only after required approvals, preserve failed attempts and null results, and run `$science-review` against the new artifacts. Use `$science-provenance` for every command, environment, input, output, claim, and receipt.

## Outputs

Return a new hash-validated artifact manifest satisfying `output.schema.json`, with explicit claims, uncertainty, limitations, model/source revisions, execution logs, and an independent review receipt when independence is available. Never return the source run as the new output.

## Boundaries

- Do not activate or catalog this draft automatically.
- Do not copy private, sensitive, proprietary, or credential-bearing source inputs into the draft.
- Do not assume the source environment, model, database, or endpoint is still available.
- Do not reuse a source review receipt for changed inputs or code.
- Do not claim generalization from one successful run.
- Do not execute destructive, remote, paid, or write-capable operations without the normal approval gate.
'''


def _reference_text(
    *,
    name: str,
    source_manifest_path: Path,
    source_manifest_sha256: str,
    manifest: Mapping[str, Any],
    command_contract: list[list[str]],
    limitations: list[str],
) -> str:
    commands = "\n".join(f"- `{json.dumps(command, ensure_ascii=False)}`" for command in command_contract) or "- No command was promoted. Reconstruct commands from an approved method before validation."
    steps = "\n".join(
        f"- `{step.get('id', '<unknown>')}` — {step.get('description', step.get('id', ''))}"
        for step in manifest.get("plan", [])
        if isinstance(step, Mapping)
    ) or "- No source plan steps were recorded."
    limitations_text = "\n".join(f"- {item}" for item in limitations)
    return f'''# Generated pipeline contract

This reference was generated from a reviewed run and is a **draft implementation contract**, not scientific evidence and not an activation decision.

## Source record

- source run: `{manifest.get('run_id')}`
- source manifest: `{source_manifest_path}`
- source manifest SHA-256: `{source_manifest_sha256}`
- source review status: `{manifest.get('review', {{}}).get('status', 'unknown')}`
- generated skill: `{name}`

The source manifest path may be local-machine-specific. The SHA-256 is the stable identity. Never use this reference to bypass source bundle validation.

## Inputs

Use `input.schema.json`. Each new input needs an ID plus either a local path or canonical external identifier. Record a checksum when practical, source/release for external data, and all transformations. Do not reuse source paths blindly.

## Environment

Reconstruct and review the runtime, lockfile/container, code revision, model and weight revisions, databases, hardware, seed, determinism settings, and material non-secret environment variables. The source environment was:

```json
{json.dumps(manifest.get('environment', {{}}), indent=2, sort_keys=True, ensure_ascii=False)}
```

## Source workflow shape

{steps}

## Command contract

Commands are represented as argv arrays. They are not executed by reading this file.

{commands}

Before using a promoted command:

1. resolve every executable and file path;
2. replace source-run paths with new run inputs;
3. pin or record model, database, and code revisions;
4. run the smallest smoke test;
5. verify exit status and output schema;
6. preserve logs and failures;
7. evaluate scientific acceptance separately from process success.

## Output contract

Use `output.schema.json`. The new run must contain a different run ID and manifest hash, current claims and limitations, current artifact hashes, and a current passed review. A process receipt alone is not an output contract.

## Validation and promotion

The generated draft starts below active maturity. To promote it:

1. add a redistributable acceptance fixture;
2. seed material failure cases;
3. add deterministic tests;
4. record exact source/model/database drift behavior;
5. run independent review;
6. add `quality.json` with an honest maturity declaration;
7. pass the repository skill, reference, inventory, wrapper, and contract gates;
8. activate it only through normal catalog policy.

## Failure handling

| Failure | Required response |
| --- | --- |
| source manifest changed | stop; restore or identify the reviewed source bytes |
| command contains unavailable paths | revise the draft and test in the approved environment |
| model/database revision unavailable | select a reviewed replacement and create a new acceptance result |
| output schema mismatch | keep the failed run and correct code/schema before retry |
| source result does not reproduce | report non-reproduction; do not lower the threshold post hoc |
| private input referenced | replace it with an approved immutable reference or remove the dependency |
| new operation requires approval | stop at the approval gate |

## Common mistakes

- Treating a generated draft as active.
- Copying a source conclusion into the new question.
- Reusing source review receipts.
- Reconstructing commands from prose while ignoring argv and environment details.
- Omitting failed source steps because the final run passed.
- Claiming generalization from a single fixture.

## Known limitations

{limitations_text}

## Evidence boundary

This reference preserves workflow shape and explicit source lineage. It does not validate new inputs, authenticate the producer, guarantee reproducibility, or establish scientific truth.
'''


def compile_pipeline_draft(
    *,
    manifest_path: Path,
    output_dir: Path,
    name: str,
    description: str,
    command_contract: list[list[str]] | None = None,
    limitations: list[str] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    name = _text(name, "name")
    if not SKILL_NAME_RE.fullmatch(name):
        raise ValueError("name must be lowercase kebab-case")
    description = _text(description, "description")
    manifest_path = manifest_path.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    sidecars = validate_bundle(manifest, manifest_path.parent)
    review = review_manifest(manifest, manifest_path.parent, sidecars=sidecars)
    if manifest.get("review", {}).get("status") != "passed" or review.get("status") != "passed":
        raise ValueError("only a currently passed run may be promoted to a skill draft")
    if any(step.get("status") != "completed" for step in manifest.get("plan", []) if isinstance(step, Mapping)):
        raise ValueError("source run has incomplete plan steps")
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    references = output_dir / "references"
    references.mkdir()
    manifest_sha, _size = stream_sha256(manifest_path)
    commands = command_contract or []
    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError(f"command_contract[{index}] must be a non-empty argv list")
    limit_values = limitations or [
        "Generated from one reviewed run and not validated for a new input distribution.",
        "External sources, models, weights, databases, and endpoints may drift.",
        "The draft contains no automatic activation or remote/write permission."
    ]
    (output_dir / "SKILL.md").write_text(
        _skill_text(name, description, str(manifest.get("run_id", "unknown")), [dict(item) for item in manifest.get("plan", []) if isinstance(item, Mapping)]),
        encoding="utf-8",
    )
    _write_json(output_dir / "input.schema.json", _schema_inputs(manifest))
    _write_json(output_dir / "output.schema.json", _schema_outputs())
    (references / "pipeline.md").write_text(
        _reference_text(
            name=name,
            source_manifest_path=manifest_path,
            source_manifest_sha256=manifest_sha,
            manifest=manifest,
            command_contract=commands,
            limitations=limit_values,
        ),
        encoding="utf-8",
    )
    _write_json(
        references / "index.json",
        {
            "schema_version": 1,
            "skill": name,
            "references": [
                {
                    "id": "pipeline",
                    "path": "references/pipeline.md",
                    "purpose": "Exact generated workflow shape, input/output schemas, promotion path, failure handling, and source lineage.",
                    "read_when": ["before using the generated draft", "before reconstructing commands", "before validating or promoting the draft"],
                    "required_before": ["executing any promoted command", "declaring the draft reusable", "adding it to an audited catalog"],
                    "search_patterns": ["## Command contract", "## Output contract", "## Validation and promotion", "## Failure handling"],
                    "authority": "Generated from a hash-validated Codex Science run",
                    "version": "1",
                    "evidence_boundary": "The generated reference preserves workflow structure but is not evidence for a new run."
                }
            ]
        },
    )
    promotion_material = {
        "schema_version": 1,
        "status": "draft",
        "activated": False,
        "cataloged": False,
        "generated_at": generated_at or _now(),
        "skill": name,
        "source_run_id": manifest.get("run_id"),
        "source_manifest_path": str(manifest_path),
        "source_manifest_sha256": manifest_sha,
        "source_review_status": manifest.get("review", {}).get("status"),
        "source_artifacts": _artifact_summary(manifest),
        "command_count": len(commands),
        "limitations": limit_values,
        "required_next_steps": [
            "add redistributable acceptance fixture",
            "seed material failures",
            "add deterministic tests",
            "run independent review",
            "declare honest maturity",
            "pass catalog activation policy"
        ]
    }
    promotion = {**promotion_material, "fingerprint": _fingerprint(promotion_material)}
    _write_json(output_dir / "promotion.json", promotion)
    return promotion
