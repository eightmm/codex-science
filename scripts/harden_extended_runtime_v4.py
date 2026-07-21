#!/usr/bin/env python3
"""Harden generated pipeline drafts against secret and private-input propagation."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    path = ROOT / "src" / "codex_science" / "pipeline_compiler.py"
    text = path.read_text(encoding="utf-8")
    if "SECRET_ARGUMENT_FLAGS" not in text:
        marker = 'SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")\n'
        addition = '''SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SECRET_ARGUMENT_FLAGS = {
    "--token", "--password", "--secret", "--credential", "--api-key",
    "--apikey", "--private-key", "--access-key", "--client-secret"
}
SECRET_KEY_FRAGMENTS = {
    "token", "password", "secret", "credential", "private_key", "api_key",
    "apikey", "access_key", "client_secret"
}
'''
        if marker not in text:
            raise SystemExit("pipeline compiler constant marker is missing")
        text = text.replace(marker, addition, 1)
    if "def _redact_mapping" not in text:
        marker = "\ndef _write_json(path: Path, payload: Any) -> None:\n"
        helper = '''
def _redact_mapping(value: Any) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(fragment in key_text.lower() for fragment in SECRET_KEY_FRAGMENTS):
                result[key_text] = "[REDACTED]"
            else:
                result[key_text] = _redact_mapping(item)
        return result
    if isinstance(value, list):
        return [_redact_mapping(item) for item in value]
    return value


def _validate_command(command: list[str], index: int) -> None:
    previous = ""
    for argument in command:
        lower = argument.lower()
        if previous in SECRET_ARGUMENT_FLAGS:
            raise ValueError(f"command_contract[{index}] contains a credential value after {previous}")
        if any(lower == flag or lower.startswith(flag + "=") for flag in SECRET_ARGUMENT_FLAGS):
            if "=" in argument:
                raise ValueError(f"command_contract[{index}] contains a credential-bearing argument")
            previous = lower
            continue
        if "://" in argument and any(
            token in lower
            for token in ("token=", "password=", "secret=", "api_key=", "apikey=", "access_key=")
        ):
            raise ValueError(f"command_contract[{index}] contains a credential-bearing URL")
        previous = lower

'''
        if marker not in text:
            raise SystemExit("pipeline compiler helper marker is missing")
        text = text.replace(marker, helper + marker, 1)
    text = text.replace(
        '        "x-source-run-inputs": list(manifest.get("inputs", []))\n',
        '        "x-source-run-input-count": len(manifest.get("inputs", [])),\n        "x-source-run-input-fields": sorted({str(key) for item in manifest.get("inputs", []) if isinstance(item, Mapping) for key in item.keys()})\n',
    )
    text = text.replace(
        '    safe_description = description.replace(chr(34), chr(39))\n',
        '    safe_description = " ".join(description.replace(chr(34), chr(39)).split())\n',
    )
    text = text.replace(
        "json.dumps(manifest.get('environment', {}), indent=2, sort_keys=True, ensure_ascii=False)",
        "json.dumps(_redact_mapping(manifest.get('environment', {})), indent=2, sort_keys=True, ensure_ascii=False)",
    )
    old = '''    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError(f"command_contract[{index}] must be a non-empty argv list")
'''
    new = '''    for index, command in enumerate(commands):
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError(f"command_contract[{index}] must be a non-empty argv list")
        _validate_command(command, index)
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif "_validate_command(command, index)" not in text:
        raise SystemExit("pipeline command validation marker is missing")
    path.write_text(text, encoding="utf-8")
    print("extended runtime hardening: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
