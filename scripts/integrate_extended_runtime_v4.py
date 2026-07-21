#!/usr/bin/env python3
"""Integrate pipeline promotion, experiment planning, and FAIR export references."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def update_index(path: Path, entry: dict[str, Any]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = "references" if "references" in payload else "entries" if "entries" in payload else "references"
    entries = payload.setdefault(key, [])
    if not isinstance(entries, list):
        raise SystemExit(f"reference index list is invalid: {path}")
    existing = next((item for item in entries if isinstance(item, dict) and item.get("id") == entry["id"]), None)
    if existing is None:
        entries.append(entry)
    else:
        existing.clear()
        existing.update(entry)
    entries.sort(key=lambda item: str(item.get("id", "")) if isinstance(item, dict) else "")
    write_json(path, payload)


def add_skill_reference(path: Path, marker: str, paragraph: str) -> None:
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
            raise SystemExit(f"cannot insert reference route: {path}")
        text = text.replace(anchor, f"## Reference usage\n\n{paragraph}\n\n{anchor}", 1)
    path.write_text(text, encoding="utf-8")


def add_quality_outputs(path: Path, values: list[str]) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    outputs = payload.setdefault("output_schemas", [])
    if not isinstance(outputs, list):
        raise SystemExit(f"quality output_schemas is invalid: {path}")
    for value in values:
        if value not in outputs:
            outputs.append(value)
    outputs.sort()
    write_json(path, payload)


def patch_pipeline_compiler() -> None:
    path = ROOT / "src" / "codex_science" / "pipeline_compiler.py"
    text = path.read_text(encoding="utf-8")
    function_start = text.index("def _skill_text(")
    step_line = text.index("    step_lines = []", function_start)
    if "safe_description = description.replace" not in text[function_start:step_line]:
        text = text[:step_line] + '    safe_description = description.replace(chr(34), chr(39))\n' + text[step_line:]
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith('description: "{description.replace('):
            lines[index] = 'description: "{safe_description}"'
    text = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    text = text.replace("manifest.get('review', {{}})", "manifest.get('review', {})")
    text = text.replace("manifest.get('environment', {{}})", "manifest.get('environment', {})")
    path.write_text(text, encoding="utf-8")


def patch_experiment_planner() -> None:
    path = ROOT / "src" / "codex_science" / "experiment_planner.py"
    text = path.read_text(encoding="utf-8")
    old = '    claim_ids = sorted({_text(item, "claim_id") for item in payload.get("claim_ids", [])})\n'
    new = '''    claim_ids_raw = payload.get("claim_ids", [])
    if not isinstance(claim_ids_raw, list):
        raise ValueError("claim_ids must be a list")
    claim_ids = sorted({_text(item, "claim_id") for item in claim_ids_raw})
'''
    if old in text:
        text = text.replace(old, new, 1)
    text = text.replace(
        '            scored.append((score, -front_rank[candidate["id"]], candidate["id"], candidate))\n',
        '            scored.append((score, front_rank[candidate["id"]], candidate["id"], candidate))\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_fair_export() -> None:
    path = ROOT / "src" / "codex_science" / "fair_export.py"
    text = path.read_text(encoding="utf-8")
    old_used = '''        for entity_id in entities:
            if entity_id.startswith("input:"):
                used[f"used:{activity_id}:{entity_id}"] = {"prov:activity": activity_id, "prov:entity": entity_id}
'''
    new_used = '''        recorded_inputs = execution.get("inputs", execution.get("input_ids", []))
        if isinstance(recorded_inputs, list):
            for value in recorded_inputs:
                entity_id = f"input:{value}"
                if entity_id in entities:
                    used[f"used:{activity_id}:{entity_id}"] = {
                        "prov:activity": activity_id,
                        "prov:entity": entity_id,
                    }
'''
    if old_used in text:
        text = text.replace(old_used, new_used, 1)
    marker = '    activities[run_activity] = {"prov:type": "ScientificRun",'
    if 'used[f"used:{run_activity}:{entity_id}"]' not in text:
        line_end = text.index("\n", text.index(marker)) + 1
        addition = '''    for entity_id in entities:
        if entity_id.startswith("input:"):
            used[f"used:{run_activity}:{entity_id}"] = {
                "prov:activity": run_activity,
                "prov:entity": entity_id,
            }
'''
        text = text[:line_end] + addition + text[line_end:]
    old_output = '''    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
'''
    new_output = '''    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"export output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
'''
    if old_output in text:
        text = text.replace(old_output, new_output, 1)
    path.write_text(text, encoding="utf-8")


def patch_references() -> None:
    codex_index = ROOT / "skills" / "codex-science" / "references" / "index.json"
    update_index(
        codex_index,
        {
            "id": "pipeline-promotion",
            "path": "references/pipeline-promotion.md",
            "purpose": "Generate a non-active reusable skill draft from a currently passed run without transferring conclusions or review receipts.",
            "read_when": ["before converting a reviewed run into a reusable workflow", "before generating a skill draft from artifacts"],
            "required_before": ["calling scripts/promote_run_to_skill.py", "adding a generated draft to authored-skills or a catalog"],
            "search_patterns": ["## Preconditions", "## Generated draft", "## Promotion path", "## Failure handling"],
            "authority": "Codex Science first-party promotion contract",
            "version": "1",
            "evidence_boundary": "Promotion preserves workflow shape; it does not activate a skill or prove generalization."
        },
    )
    update_index(
        codex_index,
        {
            "id": "next-experiment-planning",
            "path": "references/next-experiment-planning.md",
            "purpose": "Deterministic Pareto, uncertainty, control, diversity, budget, and batch planning for a non-executing experiment proposal.",
            "read_when": ["before ranking candidates for a new experiment", "before using model uncertainty or multi-objective utility for selection"],
            "required_before": ["calling scripts/plan_next_experiment.py", "treating a selected batch as an approved experiment"],
            "search_patterns": ["## Input contract", "## Selection method", "## Output contract", "## Failure handling"],
            "authority": "Codex Science first-party experiment proposal contract",
            "version": "1",
            "evidence_boundary": "The planner ranks declared properties; it does not calibrate uncertainty, infer similarity, or execute experiments."
        },
    )
    add_skill_reference(
        ROOT / "skills" / "codex-science" / "SKILL.md",
        "references/pipeline-promotion.md",
        "Before turning a reviewed run into a reusable workflow, **MUST** read [the pipeline promotion contract](references/pipeline-promotion.md). `scripts/promote_run_to_skill.py` creates a non-active draft only; acceptance fixtures, seeded failures, independent review, maturity declaration, and catalog policy are still required.",
    )
    add_skill_reference(
        ROOT / "skills" / "codex-science" / "SKILL.md",
        "references/next-experiment-planning.md",
        "Before ranking compounds, assays, datasets, simulations, or other candidates for a next experiment, **MUST** read [the next-experiment planning contract](references/next-experiment-planning.md). Save objectives, controls, budget, diversity groups, uncertainty boundary, selected and rejected records, and approval state; a proposal is not an executed experiment.",
    )

    provenance_index = ROOT / "skills" / "science-provenance" / "references" / "index.json"
    update_index(
        provenance_index,
        {
            "id": "fair-export",
            "path": "references/fair-export.md",
            "purpose": "Export validated run metadata as RO-Crate-oriented, W3C PROV-oriented, and scientific dependency BOM records.",
            "read_when": ["before archival or interoperable export", "before generating a scientific dependency or license handoff"],
            "required_before": ["calling scripts/export_scientific_run.py", "describing an export as portable, FAIR, or compliance-supporting"],
            "search_patterns": ["## RO-Crate-oriented metadata", "## W3C PROV-oriented lineage", "## Scientific dependency BOM", "## Failure handling"],
            "authority": "Codex Science first-party export contract",
            "version": "1",
            "evidence_boundary": "The exporter packages recorded metadata; it does not certify completeness, licensing, regulatory compliance, or scientific validity."
        },
    )
    add_skill_reference(
        ROOT / "skills" / "science-provenance" / "SKILL.md",
        "references/fair-export.md",
        "Before exporting a run for archival, interoperability, dependency review, or compliance-supporting handoff, **MUST** read [the FAIR-oriented export contract](references/fair-export.md). Validate the source bundle first and preserve explicit non-certification, licensing, omitted-byte, and provenance-completeness boundaries.",
    )


def patch_quality_and_docs() -> None:
    add_quality_outputs(ROOT / "skills" / "codex-science" / "quality.json", ["pipeline-promotion-v1", "experiment-proposal-v1"])
    add_quality_outputs(ROOT / "skills" / "science-provenance" / "quality.json", ["fair-export-receipt-v1", "scientific-bom-v1", "ro-crate-oriented-v1", "prov-oriented-v1"])
    quickstart = ROOT / "docs" / "NATIVE_RUNTIME_QUICKSTART.md"
    text = quickstart.read_text(encoding="utf-8")
    marker = "## 5. Promote, plan, and export"
    if marker not in text:
        text = text.rstrip() + '''

## 5. Promote, plan, and export

Read `skills/codex-science/references/pipeline-promotion.md` before generating a skill draft with `scripts/promote_run_to_skill.py`. The generated draft is not active.

Read `skills/codex-science/references/next-experiment-planning.md` before generating `experiment-proposal` records with `scripts/plan_next_experiment.py`. The proposal is not executed and always requires approval.

Read `skills/science-provenance/references/fair-export.md` before using `scripts/export_scientific_run.py`. The export is metadata-oriented and explicitly does not certify regulatory, legal, or formal standards compliance.
'''
        quickstart.write_text(text, encoding="utf-8")
    platform = ROOT / "docs" / "PLATFORM_CONTRACTS.md"
    text = platform.read_text(encoding="utf-8")
    marker = "## Pipeline promotion, next experiments, and FAIR export"
    if marker not in text:
        platform.write_text(text.rstrip() + '''

## Pipeline promotion, next experiments, and FAIR export

A passed run may be converted into a non-active skill draft with `scripts/promote_run_to_skill.py`. The draft preserves source manifest identity, argv contracts, explicit schemas, limitations, and a promotion checklist; it does not enter the catalog automatically.

`scripts/plan_next_experiment.py` creates deterministic, non-executing proposals from declared objectives, uncertainty, controls, diversity groups, budget, and batch constraints. Selected and rejected records remain inspectable and approval is still required.

`scripts/export_scientific_run.py` emits RO-Crate-oriented metadata, W3C PROV-oriented lineage, a scientific dependency BOM, and a hash-covered receipt from a validated bundle. The export does not certify formal conformance, licensing, regulatory compliance, or provenance completeness.
''', encoding="utf-8")


def main() -> int:
    patch_pipeline_compiler()
    patch_experiment_planner()
    patch_fair_export()
    patch_references()
    patch_quality_and_docs()
    subprocess.run([sys.executable, "-m", "compileall", "-q", "src", "scripts"], cwd=ROOT, check=True)
    print("extended native runtime v4 integration: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
