#!/usr/bin/env python3
"""Check and explicitly apply safe updates for a managed Codex Science install."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any, Mapping, NamedTuple


CHECK_TTL_SECONDS = 24 * 60 * 60
MAX_PRESERVED_CACHE_VERSIONS = 32
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


class UpdateStatus(NamedTuple):
    local_commit: str
    remote_commit: str
    checked_at: int
    checkout: str
    remote_url: str

    @property
    def update_available(self) -> bool:
        return self.local_commit != self.remote_commit


def is_update_request(prompt: str) -> bool:
    return any(pattern.fullmatch(prompt) for pattern in UPDATE_PATTERNS)


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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        temporary.chmod(0o600)
        temporary.replace(path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


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
    return checked_at <= now and now - checked_at <= CHECK_TTL_SECONDS


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
        if _recent_attempt(attempt_path, now=now):
            return None
    _write_attempt(attempt_path, now)
    remote = _run(
        ["git", "-C", str(home), "ls-remote", "--heads", "origin", f"refs/heads/{branch}"],
        timeout=10,
    )
    if remote.returncode != 0 or not remote.stdout.strip():
        return None
    remote_commit = remote.stdout.split()[0].lower()
    if not COMMIT_RE.fullmatch(remote_commit):
        return None
    status = UpdateStatus(local_commit, remote_commit, now, checkout, remote_url)
    write_cache(cache_path, status)
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


def _tracked_manifest(root: Path) -> dict[str, str] | None:
    tracked = _run(["git", "-C", str(root), "ls-files", "-z"], timeout=30)
    if tracked.returncode != 0:
        return None
    manifest: dict[str, str] = {}
    try:
        for value in tracked.stdout.split("\0"):
            if not value:
                continue
            path = root / value
            if path.is_symlink():
                manifest[value] = f"link:{os.readlink(path)}"
            elif path.is_file():
                manifest[value] = _sha256(path)
            elif path.is_dir():
                nested = _directory_manifest(path)
                if nested is None:
                    return None
                for relative, digest in nested.items():
                    manifest[f"{value}/{relative}"] = digest
            else:
                return None
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
            home.rename(failed)
        previous.rename(home)
    except OSError:
        return False
    return home.exists() and not previous.exists()


def _plugin_version(root: Path) -> str | None:
    try:
        payload = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        version = payload["version"]
    except (FileNotFoundError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return version if isinstance(version, str) and version else None


def _candidate_self_check(candidate: Path) -> bool:
    required = (
        ".codex-plugin/plugin.json",
        "hooks/hooks.json",
        "scripts/python_runtime.sh",
        "scripts/science_mcp.py",
        "scripts/science_session_hook.py",
        "scripts/science_update_hook.py",
    )
    if any(not (candidate / relative).is_file() for relative in required):
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
        environment = {**os.environ, "PLUGIN_DATA": tempdir, "CODEX_SCIENCE_AUTO_UPDATE": "off"}
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


def _installed_cache_matches(source: Path) -> bool:
    version = _plugin_version(source)
    if version is None:
        return False
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    cache = codex_home / "plugins" / "cache" / "codex-science" / "codex-science" / version
    source_manifest = _tracked_manifest(source)
    if source_manifest is None:
        return False
    try:
        for relative, digest in source_manifest.items():
            path = cache / relative
            if path.is_symlink():
                actual = f"link:{os.readlink(path)}"
            elif path.is_file():
                actual = _sha256(path)
            else:
                return False
            if actual != digest:
                return False
    except OSError:
        return False
    return True


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


def register_plugin_preserving_caches(source: Path) -> tuple[bool, str]:
    """Register one version while preserving caches pinned by existing Codex tasks."""
    source = Path(source).expanduser().resolve()
    source_version = _plugin_version(source)
    if source_version is None:
        return False, "plugin source has no valid version"
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    cache_root = codex_home / "plugins" / "cache" / "codex-science" / "codex-science"
    try:
        candidates = tuple(cache_root.iterdir())
    except FileNotFoundError:
        candidates = ()
    except OSError as error:
        return False, f"could not inspect existing plugin caches: {error}"
    preserved = [
        path
        for path in candidates
        if not path.is_symlink()
        and path.is_dir()
        and path.name != source_version
        and _plugin_version(path) == path.name
    ]
    if len(preserved) > MAX_PRESERVED_CACHE_VERSIONS:
        return False, "too many existing plugin cache versions to preserve safely"

    backup_root = Path(tempfile.mkdtemp(prefix=".codex-science-cache-preserve-"))
    backups: dict[Path, tuple[Path, dict[str, str]]] = {}
    registration_ok = False
    reason = "plugin registration failed"
    restore_errors: list[str] = []
    try:
        for cache in preserved:
            manifest = _directory_manifest(cache)
            if manifest is None:
                raise OSError(f"could not read existing plugin cache: {cache}")
            backup = backup_root / cache.name
            shutil.copytree(cache, backup, symlinks=True)
            if _directory_manifest(backup) != manifest:
                raise OSError(f"plugin cache backup verification failed: {cache}")
            backups[cache] = (backup, manifest)

        registration = _run(
            ["codex", "plugin", "add", "codex-science@codex-science"], timeout=60
        )
        if registration.returncode != 0:
            reason = registration.stderr.strip() or "plugin registration command failed"
        elif not _installed_cache_matches(source):
            reason = "installed plugin cache verification failed"
        else:
            registration_ok = True
            reason = "registered"
    except (OSError, subprocess.TimeoutExpired) as error:
        reason = str(error)
    finally:
        for destination, (backup, manifest) in backups.items():
            if _directory_manifest(destination) == manifest:
                continue
            if not _restore_tree(backup, destination):
                restore_errors.append(str(destination))
        shutil.rmtree(backup_root, ignore_errors=True)

    if restore_errors:
        return False, "failed to restore pinned plugin caches: " + ", ".join(restore_errors)
    return registration_ok, reason


def install_update(
    home: Path,
    branch: str,
    expected_commit: str,
    current_plugin_root: Path | None,
) -> tuple[bool, str]:
    lock_path = home.parent / ".codex-science-update.lock"
    lock_flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        lock_flags |= os.O_NOFOLLOW
    try:
        lock_descriptor = os.open(lock_path, lock_flags, 0o600)
        os.fchmod(lock_descriptor, 0o600)
    except OSError as error:
        return False, f"could not acquire update lock: {error}"
    lock_handle = os.fdopen(lock_descriptor, "r+")
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_handle.close()
        return False, "another update is already running"
    eligible = _eligible_checkout(home, branch)
    if eligible is None:
        lock_handle.close()
        return False, "managed checkout is dirty, unofficial, or diverged"
    local_commit, _ = eligible
    if not COMMIT_RE.fullmatch(expected_commit):
        lock_handle.close()
        return False, "invalid expected commit"
    loaded_version = _plugin_version(current_plugin_root or home)
    if loaded_version is None:
        lock_handle.close()
        return False, "current plugin root is unavailable"

    transaction = Path(tempfile.mkdtemp(prefix=".codex-science-update-", dir=home.parent))
    candidate = transaction / "candidate"
    previous = transaction / "previous"
    failed = transaction / "failed"
    cache_backup = transaction / "loaded-plugin"
    previous_moved = False
    cache_copied = False
    restored = False
    update_succeeded = False
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
        if not _candidate_self_check(candidate):
            return False, "candidate self-check failed"
        candidate_version = _plugin_version(candidate)
        if candidate_version is None or candidate_version == loaded_version:
            return False, "candidate must use a new plugin cachebuster"

        if current_plugin_root is not None:
            shutil.copytree(current_plugin_root, cache_backup, symlinks=True)
            cache_copied = True
        final_eligible = _eligible_checkout(home, branch)
        if final_eligible is None or final_eligible[0] != local_commit:
            return False, "managed checkout changed during validation"
        home.rename(previous)
        previous_moved = True
        candidate.rename(home)
        registered, registration_reason = register_plugin_preserving_caches(home)
        if not registered:
            raise RuntimeError(f"plugin registration failed: {registration_reason}")
        if current_plugin_root is not None and (
            _directory_manifest(current_plugin_root) != _directory_manifest(cache_backup)
        ):
            if not _restore_tree(cache_backup, current_plugin_root):
                raise RuntimeError("current task cache was not preserved")
        update_succeeded = True
        return True, "updated"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        if previous_moved:
            restored = _restore_previous(home, previous, failed)
            if restored:
                registered, registration_reason = register_plugin_preserving_caches(home)
                if not registered:
                    error = RuntimeError(
                        f"{error}; previous plugin registration could not be verified: "
                        f"{registration_reason}"
                    )
        if cache_copied and current_plugin_root is not None and cache_backup.is_dir():
            if _directory_manifest(current_plugin_root) != _directory_manifest(cache_backup):
                if not _restore_tree(cache_backup, current_plugin_root):
                    error = RuntimeError(f"{error}; current task cache recovery failed")
        if previous_moved and not restored:
            return False, f"{error}; previous checkout retained at {previous} for recovery"
        return False, str(error)
    finally:
        if update_succeeded or not previous_moved or restored or not previous.exists():
            shutil.rmtree(transaction, ignore_errors=True)
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()


def _mode(environment: Mapping[str, str]) -> str:
    value = environment.get("CODEX_SCIENCE_AUTO_UPDATE", "notify").strip().lower()
    return value if value in {"off", "notify"} else "off"


def handle(payload: dict[str, Any], environment: Mapping[str, str]) -> str | None:
    event_name = payload.get("hook_event_name")
    explicit = (
        event_name == "UserPromptSubmit"
        and isinstance(payload.get("prompt"), str)
        and is_update_request(payload["prompt"])
    )
    startup = event_name == "SessionStart" and payload.get("source") == "startup"
    if not explicit and (not startup or _mode(environment) == "off"):
        return None
    home = Path(environment.get("CODEX_SCIENCE_HOME", str(DEFAULT_HOME))).expanduser()
    plugin_data_value = environment.get("PLUGIN_DATA") or environment.get("CLAUDE_PLUGIN_DATA")
    if not plugin_data_value:
        return "Codex Science could not check for updates because plugin data is unavailable."
    plugin_data = Path(plugin_data_value)
    status = (
        get_advertised_status(home, plugin_data, "main")
        if explicit
        else get_status(home, plugin_data, "main")
    )
    if status is None:
        if not explicit:
            return None
        discovered = get_status(home, plugin_data, "main", force=True)
        if discovered is not None and discovered.update_available:
            return (
                f"Codex Science found update {discovered.remote_commit[:8]} and advertised it now. "
                "Say 'Codex Science 업데이트' again to approve that exact commit."
            )
        if discovered is not None:
            return "Codex Science is already up to date."
        return "Codex Science could not verify a clean managed official checkout; no update was applied."
    if not status.update_available:
        return "Codex Science is already up to date." if explicit else None
    if not explicit:
        return (
            f"A Codex Science update is available ({status.local_commit[:8]} -> "
            f"{status.remote_commit[:8]}). Say 'Codex Science 업데이트' to stage, verify, and "
            "install that exact commit. The current task remains pinned to its loaded version."
        )
    plugin_root_value = environment.get("PLUGIN_ROOT")
    if not plugin_root_value:
        return "Codex Science update was not applied: current plugin root is unavailable."
    plugin_root = Path(plugin_root_value)
    success, reason = install_update(home, "main", status.remote_commit, plugin_root)
    if not success:
        return f"Codex Science update was not applied: {reason}. The previous install remains active."
    write_cache(
        Path(plugin_data_value) / "update-check.json",
        UpdateStatus(
            status.remote_commit,
            status.remote_commit,
            int(time.time()),
            str(home.resolve()),
            OFFICIAL_HTTPS_REMOTE,
        ),
    )
    return (
        "Codex Science installed the verified update for the next new Codex task and preserved "
        "the current task's loaded plugin cache."
    )


def _emit(event_name: str, context: str) -> None:
    json.dump(
        {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": context}},
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")


def manual_update(home: Path, branch: str) -> int:
    """Apply the latest exact commit during an explicit installer rerun."""
    with tempfile.TemporaryDirectory() as tempdir:
        status = get_status(home, Path(tempdir), branch, force=True)
        if status is None:
            print("managed checkout is dirty, unofficial, or could not reach the official branch", file=sys.stderr)
            return 1
        if not status.update_available:
            print("Codex Science is already up to date.")
            return 0
        success, reason = install_update(home, branch, status.remote_commit, None)
        if not success:
            print(f"Codex Science update failed: {reason}", file=sys.stderr)
            return 1
        print(f"Codex Science updated to {status.remote_commit}.")
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
        home.rename(previous)
        candidate.rename(home)
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
