#!/usr/bin/env python3
"""Check and explicitly apply safe updates for a managed Codex Science install."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping, NamedTuple


SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from science_runtime_state import (  # noqa: E402
    canonical_plugin_data,
    ensure_runtime,
    inspect_activation_record,
    install_runtime_append_only,
    runtime_cache_lock,
)


CHECK_TTL_SECONDS = 24 * 60 * 60
FAILURE_RETRY_SECONDS = 5 * 60
DEFAULT_LOCK_WAIT_SECONDS = 0.0
DISPATCH_LOCK_WAIT_SECONDS = 700.0
MAX_WAIT_BEFORE_NEW_UPDATE_SECONDS = 5.0
DEFAULT_HOME = Path.home() / ".codex-science"
OFFICIAL_HTTPS_REMOTE = "https://github.com/eightmm/codex-science.git"
OFFICIAL_REMOTES = frozenset(
    {
        OFFICIAL_HTTPS_REMOTE,
        OFFICIAL_HTTPS_REMOTE.removesuffix(".git"),
        "git@github.com:eightmm/codex-science.git",
        "ssh://git@github.com/eightmm/codex-science.git",
    }
)
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
UPDATE_PATTERNS = (
    re.compile(
        r"^\s*(?:please\s+)?(?:update|upgrade)\s+codex[ -]science"
        r"(?:\s+now)?[.!]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science(?:를)?\s*(?:업데이트|최신화|갱신)"
        r"(?:해\s*줘|해줘|해주세요|해)?[.!]?\s*$",
        re.IGNORECASE,
    ),
)
ACTIVATION_PATTERNS = (
    re.compile(r"(?:^|\s)\$codex-science\b", re.IGNORECASE),
    re.compile(
        r"^\s*(?:please\s+)?(?:start|activate|enable|enter|load)\s+(?:the\s+)?"
        r"codex[ -]science\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science\s+(?:start|activate|enable|enter|load)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*codex[ -]science(?:를)?\s*(?:(?:한\s*번|한번)\s*)?"
        r"(?:시작|활성화|켜|로드)",
        re.IGNORECASE,
    ),
)
CACHE_NEUTRAL_FILES = (
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "LICENSE",
    "PROJECT.md",
    "README.md",
    "README.ko.md",
)
CACHE_NEUTRAL_PREFIXES = (
    ".claude/",
    ".github/",
    ".oms/",
    "benchmarks/",
    "tests/",
)
POLICY_PATHS = frozenset(
    {
        "release/manifest.json",
        "scripts/science_runtime_state.py",
        "scripts/science_update_hook.py",
        "scripts/validate_release.py",
        "src/codex_science/release.py",
        "src/codex_science/version.py",
    }
)
BOOTSTRAP_POLICY_FILES = frozenset(
    {
        ".agents/plugins/marketplace.json",
        ".mcp.json",
        "scripts/python_runtime.sh",
        "scripts/science_hook_dispatch.py",
        "scripts/science_mcp_proxy.py",
        "scripts/science_runtime_state.py",
        "scripts/science_update_entry.py",
        "scripts/science_update_hook.py",
    }
)
BOOTSTRAP_POLICY_PREFIXES = (
    ".codex-plugin/",
    "hooks/",
    "skills/",
)
RELEASE_VERSION_RE = re.compile(
    r"^(?P<package>\d+\.\d+\.\d+)\+codex\.(?P<cache>\d{14})$"
)
SESSION_FILE_RE = re.compile(r"^[0-9a-f]{64}$")
MIGRATION_ACK_VALUE = "all-codex-tasks-closed"


class UpdateStatus(NamedTuple):
    local_commit: str
    remote_commit: str
    checked_at: int
    checkout: str
    remote_url: str

    @property
    def update_available(self) -> bool:
        return self.local_commit != self.remote_commit


class RuntimeResolution(NamedTuple):
    status: str
    runtime_root: str
    runtime_commit: str
    message: str | None
    updated: bool


def is_update_request(prompt: str) -> bool:
    return any(pattern.fullmatch(prompt) for pattern in UPDATE_PATTERNS)


def is_activation_request(prompt: str) -> bool:
    return any(pattern.search(prompt) for pattern in ACTIVATION_PATTERNS)


def is_official_remote(value: str) -> bool:
    return value.strip().rstrip("/") in OFFICIAL_REMOTES


def _run(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 10,
    input_text: str | None = None,
    environment: Mapping[str, str] | None = None,
):
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
        env=dict(environment) if environment is not None else None,
        check=False,
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = path.parent.lstat()
    if path.parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise OSError("update state directory is not private regular storage")
    path.parent.chmod(0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_durable(source: Path, destination: Path) -> None:
    source_parent = source.parent
    destination_parent = destination.parent
    source.rename(destination)
    _fsync_directory(source_parent)
    if destination_parent != source_parent:
        _fsync_directory(destination_parent)


def write_cache(path: Path, status: UpdateStatus) -> None:
    _atomic_json(path, status._asdict())


def read_cache(path: Path, *, now: int | None = None) -> UpdateStatus | None:
    try:
        metadata = path.lstat()
        if not stat.S_ISREG(metadata.st_mode):
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        status = UpdateStatus(
            local_commit=str(payload["local_commit"]),
            remote_commit=str(payload["remote_commit"]),
            checked_at=int(payload["checked_at"]),
            checkout=str(payload["checkout"]),
            remote_url=str(payload["remote_url"]),
        )
    except (FileNotFoundError, PermissionError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if not COMMIT_RE.fullmatch(status.local_commit) or not COMMIT_RE.fullmatch(status.remote_commit):
        return None
    current = int(time.time()) if now is None else now
    if status.checked_at > current or current - status.checked_at > CHECK_TTL_SECONDS:
        return None
    return status


def _write_attempt(path: Path, checked_at: int) -> None:
    _atomic_json(path, {"checked_at": checked_at})


def _recent_attempt(path: Path, *, now: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        checked_at = int(payload["checked_at"])
    except (FileNotFoundError, PermissionError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False
    return checked_at <= now and now - checked_at <= FAILURE_RETRY_SECONDS


def _git_output(home: Path, arguments: list[str], *, timeout: int = 10) -> str | None:
    result = _run(["git", "-C", str(home), *arguments], timeout=timeout)
    return result.stdout.strip() if result.returncode == 0 else None


def _eligible_checkout(home: Path, branch: str) -> tuple[str, str] | None:
    if not (home / ".git").is_dir():
        return None
    remote_url = _git_output(home, ["remote", "get-url", "origin"])
    if remote_url is None or not is_official_remote(remote_url):
        return None
    dirty = _git_output(home, ["status", "--porcelain", "--untracked-files=normal"])
    if dirty is None or dirty:
        return None
    local = _git_output(home, ["rev-parse", "HEAD"])
    tracking = _git_output(home, ["rev-parse", f"refs/remotes/origin/{branch}"])
    if local is None or tracking is None:
        return None
    if not COMMIT_RE.fullmatch(local) or local != tracking:
        return None
    return local.lower(), remote_url


def get_status(
    home: Path,
    plugin_data: Path,
    branch: str,
    *,
    force: bool = False,
) -> UpdateStatus | None:
    eligible = _eligible_checkout(home, branch)
    if eligible is None:
        return None
    local_commit, remote_url = eligible
    checkout = str(home.resolve())
    cache_path = plugin_data / "update-check.json"
    attempt_path = plugin_data / "update-attempt.json"
    now = int(time.time())
    if not force:
        cached = read_cache(cache_path, now=now)
        if (
            cached is not None
            and cached.local_commit == local_commit
            and cached.checkout == checkout
            and cached.remote_url == remote_url
        ):
            return cached
    if not force and _recent_attempt(attempt_path, now=now):
        return None
    remote = _run(
        ["git", "-C", str(home), "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
        timeout=10,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        _write_attempt(attempt_path, now)
        return None
    remote_commit = remote.stdout.split()[0].lower()
    if not COMMIT_RE.fullmatch(remote_commit):
        return None
    status = UpdateStatus(local_commit, remote_commit, now, checkout, remote_url)
    write_cache(cache_path, status)
    attempt_path.unlink(missing_ok=True)
    return status


def get_advertised_status(home: Path, plugin_data: Path, branch: str) -> UpdateStatus | None:
    """Return only a still-valid status that was previously shown to the user."""
    eligible = _eligible_checkout(home, branch)
    if eligible is None:
        return None
    local_commit, remote_url = eligible
    cached = read_cache(plugin_data / "update-check.json")
    if cached is None:
        return None
    if (
        cached.local_commit != local_commit
        or cached.checkout != str(home.resolve())
        or cached.remote_url != remote_url
    ):
        return None
    return cached


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_manifest(root: Path) -> dict[str, str] | None:
    if not root.is_dir():
        return None
    manifest: dict[str, str] = {}
    try:
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if ".git" in relative.parts or "__pycache__" in relative.parts:
                continue
            if path.is_symlink():
                manifest[str(relative)] = f"link:{os.readlink(path)}"
            elif path.is_file() and path.suffix != ".pyc":
                manifest[str(relative)] = _sha256(path)
    except OSError:
        return None
    return manifest


def _restore_tree(backup: Path, destination: Path) -> bool:
    try:
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(backup, destination, symlinks=True)
    except OSError:
        return False
    return _directory_manifest(backup) == _directory_manifest(destination)


def _restore_previous(home: Path, previous: Path, failed: Path) -> bool:
    """Restore the prior checkout without ever deleting its only remaining copy."""
    try:
        if home.exists():
            if failed.exists():
                shutil.rmtree(failed)
            _rename_durable(home, failed)
        _rename_durable(previous, home)
    except OSError:
        return False
    return home.exists() and not previous.exists()


def _plugin_version(root: Path) -> str | None:
    try:
        payload = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        version = payload["version"]
    except (OSError, UnicodeError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and version else None


def _runtime_version(root: Path) -> str | None:
    try:
        payload = json.loads(
            (root / "release" / "manifest.json").read_text(encoding="utf-8")
        )
        # Schema-v1 releases used the host plugin cachebuster as runtime identity.
        version = payload.get("runtime_version", payload.get("plugin_version"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and RELEASE_VERSION_RE.fullmatch(version) else None


def _version_advances(previous: str, current: str) -> bool:
    previous_match = RELEASE_VERSION_RE.fullmatch(previous)
    current_match = RELEASE_VERSION_RE.fullmatch(current)
    if previous_match is None or current_match is None:
        return False
    previous_package = tuple(
        int(value) for value in previous_match.group("package").split(".")
    )
    current_package = tuple(
        int(value) for value in current_match.group("package").split(".")
    )
    if current_package != previous_package:
        return current_package > previous_package
    return int(current_match.group("cache")) > int(previous_match.group("cache"))


def _mcp_discovery_contract(root: Path) -> object | None:
    """Return the complete discovery contract a stable MCP proxy would expose."""

    script = root / "scripts" / "science_mcp.py"
    inventory = root / "catalog" / "inventory.json"
    if not script.is_file() or not inventory.is_file():
        return None
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    for name in (
        "CODEX_SCIENCE_RUNTIME_VERSION",
        "CODEX_SCIENCE_RUNTIME_COMMIT",
        "CODEX_SCIENCE_RUNTIME_RECEIPT",
    ):
        environment.pop(name, None)
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", str(script), "--inventory", str(inventory)],
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=environment,
        )
    except OSError:
        return None
    if process.stdin is None or process.stdout is None:
        process.kill()
        process.wait()
        return None

    def exchange(payload: Mapping[str, Any]) -> dict[str, Any] | None:
        try:
            process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
            process.stdin.flush()
            ready, _, _ = select.select([process.stdout], [], [], 20)
            if not ready:
                return None
            line = process.stdout.readline()
            response = json.loads(line)
        except (BrokenPipeError, OSError, UnicodeError, json.JSONDecodeError):
            return None
        return response if isinstance(response, dict) else None

    try:
        initialized = exchange(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        )
        if initialized is None or not isinstance(initialized.get("result"), dict):
            return None
        initialize_result = initialized["result"]
        server_info = initialize_result.get("serverInfo")
        initialize_contract = {
            "protocolVersion": initialize_result.get("protocolVersion"),
            "capabilities": initialize_result.get("capabilities"),
            "instructions": initialize_result.get("instructions"),
            "serverName": (
                server_info.get("name") if isinstance(server_info, dict) else None
            ),
        }
        process.stdin.write(
            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n'
        )
        process.stdin.flush()
        pages: list[object] = []
        cursor: object | None = None
        for request_id in range(2, 34):
            params = {"cursor": cursor} if cursor is not None else {}
            response = exchange(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/list",
                    "params": params,
                }
            )
            result = response.get("result") if isinstance(response, dict) else None
            if not isinstance(result, dict) or not isinstance(result.get("tools"), list):
                return None
            cursor = result.get("nextCursor")
            pages.append({"tools": result["tools"], "nextCursor": cursor})
            if cursor is None:
                return {"initialize": initialize_contract, "tools": pages}
            if not isinstance(cursor, str) or not cursor:
                return None
        return None
    finally:
        try:
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _core_agent_metadata_valid(candidate: Path) -> bool:
    expected = {
        "codex-science": True,
        "science-provenance": False,
        "science-review": False,
    }
    for parent in ("skills", "runtime-skills"):
        for skill, implicit in expected.items():
            path = candidate / parent / skill / "agents" / "openai.yaml"
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                return False
            section = ""
            values: dict[tuple[str, str], str] = {}
            for raw in lines:
                if raw and not raw.startswith((" ", "\t")) and raw.endswith(":"):
                    section = raw[:-1]
                    continue
                if not raw.startswith("  ") or ":" not in raw:
                    continue
                key, value = raw.strip().split(":", 1)
                values[(section, key)] = value.strip().strip('"\'')
            if any(
                not values.get(("interface", key), "").strip()
                for key in ("display_name", "short_description", "default_prompt")
            ):
                return False
            if f"${skill}" not in values[("interface", "default_prompt")]:
                return False
            if values.get(("policy", "allow_implicit_invocation")) != str(implicit).lower():
                return False
    return True


def _candidate_self_check(candidate: Path) -> bool:
    required = (
        ".codex-plugin/plugin.json",
        ".mcp.json",
        "skills/codex-science/SKILL.md",
        "skills/codex-science/agents/openai.yaml",
        "skills/science-provenance/SKILL.md",
        "skills/science-provenance/agents/openai.yaml",
        "skills/science-review/SKILL.md",
        "skills/science-review/agents/openai.yaml",
        "hooks/hooks.json",
        "scripts/python_runtime.sh",
        "scripts/science_hook_dispatch.py",
        "scripts/science_mcp.py",
        "scripts/science_mcp_proxy.py",
        "scripts/science_runtime_state.py",
        "scripts/science_session_hook.py",
        "scripts/science_stop_hook.py",
        "scripts/science_update_entry.py",
        "scripts/science_update_hook.py",
        "runtime-skills/codex-science/SKILL.md",
        "runtime-skills/codex-science/agents/openai.yaml",
        "runtime-skills/science-provenance/SKILL.md",
        "runtime-skills/science-provenance/agents/openai.yaml",
        "runtime-skills/science-review/SKILL.md",
        "runtime-skills/science-review/agents/openai.yaml",
    )
    if any(not (candidate / relative).is_file() for relative in required):
        return False
    if not _core_agent_metadata_valid(candidate):
        return False
    submodule = _run(
        [
            "git",
            "-C",
            str(candidate),
            "submodule",
            "update",
            "--init",
            "--recursive",
            "--depth",
            "1",
            "vendor/scientific-agent-skills",
        ],
        timeout=180,
    )
    if submodule.returncode != 0:
        return False
    mcp_input = (
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'
    )
    mcp = _run(
        [sys.executable, str(candidate / "scripts" / "science_mcp.py")],
        input_text=mcp_input,
        timeout=20,
    )
    if mcp.returncode != 0 or "science_search_skills" not in mcp.stdout:
        return False
    with tempfile.TemporaryDirectory() as tempdir:
        environment = {
            **os.environ,
            "PLUGIN_DATA": tempdir,
            "CODEX_SCIENCE_AUTO_UPDATE": "off",
            "CODEX_SCIENCE_RUNTIME_VERSION": _runtime_version(candidate) or "",
            "CODEX_SCIENCE_RUNTIME_COMMIT": "a" * 40,
            "CODEX_SCIENCE_RUNTIME_RECEIPT": "b" * 64,
        }
        session = _run(
            [sys.executable, str(candidate / "scripts" / "science_session_hook.py")],
            input_text=(
                '{"hook_event_name":"UserPromptSubmit","session_id":"candidate-check",'
                '"prompt":"Start Codex Science"}'
            ),
            environment=environment,
        )
        if session.returncode != 0 or "Codex Science is active" not in session.stdout:
            return False
    updater = _run(
        [sys.executable, str(candidate / "scripts" / "science_update_hook.py"), "--self-check"]
    )
    return updater.returncode == 0 and "self-check: ok" in updater.stdout


def _changed_paths(candidate: Path, previous: str, current: str) -> tuple[str, ...] | None:
    changed = _run(
        [
            "git",
            "-C",
            str(candidate),
            "diff",
            "--no-renames",
            "--name-only",
            "-z",
            f"{previous}..{current}",
        ],
        timeout=30,
    )
    if changed.returncode != 0:
        return None
    return tuple(path for path in changed.stdout.split("\0") if path)


def _release_neutral_policy(
    candidate: Path, revision: str
) -> tuple[frozenset[str], tuple[str, ...]] | None:
    result = _run(
        ["git", "-C", str(candidate), "show", f"{revision}:release/manifest.json"],
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
        files = payload.get("cache_neutral_files")
        prefixes = payload.get("cache_neutral_prefixes")
    except (AttributeError, json.JSONDecodeError):
        return None
    if not isinstance(files, list) or not isinstance(prefixes, list):
        return None
    file_set: set[str] = set()
    prefix_values: list[str] = []
    for value in files:
        if (
            not isinstance(value, str)
            or not value
            or value.startswith("/")
            or value.endswith("/")
            or "\\" in value
            or "\0" in value
            or ".." in Path(value).parts
        ):
            return None
        file_set.add(value)
    for value in prefixes:
        if (
            not isinstance(value, str)
            or not value.endswith("/")
            or value.startswith("/")
            or "\\" in value
            or "\0" in value
            or ".." in Path(value).parts
        ):
            return None
        prefix_values.append(value)
    return frozenset(file_set), tuple(prefix_values)


def _release_bootstrap_policy(
    candidate: Path, revision: str
) -> tuple[frozenset[str], tuple[str, ...]] | None:
    result = _run(
        ["git", "-C", str(candidate), "show", f"{revision}:release/manifest.json"],
        timeout=30,
    )
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
        files = payload.get("bootstrap_affecting_files", [])
        prefixes = payload.get("bootstrap_affecting_prefixes", [])
    except (AttributeError, json.JSONDecodeError):
        return None
    if not isinstance(files, list) or not isinstance(prefixes, list):
        return None
    file_set: set[str] = set(BOOTSTRAP_POLICY_FILES)
    prefix_values: list[str] = list(BOOTSTRAP_POLICY_PREFIXES)
    for value in files:
        if (
            not isinstance(value, str)
            or not value
            or value.startswith("/")
            or value.endswith("/")
            or "\\" in value
            or "\0" in value
            or ".." in Path(value).parts
        ):
            return None
        file_set.add(value)
    for value in prefixes:
        if (
            not isinstance(value, str)
            or not value.endswith("/")
            or value.startswith("/")
            or "\\" in value
            or "\0" in value
            or ".." in Path(value).parts
        ):
            return None
        prefix_values.append(value)
    return frozenset(file_set), tuple(dict.fromkeys(prefix_values))


def _bootstrap_change(
    paths: tuple[str, ...],
    base_policy: tuple[frozenset[str], tuple[str, ...]],
    candidate_policy: tuple[frozenset[str], tuple[str, ...]],
) -> bool:
    if base_policy[0] != candidate_policy[0] or set(base_policy[1]) != set(
        candidate_policy[1]
    ):
        return True
    files = base_policy[0] | candidate_policy[0] | BOOTSTRAP_POLICY_FILES
    prefixes = tuple(
        dict.fromkeys(
            [
                *BOOTSTRAP_POLICY_PREFIXES,
                *base_policy[1],
                *candidate_policy[1],
            ]
        )
    )
    return any(path in files or any(path.startswith(prefix) for prefix in prefixes) for path in paths)


def _cache_neutral_change(
    paths: tuple[str, ...],
    base_policy: tuple[frozenset[str], tuple[str, ...]],
    candidate_policy: tuple[frozenset[str], tuple[str, ...]],
) -> bool:
    def admitted(path: str, policy: tuple[frozenset[str], tuple[str, ...]]) -> bool:
        files, prefixes = policy
        return path not in POLICY_PATHS and (
            path in files or any(path.startswith(prefix) for prefix in prefixes)
        )

    return all(
        admitted(path, base_policy) and admitted(path, candidate_policy)
        for path in paths
    )


def _bootstrap_manifest(root: Path) -> dict[str, str] | None:
    selected: dict[str, str] = {}
    try:
        for relative in sorted(BOOTSTRAP_POLICY_FILES):
            path = root / relative
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                selected[relative] = f"link:{os.readlink(path)}"
            elif stat.S_ISREG(metadata.st_mode):
                selected[relative] = _sha256(path)
            else:
                return None
        for prefix in BOOTSTRAP_POLICY_PREFIXES:
            directory = root / prefix.rstrip("/")
            metadata = directory.lstat()
            if directory.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
                return None
            for current, directories, files in os.walk(directory, followlinks=False):
                base = Path(current)
                directories[:] = sorted(
                    name for name in directories if name != "__pycache__"
                )
                if any((base / name).is_symlink() for name in directories):
                    return None
                for name in sorted(files):
                    path = base / name
                    relative = path.relative_to(root).as_posix()
                    if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                        continue
                    metadata = path.lstat()
                    if stat.S_ISLNK(metadata.st_mode):
                        selected[relative] = f"link:{os.readlink(path)}"
                    elif stat.S_ISREG(metadata.st_mode):
                        selected[relative] = _sha256(path)
                    else:
                        return None
    except OSError:
        return None
    return selected


def _installed_bootstrap_matches(source: Path) -> bool:
    version = _plugin_version(source)
    if version is None:
        return False
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    cache = (
        codex_home
        / "plugins"
        / "cache"
        / "codex-science"
        / "codex-science"
        / version
    )
    source_manifest = _bootstrap_manifest(source)
    cache_manifest = _bootstrap_manifest(cache)
    return source_manifest is not None and cache_manifest == source_manifest


def _configured_plugin_enabled() -> bool:
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    try:
        config = tomllib.loads(
            (codex_home / "config.toml").read_text(encoding="utf-8")
        )
    except (FileNotFoundError, OSError, UnicodeError, tomllib.TOMLDecodeError):
        return False
    plugin = config.get("plugins", {}).get("codex-science@codex-science", {})
    return isinstance(plugin, dict) and plugin.get("enabled") is True


def _listed_plugin(source: Path) -> tuple[dict[str, Any] | None, str | None]:
    listing = _run(["codex", "plugin", "list", "--json"], timeout=60)
    if listing.returncode != 0:
        return None, _command_reason(listing, "could not list installed plugins")
    try:
        payload = json.loads(listing.stdout)
        installed = payload["installed"]
        matches = [
            item
            for item in installed
            if isinstance(item, dict)
            and item.get("pluginId") == "codex-science@codex-science"
        ]
    except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
        return None, "Codex returned invalid installed-plugin metadata"
    if len(matches) > 1:
        return None, "Codex returned duplicate codex-science registrations"
    return (matches[0] if matches else None), None


def _host_registration_matches(source: Path) -> tuple[bool, str]:
    expected_version = _plugin_version(source)
    if expected_version is None:
        return False, "plugin source has no valid bootstrap version"
    entry, listing_error = _listed_plugin(source)
    if entry is not None:
        source_info = entry.get("source")
        source_path = source_info.get("path") if isinstance(source_info, dict) else None
        try:
            same_source = (
                isinstance(source_path, str)
                and Path(source_path).expanduser().resolve() == source.resolve()
            )
        except OSError:
            same_source = False
        if (
            entry.get("version") == expected_version
            and entry.get("installed") is True
            and entry.get("enabled") is True
            and same_source
            and _installed_bootstrap_matches(source)
        ):
            return True, "host bootstrap is registered and verified"
        return False, "installed Codex plugin does not match the managed bootstrap"
    if (
        listing_error is not None
        and _configured_plugin_enabled()
        and _installed_bootstrap_matches(source)
    ):
        return True, "host bootstrap verified from config and immutable cache"
    return False, listing_error or "Codex Science is not registered"


def _activation_migration_gate(
    plugin_data: Path, *, require_ack: bool = True
) -> tuple[bool, str]:
    acknowledged = (
        os.environ.get("CODEX_SCIENCE_MIGRATION_ACK") == MIGRATION_ACK_VALUE
    )
    if require_ack and not acknowledged:
        return False, (
            "bootstrap migration requires all Codex tasks and the Codex app to be closed; "
            f"then rerun the installer with CODEX_SCIENCE_MIGRATION_ACK={MIGRATION_ACK_VALUE}"
        )
    directory = plugin_data / "science-sessions"
    try:
        metadata = directory.lstat()
    except FileNotFoundError:
        return True, "no active Codex Science tasks"
    except OSError as error:
        return False, f"could not inspect active Codex Science tasks: {error}"
    if directory.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        return False, "activation state path is unsafe"
    try:
        entries = tuple(directory.iterdir())
    except OSError as error:
        return False, f"could not inspect active Codex Science tasks: {error}"
    active = 0
    for path in entries:
        if path.name.startswith(".") and path.name.endswith(".lock"):
            stem = path.name[1:-5]
            if SESSION_FILE_RE.fullmatch(stem):
                continue
        if SESSION_FILE_RE.fullmatch(path.name) is None:
            return False, "activation state contains an unrecognized entry"
        status, _record = inspect_activation_record(path)
        if acknowledged:
            try:
                metadata = path.lstat()
                if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
                    return False, "activation state contains an unsafe task marker"
                path.unlink()
                _fsync_directory(directory)
            except OSError as error:
                return False, f"could not retire stale activation state: {error}"
            continue
        if status == "valid":
            active += 1
        elif status not in {"missing", "expired"}:
            return False, "activation state contains an invalid task marker"
    if active:
        return False, (
            f"{active} active Codex Science task(s) still use the current bootstrap; "
            "close or deactivate them before rerunning the curl installer"
        )
    return True, "no active Codex Science tasks"


def _existing_host_state() -> bool:
    if _configured_plugin_enabled():
        return True
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    cache_root = (
        codex_home / "plugins" / "cache" / "codex-science" / "codex-science"
    )
    try:
        return any(cache_root.iterdir())
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _runtime_install_environment(
    source: Path, *, host_root: Path | None = None
) -> dict[str, str]:
    environment = dict(os.environ)
    if host_root is not None:
        environment["PLUGIN_ROOT"] = str(host_root.expanduser().resolve())
        environment.pop("CODEX_SCIENCE_BOOTSTRAP_VERSION", None)
    else:
        environment.pop("PLUGIN_ROOT", None)
        version = _plugin_version(source)
        if version is not None:
            environment["CODEX_SCIENCE_BOOTSTRAP_VERSION"] = version
    return environment


def _register_host_now(source: Path) -> tuple[bool, str]:
    marketplace_ready, marketplace_reason = ensure_managed_marketplace(source)
    if not marketplace_ready:
        return False, f"managed marketplace repair failed: {marketplace_reason}"
    registration = _run(
        ["codex", "plugin", "add", "codex-science@codex-science"], timeout=60
    )
    if registration.returncode != 0:
        return False, _command_reason(
            registration, "plugin registration command failed"
        )
    matches, verification_reason = _host_registration_matches(source)
    if not matches:
        return False, (
            "plugin registration command completed but verification failed: "
            f"{verification_reason}"
        )
    return True, "host bootstrap registered"


def _marketplace_config_fallback() -> tuple[list[dict[str, Any]], str | None]:
    """Read only the managed marketplace entry when the CLI cannot list it."""
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    config_path = codex_home / "config.toml"
    try:
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [], None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        return [], f"could not read {config_path}: {error}"

    marketplaces = payload.get("marketplaces", {})
    if not isinstance(marketplaces, dict):
        return [], f"{config_path} has invalid marketplace metadata"
    current = marketplaces.get("codex-science")
    if current is None:
        return [], None
    if not isinstance(current, dict):
        return [], f"{config_path} has an invalid codex-science marketplace"
    source = current.get("source")
    source_type = current.get("source_type")
    if not isinstance(source, str) or not source:
        return [], f"{config_path} has no codex-science marketplace source"
    if source_type is not None and not isinstance(source_type, str):
        return [], f"{config_path} has an invalid codex-science source type"
    return [
        {
            "name": "codex-science",
            "root": source,
            "marketplaceSource": {
                "sourceType": source_type,
                "source": source,
            },
        }
    ], None


def _command_reason(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    return result.stderr.strip() or result.stdout.strip() or fallback


def ensure_managed_marketplace(source: Path) -> tuple[bool, str]:
    """Point the Codex Science marketplace at the managed installer checkout."""
    source = Path(source).expanduser().resolve()
    listing = _run(
        ["codex", "plugin", "marketplace", "list", "--json"], timeout=30
    )
    listing_reason = ""
    if listing.returncode == 0:
        try:
            payload = json.loads(listing.stdout)
            marketplaces = payload["marketplaces"]
            matches = [
                item for item in marketplaces if item.get("name") == "codex-science"
            ]
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            listing_reason = "Codex returned invalid marketplace metadata"
    else:
        listing_reason = _command_reason(
            listing, "could not list plugin marketplaces"
        )
    if listing_reason:
        matches, config_reason = _marketplace_config_fallback()
        if config_reason:
            return False, f"{listing_reason}; {config_reason}"
    if len(matches) > 1:
        return False, "Codex returned duplicate codex-science marketplaces"

    add_command = ["codex", "plugin", "marketplace", "add", str(source)]
    if not matches:
        added = _run(add_command, timeout=30)
        if added.returncode != 0:
            reason = _command_reason(added, "could not add managed marketplace")
            if listing_reason:
                reason = f"{reason}; marketplace list failed: {listing_reason}"
            return False, reason
        return True, "managed marketplace added"

    current = matches[0]
    source_metadata = current.get("marketplaceSource") or {}
    source_type = source_metadata.get("sourceType")
    if source_type not in {None, "local"}:
        return False, "existing codex-science marketplace is not a local source"
    previous_value = source_metadata.get("source") or current.get("root")
    if not isinstance(previous_value, str) or not previous_value:
        return False, "existing codex-science marketplace has no local source path"
    previous = Path(previous_value).expanduser().resolve()
    if previous == source:
        return True, "managed marketplace already registered"

    removed = _run(
        ["codex", "plugin", "marketplace", "remove", "codex-science"],
        timeout=30,
    )
    if removed.returncode != 0:
        return False, _command_reason(
            removed, "could not remove previous marketplace source"
        )
    added = _run(add_command, timeout=30)
    if added.returncode == 0:
        return True, f"managed marketplace replaced previous source {previous}"

    restored = _run(
        ["codex", "plugin", "marketplace", "add", str(previous)], timeout=30
    )
    reason = _command_reason(added, "could not add managed marketplace")
    if restored.returncode == 0:
        return False, f"{reason}; previous source restored"
    restore_reason = _command_reason(restored, "restore command failed")
    return False, f"{reason}; previous source restore failed: {restore_reason}"


def register_host_bootstrap(source: Path) -> tuple[bool, str]:
    """Explicit-installer-only host registration after preserving the runtime."""

    source = Path(source).expanduser().resolve()
    plugin_data = canonical_plugin_data(os.environ)
    runtime, runtime_reason = install_runtime_append_only(
        source,
        _runtime_install_environment(source),
        plugin_data=plugin_data,
        repair_existing=True,
    )
    if runtime is None:
        return False, f"private runtime preparation failed: {runtime_reason}"
    matches, match_reason = _host_registration_matches(source)
    if matches:
        return True, f"{match_reason}; {runtime_reason}"
    try:
        with runtime_cache_lock(
            os.environ, plugin_data=plugin_data, exclusive=True, timeout=130.0
        ):
            allowed, gate_reason = _activation_migration_gate(
                plugin_data, require_ack=_existing_host_state()
            )
            if not allowed:
                return False, gate_reason
            registered, registration_reason = _register_host_now(source)
            if not registered:
                return False, registration_reason
    except TimeoutError as error:
        return False, str(error)
    return True, f"host bootstrap registered; {runtime_reason}"


# Kept as a short-lived compatibility name for older streamed installers.  It
# now follows the explicit host-migration contract and never manages Codex's
# cache as the runtime store.
register_plugin_preserving_caches = register_host_bootstrap


def _lock_timeout(value: float | None) -> float:
    if value is not None:
        return max(value, 0.0)
    raw = os.environ.get("CODEX_SCIENCE_UPDATE_LOCK_TIMEOUT", "")
    try:
        return max(float(raw), 0.0) if raw else DEFAULT_LOCK_WAIT_SECONDS
    except ValueError:
        return DEFAULT_LOCK_WAIT_SECONDS


def _acquire_update_lock(home: Path, *, timeout: float | None = None):
    lock_path = home.parent / ".codex-science-update.lock"
    lock_flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        lock_flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(lock_path, lock_flags, 0o600)
        os.fchmod(descriptor, 0o600)
    except OSError as error:
        return None, f"could not acquire update lock: {error}"
    handle = os.fdopen(descriptor, "r+")
    deadline = time.monotonic() + _lock_timeout(timeout)
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return handle, None
        except BlockingIOError:
            if time.monotonic() >= deadline:
                handle.close()
                return None, "another update is already running"
            time.sleep(0.1)


def _release_update_lock(handle: Any) -> None:
    fcntl.flock(handle, fcntl.LOCK_UN)
    handle.close()


def _journal(transaction: Path, phase: str, home: Path) -> None:
    _atomic_json(
        transaction / "journal.json",
        {
            "schema_version": 1,
            "phase": phase,
            "home": str(home.resolve(strict=False)),
            "updated_at": int(time.time()),
        },
    )


def _journal_phase(transaction: Path, home: Path) -> str:
    try:
        payload = json.loads((transaction / "journal.json").read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            return "unknown"
        recorded_home = Path(str(payload["home"])).resolve(strict=False)
        if recorded_home != home.resolve(strict=False):
            return "unknown"
        phase = str(payload.get("phase", "unknown"))
        return phase if phase in {
            "validated",
            "previous_moved",
            "candidate_active",
            "registration_started",
            "host_registered",
            "complete",
        } else "unknown"
    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ):
        return "unknown"


def _recover_transactions(
    home: Path,
    *,
    allow_host_repair: bool = False,
    plugin_data: Path | None = None,
) -> tuple[bool, str | None]:
    """Restore the last known-good checkout after an interrupted rename transaction."""
    recovered = False
    for transaction in sorted(home.parent.glob(".codex-science-update-*")):
        try:
            metadata = transaction.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(metadata.st_mode) or transaction.is_symlink():
            continue
        previous = transaction / "previous"
        phase = _journal_phase(transaction, home)
        if phase == "complete":
            if _eligible_checkout(home, "main") is not None:
                shutil.rmtree(transaction, ignore_errors=True)
                continue
            if not previous.is_dir() or previous.is_symlink():
                return recovered, (
                    "completed update has no verified active checkout or recoverable previous "
                    f"checkout: {transaction}"
                )
        if phase in {"registration_started", "host_registered"}:
            if (
                not allow_host_repair
                or os.environ.get("CODEX_SCIENCE_MIGRATION_ACK")
                != MIGRATION_ACK_VALUE
            ):
                return recovered, (
                    "bootstrap registration was interrupted; close all Codex tasks and rerun "
                    "the acknowledged curl installer"
                )
            data = plugin_data or canonical_plugin_data(os.environ)
            try:
                with runtime_cache_lock(
                    os.environ, plugin_data=data, exclusive=True, timeout=130.0
                ):
                    allowed, reason = _activation_migration_gate(
                        data, require_ack=True
                    )
                    if not allowed:
                        return recovered, reason
                    matches, _match_reason = _host_registration_matches(home)
                    if matches and _eligible_checkout(home, "main") is not None:
                        shutil.rmtree(transaction, ignore_errors=True)
                        recovered = True
                        continue
                    if previous.is_symlink() or _eligible_checkout(previous, "main") is None:
                        return recovered, (
                            "interrupted bootstrap registration has no verified previous checkout"
                        )
                    failed = transaction / "failed-recovery"
                    if not _restore_previous(home, previous, failed):
                        return recovered, "could not restore interrupted bootstrap migration"
                    registered, registration_reason = _register_host_now(home)
                    if not registered:
                        return recovered, (
                            "restored previous checkout but host registration failed: "
                            f"{registration_reason}"
                        )
                    shutil.rmtree(transaction, ignore_errors=True)
                    recovered = True
                    continue
            except (OSError, TimeoutError, subprocess.TimeoutExpired) as error:
                return recovered, f"could not recover bootstrap migration: {error}"
        if previous.is_dir() and not previous.is_symlink():
            if phase == "unknown":
                return recovered, f"interrupted update journal is untrusted: {transaction}"
            if _eligible_checkout(previous, "main") is None:
                return recovered, (
                    "interrupted update previous checkout is not verified; retained both trees: "
                    f"{transaction}"
                )
            failed = transaction / "failed-recovery"
            try:
                if home.exists() or home.is_symlink():
                    if failed.exists() or failed.is_symlink():
                        return recovered, f"interrupted update recovery path already exists: {failed}"
                    _rename_durable(home, failed)
                _rename_durable(previous, home)
            except OSError as error:
                return recovered, f"could not recover interrupted update: {error}"
            recovered = True
        elif phase in {"previous_moved", "candidate_active"}:
            if _eligible_checkout(home, "main") is None:
                return recovered, f"interrupted update has no recoverable checkout: {transaction}"
            # A prior recovery may have restored `previous` and crashed before cleanup.
            # Re-register the verified active checkout before discarding the journal.
            recovered = True
        if previous.exists():
            return recovered, f"interrupted update retained for recovery: {transaction}"
        shutil.rmtree(transaction, ignore_errors=True)
    return recovered, None


def repair_interrupted_update(
    home: Path,
    current_plugin_root: Path | None,
    *,
    lock_timeout: float | None = None,
    plugin_data: Path | None = None,
    allow_host_repair: bool = False,
) -> tuple[bool, str]:
    handle, error = _acquire_update_lock(home, timeout=lock_timeout)
    if handle is None:
        return False, str(error)
    try:
        data = plugin_data or canonical_plugin_data(os.environ)
        recovered, recovery_error = _recover_transactions(
            home,
            allow_host_repair=allow_host_repair,
            plugin_data=data,
        )
        if recovery_error:
            return False, recovery_error
        if not recovered:
            return True, "no interrupted update"
        if current_plugin_root is not None and not current_plugin_root.exists():
            return False, "recovered checkout but loaded host bootstrap is unavailable"
        if (
            current_plugin_root is not None
            and _plugin_version(current_plugin_root) != _plugin_version(home)
        ):
            return False, "recovered checkout requires an explicit bootstrap migration"
        runtime, runtime_reason = install_runtime_append_only(
            home,
            _runtime_install_environment(home),
            plugin_data=data,
        )
        if runtime is None:
            return False, f"recovered checkout runtime verification failed: {runtime_reason}"
        return True, "recovered interrupted update"
    finally:
        _release_update_lock(handle)


def install_update(
    home: Path,
    branch: str,
    expected_commit: str,
    current_plugin_root: Path | None,
    *,
    lock_timeout: float | None = None,
    plugin_data: Path | None = None,
    allow_bootstrap_change: bool = False,
) -> tuple[bool, str]:
    data = plugin_data or canonical_plugin_data(os.environ)
    lock_started = time.monotonic()
    lock_handle, lock_error = _acquire_update_lock(home, timeout=lock_timeout)
    if lock_handle is None:
        return False, str(lock_error)
    lock_waited = time.monotonic() - lock_started
    try:
        recovered, recovery_error = _recover_transactions(
            home,
            allow_host_repair=allow_bootstrap_change,
            plugin_data=data,
        )
        if recovery_error:
            _release_update_lock(lock_handle)
            return False, recovery_error
        eligible = _eligible_checkout(home, branch)
    except (OSError, subprocess.TimeoutExpired) as error:
        _release_update_lock(lock_handle)
        return False, f"could not inspect managed checkout: {error}"
    if eligible is None:
        _release_update_lock(lock_handle)
        return False, "managed checkout is dirty, unofficial, or diverged"
    local_commit, _ = eligible
    if not COMMIT_RE.fullmatch(expected_commit):
        _release_update_lock(lock_handle)
        return False, "invalid expected commit"
    home_bootstrap = _plugin_version(home)
    home_runtime = _runtime_version(home)
    loaded_bootstrap = _plugin_version(current_plugin_root) if current_plugin_root else None
    if (
        home_bootstrap is None
        or RELEASE_VERSION_RE.fullmatch(home_bootstrap) is None
        or home_runtime is None
    ):
        _release_update_lock(lock_handle)
        return False, "managed checkout has no valid release identity"
    if not allow_bootstrap_change and loaded_bootstrap is None:
        _release_update_lock(lock_handle)
        return False, "current host bootstrap is unavailable"
    if (
        not allow_bootstrap_change
        and loaded_bootstrap != home_bootstrap
    ):
        _release_update_lock(lock_handle)
        return False, "loaded host and managed checkout require a curl bootstrap migration"
    if not allow_bootstrap_change and current_plugin_root is not None:
        loaded_manifest = _bootstrap_manifest(current_plugin_root)
        home_manifest = _bootstrap_manifest(home)
        if loaded_manifest is None or loaded_manifest != home_manifest:
            _release_update_lock(lock_handle)
            return False, "loaded host bootstrap bytes do not match the managed checkout"

    if local_commit == expected_commit:
        _release_update_lock(lock_handle)
        return True, "already updated by another process"
    if lock_waited > MAX_WAIT_BEFORE_NEW_UPDATE_SECONDS:
        _release_update_lock(lock_handle)
        return False, "concurrent update ended without installing the expected commit"

    try:
        transaction = Path(tempfile.mkdtemp(prefix=".codex-science-update-", dir=home.parent))
    except OSError as error:
        _release_update_lock(lock_handle)
        return False, f"could not create update transaction: {error}"
    candidate = transaction / "candidate"
    previous = transaction / "previous"
    failed = transaction / "failed"
    previous_moved = False
    restored = False
    update_succeeded = False
    bootstrap_migration = False
    try:
        clone = _run(
            [
                "git",
                "clone",
                "--quiet",
                "--filter=blob:none",
                "--branch",
                branch,
                "--single-branch",
                OFFICIAL_HTTPS_REMOTE,
                str(candidate),
            ],
            timeout=180,
        )
        if clone.returncode != 0:
            return False, "candidate clone failed"
        candidate_commit = _git_output(candidate, ["rev-parse", "HEAD"])
        if candidate_commit != expected_commit:
            return False, "official branch moved after approval; retry the update"
        ancestry = _run(
            ["git", "-C", str(candidate), "merge-base", "--is-ancestor", local_commit, expected_commit]
        )
        if ancestry.returncode != 0:
            return False, "candidate is not a fast-forward descendant"
        # Only issue a missing current-runtime receipt after the exact official
        # candidate proves that the local commit is part of its history. A
        # locally forged origin/main tracking ref must never mint a selectable
        # runtime before this ancestry gate.
        current_runtime, current_runtime_reason = install_runtime_append_only(
            home,
            _runtime_install_environment(
                home,
                host_root=(
                    current_plugin_root if not allow_bootstrap_change else None
                ),
            ),
            plugin_data=data,
        )
        if current_runtime is None and not allow_bootstrap_change:
            return False, (
                "current runtime preservation failed: "
                f"{current_runtime_reason}"
            )
        candidate_bootstrap = _plugin_version(candidate)
        candidate_runtime = _runtime_version(candidate)
        if (
            candidate_bootstrap is None
            or RELEASE_VERSION_RE.fullmatch(candidate_bootstrap) is None
            or candidate_runtime is None
        ):
            return False, "candidate has no valid release identity"
        changed_paths = _changed_paths(candidate, local_commit, expected_commit)
        base_neutral = _release_neutral_policy(candidate, local_commit)
        candidate_neutral = _release_neutral_policy(candidate, expected_commit)
        base_bootstrap = _release_bootstrap_policy(candidate, local_commit)
        candidate_bootstrap_policy = _release_bootstrap_policy(
            candidate, expected_commit
        )
        if (
            changed_paths is None
            or base_neutral is None
            or candidate_neutral is None
            or base_bootstrap is None
            or candidate_bootstrap_policy is None
        ):
            return False, "could not classify candidate changes"
        bootstrap_changed = _bootstrap_change(
            changed_paths, base_bootstrap, candidate_bootstrap_policy
        )
        bootstrap_migration = candidate_bootstrap != home_bootstrap
        if bootstrap_migration:
            if not allow_bootstrap_change:
                return False, (
                    "candidate changes the stable host bootstrap; rerun the curl installer"
                )
            if not _version_advances(home_bootstrap, candidate_bootstrap):
                return False, "candidate bootstrap version is not a monotonic advance"
            if os.environ.get("CODEX_SCIENCE_MIGRATION_ACK") != MIGRATION_ACK_VALUE:
                return False, (
                    "bootstrap migration requires all Codex tasks and the Codex app to be "
                    "closed before the acknowledged curl installer is run"
                )
        elif bootstrap_changed:
            return False, "bootstrap files changed without a new bootstrap version"

        if candidate_runtime == home_runtime:
            if not _cache_neutral_change(
                changed_paths, base_neutral, candidate_neutral
            ):
                return False, "runtime content changed without a new runtime version"
        elif not _version_advances(home_runtime, candidate_runtime):
            return False, "candidate runtime version is not a monotonic advance"

        if not bootstrap_migration:
            host = current_plugin_root or home
            host_contract = _mcp_discovery_contract(host)
            candidate_contract = _mcp_discovery_contract(candidate)
            if host_contract is None or candidate_contract is None:
                return False, "could not verify the MCP discovery contract"
            if candidate_contract != host_contract:
                return False, (
                    "candidate changes the MCP discovery contract; a new bootstrap "
                    "version and curl migration are required"
                )
        if not _candidate_self_check(candidate):
            return False, "candidate self-check failed"

        prepared, preparation_reason = install_runtime_append_only(
            candidate,
            _runtime_install_environment(
                candidate,
                host_root=current_plugin_root if not bootstrap_migration else None,
            ),
            plugin_data=data,
        )
        if prepared is None:
            return False, f"candidate runtime preparation failed: {preparation_reason}"

        def swap_candidate() -> None:
            nonlocal previous_moved
            final_eligible = _eligible_checkout(home, branch)
            if final_eligible is None or final_eligible[0] != local_commit:
                raise RuntimeError("managed checkout changed during validation")
            _journal(transaction, "validated", home)
            _rename_durable(home, previous)
            previous_moved = True
            _journal(transaction, "previous_moved", home)
            _rename_durable(candidate, home)
            _journal(transaction, "candidate_active", home)

        if bootstrap_migration:
            with runtime_cache_lock(
                os.environ,
                plugin_data=data,
                exclusive=True,
                timeout=130.0,
            ):
                allowed, gate_reason = _activation_migration_gate(
                    data, require_ack=True
                )
                if not allowed:
                    return False, gate_reason
                try:
                    swap_candidate()
                    _journal(transaction, "registration_started", home)
                    registered, registration_reason = _register_host_now(home)
                    if not registered:
                        raise RuntimeError(registration_reason)
                    _journal(transaction, "host_registered", home)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
                    if previous_moved:
                        restored = _restore_previous(home, previous, failed)
                        if restored:
                            old_registered, old_reason = _register_host_now(home)
                            if not old_registered:
                                error = RuntimeError(
                                    f"{error}; previous host bootstrap repair failed: {old_reason}"
                                )
                    if previous_moved and not restored:
                        return False, (
                            f"{error}; previous checkout retained at {previous} for recovery"
                        )
                    return False, str(error)
        else:
            swap_candidate()

        _journal(
            transaction,
            "host_registered" if bootstrap_migration else "complete",
            home,
        )
        update_succeeded = True
        return True, "updated"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        if previous_moved:
            restored = _restore_previous(home, previous, failed)
        if previous_moved and not restored:
            return False, f"{error}; previous checkout retained at {previous} for recovery"
        return False, str(error)
    finally:
        if update_succeeded or not previous_moved or restored or not previous.exists():
            shutil.rmtree(transaction, ignore_errors=True)
        _release_update_lock(lock_handle)


def _mode(environment: Mapping[str, str]) -> str:
    value = environment.get("CODEX_SCIENCE_AUTO_UPDATE", "apply").strip().lower()
    return value if value in {"off", "notify", "apply"} else "off"


def _runtime_fallback(
    home: Path,
    plugin_root: Path | None,
    *,
    status: str,
    message: str | None,
) -> RuntimeResolution:
    eligible = _eligible_checkout(home, "main")
    if eligible is not None:
        return RuntimeResolution(status, str(home.resolve()), eligible[0], message, False)
    if plugin_root is not None and plugin_root.is_dir():
        version = _plugin_version(plugin_root) or "loaded-cache"
        return RuntimeResolution(
            status,
            str(plugin_root.resolve()),
            f"cache:{version}",
            message,
            False,
        )
    return RuntimeResolution(status, str(home.resolve()), "unavailable", message, False)


def _should_check(payload: Mapping[str, Any]) -> bool:
    event_name = payload.get("hook_event_name")
    if event_name == "SessionStart":
        return payload.get("source") == "startup"
    if event_name != "UserPromptSubmit":
        return False
    prompt = payload.get("prompt")
    return isinstance(prompt, str) and (
        is_update_request(prompt) or is_activation_request(prompt)
    )


def resolve_runtime(
    payload: dict[str, Any], environment: Mapping[str, str]
) -> RuntimeResolution:
    event_name = payload.get("hook_event_name")
    explicit = (
        event_name == "UserPromptSubmit"
        and isinstance(payload.get("prompt"), str)
        and is_update_request(payload["prompt"])
    )
    home = Path(environment.get("CODEX_SCIENCE_HOME", str(DEFAULT_HOME))).expanduser()
    plugin_root_value = environment.get("PLUGIN_ROOT")
    plugin_root = Path(plugin_root_value).expanduser() if plugin_root_value else None
    plugin_data_value = environment.get("PLUGIN_DATA") or environment.get(
        "CLAUDE_PLUGIN_DATA"
    )
    plugin_data = Path(plugin_data_value) if plugin_data_value else None
    interrupted = tuple(home.parent.glob(".codex-science-update-*"))
    if interrupted:
        repaired, reason = repair_interrupted_update(
            home,
            plugin_root,
            lock_timeout=DISPATCH_LOCK_WAIT_SECONDS,
            plugin_data=plugin_data,
        )
        if not repaired:
            return _runtime_fallback(
                home,
                plugin_root,
                status="recovery-failed",
                message=(
                    "Codex Science · 중단된 업데이트를 복구하지 못해 현재 검증된 버전으로 "
                    f"계속합니다. 다시 설치가 필요합니다: {reason}"
                ),
            )

    mode = _mode(environment)
    if not _should_check(payload) or (mode == "off" and not explicit):
        return _runtime_fallback(home, plugin_root, status="current", message=None)
    if plugin_data is None:
        return _runtime_fallback(
            home,
            plugin_root,
            status="offline-last-good",
            message="Codex Science · 업데이트 상태 저장소를 사용할 수 없어 현재 검증된 버전으로 계속합니다.",
        )
    status = get_status(
        home,
        plugin_data,
        "main",
        force=(
            explicit
            or event_name == "SessionStart"
            or (
                event_name == "UserPromptSubmit"
                and isinstance(payload.get("prompt"), str)
                and is_activation_request(payload["prompt"])
            )
        ),
    )
    if status is None:
        eligible = _eligible_checkout(home, "main")
        if eligible is None:
            return _runtime_fallback(
                home,
                plugin_root,
                status="repair-required",
                message=(
                    "Codex Science · 관리 설치가 수정되었거나 공식 main과 달라서 자동 업데이트를 "
                    "건너뛰고 로드된 검증 버전으로 계속합니다. 설치 명령을 다시 실행하세요."
                ),
            )
        return _runtime_fallback(
            home,
            plugin_root,
            status="offline-last-good",
            message=(
                f"Codex Science · 업데이트 서버에 연결하지 못해 검증된 {eligible[0][:8]} 버전으로 "
                "계속합니다."
            ),
        )
    if not status.update_available:
        return RuntimeResolution(
            "current",
            str(home.resolve()),
            status.local_commit,
            (
                f"Codex Science · 이미 최신 버전 {status.local_commit[:8]}입니다."
                if explicit
                else None
            ),
            False,
        )
    if mode == "notify" and not explicit:
        return RuntimeResolution(
            "update-available",
            str(home.resolve()),
            status.local_commit,
            (
                f"Codex Science · 새 버전 {status.remote_commit[:8]}을 사용할 수 있습니다. "
                "자동 적용을 끈 상태입니다."
            ),
            False,
        )
    if plugin_root is None:
        return _runtime_fallback(
            home,
            plugin_root,
            status="update-failed",
            message="Codex Science · 현재 플러그인 경로를 확인할 수 없어 기존 버전으로 계속합니다.",
        )
    success, reason = install_update(
        home,
        "main",
        status.remote_commit,
        plugin_root,
        lock_timeout=DISPATCH_LOCK_WAIT_SECONDS,
        plugin_data=plugin_data,
    )
    if not success:
        return _runtime_fallback(
            home,
            plugin_root,
            status="update-failed",
            message=(
                "Codex Science · 업데이트 검증 또는 적용에 실패해 이전 검증 버전으로 "
                f"계속합니다: {reason}"
            ),
        )
    write_cache(
        plugin_data / "update-check.json",
        UpdateStatus(
            status.remote_commit,
            status.remote_commit,
            int(time.time()),
            str(home.resolve()),
            OFFICIAL_HTTPS_REMOTE,
        ),
    )
    return RuntimeResolution(
        "updated",
        str(home.resolve()),
        status.remote_commit,
        (
            f"Codex Science · {status.remote_commit[:8]}로 업데이트했고 이 작업부터 새 runtime을 "
            "사용합니다. 표시된 plugin 버전은 안정 host bootstrap을 나타냅니다."
        ),
        True,
    )


def handle(payload: dict[str, Any], environment: Mapping[str, str]) -> str | None:
    return resolve_runtime(payload, environment).message


def _emit(event_name: str, context: str) -> None:
    json.dump(
        {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}},
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


def manual_update(home: Path, branch: str) -> int:
    """Apply the latest exact commit during an explicit installer rerun."""
    plugin_data = canonical_plugin_data(os.environ)
    repaired, repair_reason = repair_interrupted_update(
        home,
        None,
        lock_timeout=DISPATCH_LOCK_WAIT_SECONDS,
        plugin_data=plugin_data,
        allow_host_repair=True,
    )
    if not repaired:
        print(
            f"Codex Science · 중단된 업데이트 복구 실패 — {repair_reason}",
            file=sys.stderr,
        )
        return 1
    with tempfile.TemporaryDirectory() as tempdir:
        status = get_status(home, Path(tempdir), branch, force=True)
        if status is None:
            print(
                "Codex Science · 공식 main을 확인할 수 없습니다. 관리 설치와 네트워크를 확인하세요.",
                file=sys.stderr,
            )
            return 1
        if not status.update_available:
            print(f"Codex Science · 이미 최신 버전 {status.local_commit[:8]}입니다.")
            return 0
        success, reason = install_update(
            home,
            branch,
            status.remote_commit,
            None,
            lock_timeout=DISPATCH_LOCK_WAIT_SECONDS,
            plugin_data=plugin_data,
            allow_bootstrap_change=True,
        )
        if not success:
            print(f"Codex Science · 업데이트 실패 — {reason}", file=sys.stderr)
            return 1
        print(f"Codex Science · {status.remote_commit[:8]}로 업데이트했습니다.")
        return 0


def self_check() -> int:
    if not is_update_request("Codex Science 업데이트") or not is_official_remote(
        OFFICIAL_HTTPS_REMOTE
    ):
        return 1
    with tempfile.TemporaryDirectory() as tempdir:
        root = Path(tempdir)
        path = root / "cache.json"
        now = int(time.time())
        status = UpdateStatus("a" * 40, "b" * 40, now, "/managed", OFFICIAL_HTTPS_REMOTE)
        write_cache(path, status)
        if read_cache(path, now=now) != status or stat.S_IMODE(path.stat().st_mode) != 0o600:
            return 1
        home = root / "home"
        candidate = root / "candidate"
        previous = root / "previous"
        failed = root / "failed"
        backup = root / "backup"
        loaded = root / "loaded"
        home.mkdir()
        candidate.mkdir()
        (home / "release").write_text("old", encoding="utf-8")
        (candidate / "release").write_text("new", encoding="utf-8")
        shutil.copytree(home, backup)
        shutil.copytree(home, loaded)
        _rename_durable(home, previous)
        _rename_durable(candidate, home)
        if not _restore_previous(home, previous, failed):
            return 1
        if (home / "release").read_text(encoding="utf-8") != "old":
            return 1
        (loaded / "release").write_text("corrupt", encoding="utf-8")
        if not _restore_tree(backup, loaded):
            return 1
        if _directory_manifest(backup) != _directory_manifest(loaded):
            return 1
    print("update hook self-check: ok")
    return 0


def main() -> int:
    if sys.argv[1:] == ["--self-check"]:
        return self_check()
    if len(sys.argv) == 3 and sys.argv[1] == "--candidate-check":
        return 0 if _candidate_self_check(Path(sys.argv[2]).resolve()) else 1
    if len(sys.argv) == 3 and sys.argv[1] == "--register-plugin":
        success, reason = register_plugin_preserving_caches(Path(sys.argv[2]))
        stream = sys.stdout if success else sys.stderr
        print(reason, file=stream)
        return 0 if success else 1
    if len(sys.argv) == 3 and sys.argv[1] == "--ensure-marketplace":
        success, reason = ensure_managed_marketplace(Path(sys.argv[2]))
        stream = sys.stdout if success else sys.stderr
        print(reason, file=stream)
        return 0 if success else 1
    if len(sys.argv) == 4 and sys.argv[1] == "--manual-update":
        return manual_update(Path(sys.argv[2]).expanduser().resolve(), sys.argv[3])
    if sys.argv[1:] == ["--resolve-runtime"]:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0
        if not isinstance(payload, dict):
            return 0
        try:
            resolution = resolve_runtime(payload, os.environ)
        except (OSError, subprocess.TimeoutExpired) as error:
            home = Path(os.environ.get("CODEX_SCIENCE_HOME", str(DEFAULT_HOME))).expanduser()
            plugin_root_value = os.environ.get("PLUGIN_ROOT")
            plugin_root = Path(plugin_root_value) if plugin_root_value else None
            resolution = _runtime_fallback(
                home,
                plugin_root,
                status="update-failed",
                message=f"Codex Science · 업데이트 확인 실패 — 기존 검증 버전으로 계속합니다: {error}",
            )
        print(json.dumps(resolution._asdict(), ensure_ascii=False, sort_keys=True))
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict) or payload.get("hook_event_name") not in {
        "SessionStart",
        "UserPromptSubmit",
    }:
        return 0
    try:
        context = handle(payload, os.environ)
    except (OSError, subprocess.TimeoutExpired):
        return 0
    if context:
        _emit(str(payload["hook_event_name"]), context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
