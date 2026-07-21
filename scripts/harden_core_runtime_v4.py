#!/usr/bin/env python3
"""Apply final resource, input-integrity, and secret-boundary hardening."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_artifact_runtime() -> None:
    path = ROOT / "src" / "codex_science" / "artifact_runtime.py"
    text = path.read_text(encoding="utf-8")
    if "MAX_RUNTIME_BYTES" not in text:
        marker = "VIEWER_SELECTIONS = {\n"
        index = text.index(marker)
        end = text.index("\n}\n", index) + 3
        text = text[:end] + "\nMAX_RUNTIME_BYTES = 16 * 1024 * 1024\nMAX_RUNTIME_RECORDS = 10_000\nMAX_SELECTION_BYTES = 64 * 1024\nMAX_PROPOSAL_PARAMETER_BYTES = 64 * 1024\nMAX_REASON_CHARACTERS = 4_000\n" + text[end:]
    old = '''    if max_bytes < 1 or max_records < 1:
        raise ValueError("max_bytes and max_records must be positive")
'''
    new = '''    if max_bytes < 1 or max_records < 1:
        raise ValueError("max_bytes and max_records must be positive")
    if max_bytes > MAX_RUNTIME_BYTES:
        raise ValueError(f"max_bytes exceeds hard runtime ceiling: {MAX_RUNTIME_BYTES}")
    if max_records > MAX_RUNTIME_RECORDS:
        raise ValueError(f"max_records exceeds hard runtime ceiling: {MAX_RUNTIME_RECORDS}")
'''
    if old in text:
        text = text.replace(old, new, 1)
    old = '''    reason = _text(reason, "selection reason")
    material = {
'''
    new = '''    reason = _text(reason, "selection reason")
    if len(reason) > MAX_REASON_CHARACTERS:
        raise ValueError("selection reason is too long")
    if len(_canonical_bytes(selector)) > MAX_SELECTION_BYTES:
        raise ValueError("selection payload exceeds the runtime limit")
    material = {
'''
    if old in text:
        text = text.replace(old, new, 1)
    old = '''    reason = _text(reason, "proposal reason")
    steps = sorted({_safe_relative(item, "affected step") for item in affected_steps})
'''
    new = '''    reason = _text(reason, "proposal reason")
    if len(reason) > MAX_REASON_CHARACTERS:
        raise ValueError("proposal reason is too long")
    if len(_canonical_bytes(parameters)) > MAX_PROPOSAL_PARAMETER_BYTES:
        raise ValueError("proposal parameters exceed the runtime limit")
    steps = sorted({_safe_relative(item, "affected step") for item in affected_steps})
'''
    if old in text:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def patch_compute_inputs() -> None:
    path = ROOT / "src" / "codex_science" / "compute_backends.py"
    text = path.read_text(encoding="utf-8")
    if "def _normalize_inputs" not in text:
        marker = "\n\n@dataclass(frozen=True)\nclass ResourceRequest:\n"
        helper = '''

def _normalize_inputs(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("inputs must be a list")
    results: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(value):
        if not isinstance(raw, Mapping):
            raise ValueError(f"input {index} must be an object")
        item = dict(raw)
        input_id = _text(item.get("id", f"input-{index}"), f"input {index} id")
        if input_id in ids:
            raise ValueError(f"duplicate input ID: {input_id}")
        ids.add(input_id)
        item["id"] = input_id
        if item.get("path") is not None:
            item["path"] = _safe_relative(str(item["path"]), f"input {input_id} path")
        elif not str(item.get("identifier", "")).strip():
            raise ValueError(f"input {input_id} needs path or identifier")
        if item.get("sha256") is not None:
            item["sha256"] = _sha(item["sha256"], f"input {input_id} sha256")
        if item.get("root_sha256") is not None:
            item["root_sha256"] = _sha(item["root_sha256"], f"input {input_id} root_sha256")
        results.append(item)
    return tuple(results)


def _input_preflight(spec: "JobSpec") -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    working = Path(spec.working_directory).resolve()
    for item in spec.inputs:
        input_id = str(item["id"])
        if item.get("path") is None:
            checks.append({"name": f"input:{input_id}", "ready": True, "detail": "external identifier recorded"})
            continue
        target = (working / str(item["path"])).resolve()
        if not target.is_relative_to(working):
            checks.append({"name": f"input:{input_id}", "ready": False, "detail": "path escapes working directory"})
            continue
        if not target.exists():
            checks.append({"name": f"input:{input_id}", "ready": False, "detail": "missing"})
            continue
        expected = item.get("sha256") or item.get("root_sha256")
        if expected is None:
            checks.append({"name": f"input:{input_id}", "ready": True, "detail": "exists; no digest declared"})
            continue
        if target.is_file():
            actual, _size = stream_sha256(target)
        elif target.is_dir():
            actual = describe_directory(target).root_sha256
        else:
            checks.append({"name": f"input:{input_id}", "ready": False, "detail": "unsupported filesystem object"})
            continue
        checks.append({"name": f"input:{input_id}", "ready": actual == expected, "detail": "digest matches" if actual == expected else f"digest mismatch: {actual}"})
    return checks
'''
        if marker not in text:
            raise SystemExit("compute input helper marker is missing")
        text = text.replace(marker, helper + marker, 1)
    text = text.replace(
        '            inputs=tuple(dict(item) for item in payload.get("inputs", [])),\n',
        '            inputs=_normalize_inputs(payload.get("inputs", [])),\n',
    )
    local_marker = '''        checks = [
            {"name": "working-directory", "ready": Path(spec.working_directory).is_dir(), "detail": spec.working_directory},
            {"name": "executable", "ready": executable is not None, "detail": executable or "not found"},
            {"name": "resource-request-recorded", "ready": True, "detail": spec.resources.to_dict()},
        ]
'''
    local_replacement = local_marker + "        checks.extend(_input_preflight(spec))\n"
    if local_marker in text and "checks.extend(_input_preflight(spec))" not in text[text.index(local_marker):text.index(local_marker) + len(local_marker) + 100]:
        text = text.replace(local_marker, local_replacement, 1)
    slurm_marker = '''        checks = [
            {"name": "working-directory", "ready": Path(spec.working_directory).is_dir(), "detail": spec.working_directory},
            {"name": "sbatch", "ready": sbatch is not None, "detail": sbatch or "not found"},
            {"name": "scancel", "ready": scancel is not None, "detail": scancel or "not found"},
            {"name": "status-command", "ready": sacct is not None or squeue is not None, "detail": sacct or squeue or "not found"},
        ]
'''
    slurm_replacement = slurm_marker + "        checks.extend(_input_preflight(spec))\n"
    if slurm_marker in text:
        text = text.replace(slurm_marker, slurm_replacement, 1)
    path.write_text(text, encoding="utf-8")


def patch_pipeline_command_validation() -> None:
    path = ROOT / "src" / "codex_science" / "pipeline_compiler.py"
    text = path.read_text(encoding="utf-8")
    if "def _validate_command" in text:
        start = text.index("def _validate_command")
        end = text.index("\n\ndef _write_json", start)
        replacement = '''def _validate_command(command: list[str], index: int) -> None:
    for argument in command:
        lower = argument.lower()
        if any(lower == flag or lower.startswith(flag + "=") for flag in SECRET_ARGUMENT_FLAGS):
            raise ValueError(f"command_contract[{index}] contains a credential-bearing argument")
        if "://" in argument and any(
            token in lower
            for token in (
                "token=", "password=", "secret=", "api_key=", "apikey=",
                "access_key=", "client_secret=", "authorization="
            )
        ):
            raise ValueError(f"command_contract[{index}] contains a credential-bearing URL")

'''
        text = text[:start] + replacement + text[end + 2:]
    path.write_text(text, encoding="utf-8")


def patch_action_provider_records() -> None:
    path = ROOT / "src" / "codex_science" / "action_connectors.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '    before = dict(adapter.snapshot(spec))\n    before_sha = _fingerprint(before)\n',
        '    before = dict(adapter.snapshot(spec))\n    _json_value(before, "provider before state")\n    before_sha = _fingerprint(before)\n',
    )
    text = text.replace(
        '    changes = dict(adapter.preview(spec, before))\n    material = {\n',
        '    changes = dict(adapter.preview(spec, before))\n    _json_value(changes, "provider proposed changes")\n    material = {\n',
    )
    text = text.replace(
        '    result = dict(adapter.execute(spec, preview))\n    after = dict(result.get("after_state", result))\n',
        '    result = dict(adapter.execute(spec, preview))\n    _json_value(result, "provider execution result")\n    after = dict(result.get("after_state", result))\n',
    )
    path.write_text(text, encoding="utf-8")


def patch_experiment_integers() -> None:
    path = ROOT / "src" / "codex_science" / "experiment_planner.py"
    text = path.read_text(encoding="utf-8")
    old = '''    batch_size = int(constraints.get("batch_size", 0))
    budget = _number(constraints.get("budget", 0), "budget")
    group_cap = int(constraints.get("diversity_group_cap", constraints.get("scaffold_cap", batch_size)))
    minimum_controls = int(constraints.get("minimum_controls", 0))
'''
    new = '''    batch_raw = constraints.get("batch_size", 0)
    group_raw = constraints.get("diversity_group_cap", constraints.get("scaffold_cap", batch_raw))
    controls_raw = constraints.get("minimum_controls", 0)
    if any(isinstance(item, bool) for item in (batch_raw, group_raw, controls_raw)):
        raise ValueError("batch size, diversity cap, and minimum controls must be integers")
    batch_size = int(batch_raw)
    budget = _number(constraints.get("budget", 0), "budget")
    group_cap = int(group_raw)
    minimum_controls = int(controls_raw)
'''
    if old in text:
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    patch_artifact_runtime()
    patch_compute_inputs()
    patch_pipeline_command_validation()
    patch_action_provider_records()
    patch_experiment_integers()
    print("core runtime v4 hardening: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
