#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from codex_science.release import (  # noqa: E402
    classify_release_path,
    load_release_manifest,
    manifest_runtime_version,
    release_version_advances,
    validate_release,
)


POLICY_PATHS = (
    "release/manifest.json",
    "scripts/science_runtime_state.py",
    "scripts/science_update_hook.py",
    "scripts/validate_release.py",
    "src/codex_science/release.py",
    "src/codex_science/version.py",
)


def _git_json(root: Path, revision: str, path: str) -> dict:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"could not read {path} at {revision}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"could not parse {path} at {revision}: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{path} at {revision} is not a JSON object")
    return payload


def _semantic_path_policy(
    files: list[str], prefixes: list[str]
) -> tuple[frozenset[str], frozenset[str]]:
    """Canonicalize the positive exact-file/prefix matcher used by a policy."""

    unique_prefixes = set(prefixes)
    effective_prefixes = frozenset(
        prefix
        for prefix in unique_prefixes
        if not any(
            prefix != other and prefix.startswith(other)
            for other in unique_prefixes
        )
    )
    effective_files = frozenset(
        path
        for path in files
        if not any(path.startswith(prefix) for prefix in effective_prefixes)
    )
    return effective_files, effective_prefixes


def _base_diff_errors(root: Path, base_ref: str) -> list[str]:
    merge_base = subprocess.run(
        ["git", "-C", str(root), "merge-base", base_ref, "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    base_commit = merge_base.stdout.strip()
    if merge_base.returncode != 0 or len(base_commit) != 40:
        return [merge_base.stderr.strip() or f"could not resolve merge base with {base_ref}"]
    changed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            f"{base_commit}..HEAD",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if changed.returncode != 0:
        return [changed.stderr.strip() or f"could not compare release with {base_ref}"]
    try:
        previous_plugin = _git_json(root, base_commit, ".codex-plugin/plugin.json")
        previous_manifest = _git_json(root, base_commit, "release/manifest.json")
        previous_plugin_version = str(previous_plugin["version"])
        current_plugin_version = str(
            json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))[
                "version"
            ]
        )
        current_manifest = load_release_manifest(root)
        previous_runtime_version = manifest_runtime_version(previous_manifest)
        current_runtime_version = manifest_runtime_version(current_manifest)
        previous_prefixes = previous_manifest["runtime_affecting_prefixes"]
        current_prefixes = current_manifest["runtime_affecting_prefixes"]
        previous_neutral_files = previous_manifest.get("cache_neutral_files", [])
        current_neutral_files = current_manifest.get("cache_neutral_files", [])
        previous_neutral_prefixes = previous_manifest.get("cache_neutral_prefixes", [])
        current_neutral_prefixes = current_manifest.get("cache_neutral_prefixes", [])
        previous_bootstrap_files = previous_manifest.get("bootstrap_affecting_files", [])
        current_bootstrap_files = current_manifest.get("bootstrap_affecting_files", [])
        previous_bootstrap_prefixes = previous_manifest.get(
            "bootstrap_affecting_prefixes", []
        )
        current_bootstrap_prefixes = current_manifest.get(
            "bootstrap_affecting_prefixes", []
        )
        for label, values in (
            ("base runtime-affecting prefixes", previous_prefixes),
            ("current runtime-affecting prefixes", current_prefixes),
            ("base cache-neutral files", previous_neutral_files),
            ("current cache-neutral files", current_neutral_files),
            ("base cache-neutral prefixes", previous_neutral_prefixes),
            ("current cache-neutral prefixes", current_neutral_prefixes),
            ("base bootstrap-affecting files", previous_bootstrap_files),
            ("current bootstrap-affecting files", current_bootstrap_files),
            ("base bootstrap-affecting prefixes", previous_bootstrap_prefixes),
            ("current bootstrap-affecting prefixes", current_bootstrap_prefixes),
        ):
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values
            ):
                raise ValueError(f"{label} are invalid")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return [f"could not compare release versions: {error}"]
    paths = [value for value in changed.stdout.split("\0") if value]
    runtime_prefixes = tuple(
        dict.fromkeys([*previous_prefixes, *current_prefixes, *POLICY_PATHS])
    )
    # A path is neutral only when both the base and candidate policy admit it.
    # New or reclassified paths therefore require a cachebuster instead of
    # silently weakening the release boundary in the same commit.
    neutral_files = set(previous_neutral_files) & set(current_neutral_files)
    neutral_prefixes = set(previous_neutral_prefixes) & set(current_neutral_prefixes)
    risky_paths = [
        path
        for path in paths
        if classify_release_path(
            path,
            runtime_prefixes=runtime_prefixes,
            neutral_files=neutral_files,
            neutral_prefixes=neutral_prefixes,
        )
        != "neutral"
    ]
    bootstrap_files = set(previous_bootstrap_files) | set(current_bootstrap_files)
    bootstrap_prefixes = set(previous_bootstrap_prefixes) | set(
        current_bootstrap_prefixes
    )
    bootstrap_paths = [
        path
        for path in paths
        if path in bootstrap_files
        or any(path.startswith(prefix) for prefix in bootstrap_prefixes)
    ]
    bootstrap_policy_changed = _semantic_path_policy(
        previous_bootstrap_files, previous_bootstrap_prefixes
    ) != _semantic_path_policy(
        current_bootstrap_files, current_bootstrap_prefixes
    )

    errors: list[str] = []
    if risky_paths and not release_version_advances(
        previous_runtime_version, current_runtime_version
    ):
        errors.append(
            "runtime-affecting or unclassified files changed without a monotonic "
            f"runtime version bump from {previous_runtime_version}: "
            f"{', '.join(risky_paths[:8])}"
        )
    bootstrap_reasons = list(bootstrap_paths)
    if bootstrap_policy_changed:
        bootstrap_reasons.append("release/manifest.json (bootstrap policy)")
    if bootstrap_reasons and not release_version_advances(
        previous_plugin_version, current_plugin_version
    ):
        errors.append(
            "bootstrap-affecting files or policy changed without a monotonic plugin "
            f"version bump from {previous_plugin_version}: "
            f"{', '.join(list(dict.fromkeys(bootstrap_reasons))[:8])}"
        )
    return errors


def _tracked_path_errors(root: Path) -> list[str]:
    try:
        manifest = load_release_manifest(root)
        runtime_prefixes = manifest["runtime_affecting_prefixes"]
        neutral_files = manifest["cache_neutral_files"]
        neutral_prefixes = manifest["cache_neutral_prefixes"]
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        return [f"could not classify release paths: {error}"]
    tracked = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked.returncode != 0:
        return [tracked.stderr.strip() or "could not list release paths"]
    errors: list[str] = []
    for path in (value for value in tracked.stdout.split("\0") if value):
        runtime = any(path.startswith(prefix) for prefix in runtime_prefixes)
        neutral = path in neutral_files or any(
            path.startswith(prefix) for prefix in neutral_prefixes
        )
        if runtime == neutral:
            state = "overlapping" if runtime else "unclassified"
            errors.append(f"release path is {state}: {path}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--base-ref")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = validate_release(root)
    errors.extend(_tracked_path_errors(root))
    if args.base_ref:
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            capture_output=True,
            text=True,
            check=False,
        )
        if dirty.returncode != 0:
            errors.append(dirty.stderr.strip() or "could not inspect worktree state")
        elif dirty.stdout:
            errors.append(
                "--base-ref validates committed changes only; commit or stash worktree changes first"
            )
        else:
            errors.extend(_base_diff_errors(root, args.base_ref))
    if errors:
        raise SystemExit("\n".join(errors))
    print("release contract: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
