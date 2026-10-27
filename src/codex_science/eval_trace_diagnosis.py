"""Read-only, deterministic diagnosis of a recorded Codex evaluation trace.

Every number is a pattern match over recorded command text; nothing from the
trace is executed and trace content is treated as untrusted text.
"""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping

from .literature_evaluation_runner import _ANY_PLUGIN_CACHE_PATH, _plugin_cache_patterns

SCHEMA_VERSION = 1
MAX_EXAMPLES = 5
MAX_COMMAND_CHARS = 200
REPEAT_THRESHOLD = 3
_MAX_LINE_BYTES = 1 << 20
_MAX_FILE_BYTES = 64 << 20
_MAX_MANIFESTS = 200
EVIDENCE_BOUNDARY = (
    "Counts are pattern matches over recorded commands, not judgments of scientific quality; "
    "regexes can miss shell indirection (variables, eval, scripts that run other commands).")

_SCRIPT_RE = re.compile(r"(?<![\w.-])(?:[\w.$~{}-]*/)*scripts/(?P<name>[\w.-]+\.py)(?![\w.-])")
_SOURCE_TAIL = r"/(?:scripts|src)/[^\s\"'<>;|&]+"
_MANIFEST_WRITE_RES = tuple(re.compile(pattern) for pattern in (
    r"\bsed\b[^|;&\n]*\s-[A-Za-z]*i[^|;&\n]*manifest\.json",
    r">>?\s*['\"]?[^\s'\"<>|;&]*manifest\.json",
    r"\btee\b[^|;&\n]*manifest\.json",
    r"open\([^)\n]*manifest\.json[^)\n]*['\"][wax]\+?b?['\"]",
    r"manifest\.json['\"]?\s*\)\s*\.write_(?:text|bytes)\(",
))
_SHELLS = {"bash", "sh", "zsh", "dash"}
_SEGMENT_SPLIT = {";", "&&", "||", "|", "&"}


_PLUGIN_ROOT_RE = re.compile(
    r"[^\s\"'<>;|&=:]*plugins/cache/[A-Za-z0-9][A-Za-z0-9._-]*/codex-science/[^/\\\s\"'<>;|&]+(?=/|$|[\\\s\"'<>;|&])")
_HEREDOC_RE = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|\\?([\w.-]+))")
_REDIRECT_RE = re.compile(r"^\d*(?:>>?|<)")
_FD_DUP_RE = re.compile(r"\d*>&(?:\d+|-)|&>>?")


def _plugin_relative(text: str) -> str:
    """Replace plugin cache roots (machine-specific prefixes) with `<plugin>`."""
    return _PLUGIN_ROOT_RE.sub("<plugin>", text)


def _short(text: str) -> str:
    return _plugin_relative(text)[:MAX_COMMAND_CHARS]


def _normalize(command: str) -> str:
    return " ".join(_plugin_relative(command).split())


def _strip_heredocs(command: str) -> str:
    """Drop heredoc bodies (data written by the command, not commands it runs)."""
    kept: list[str] = []
    delimiters: list[str] = []
    for line in command.split("\n"):
        if delimiters:
            if line.strip() == delimiters[0]:
                delimiters.pop(0)
            continue
        kept.append(line)
        delimiters.extend(next(g for g in match.groups() if g) for match in _HEREDOC_RE.finditer(line))
    return "\n".join(kept)


def _strip_redirects(segment: list[str]) -> list[str]:
    result: list[str] = []
    skip = False
    for token in segment:
        if skip:
            skip = False
        elif _REDIRECT_RE.match(token):
            skip = _REDIRECT_RE.sub("", token, count=1) == "" or token.endswith(("<<", "<<-"))
        else:
            result.append(token)
    return result


def _finite_t(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            if math.isfinite(value) and value >= 0:
                return float(value)
        except (OverflowError, TypeError, ValueError):
            pass
    return None


def _bounded_lines(path: Path) -> Iterable[bytes | None]:
    """Yield lines; None marks a line over the size cap (rest of it is skipped)."""
    with path.open("rb") as handle:
        while True:
            line = handle.readline(_MAX_LINE_BYTES + 1)
            if not line:
                return
            if len(line) > _MAX_LINE_BYTES and not line.endswith(b"\n"):
                while True:
                    chunk = handle.readline(_MAX_LINE_BYTES)
                    if not chunk or chunk.endswith(b"\n"):
                        break
                yield None
            else:
                yield line


def _regular_text(path: Path) -> str | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _tokens(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return command.split()


def _segments(command: str, depth: int = 0) -> list[list[str]]:
    """Split a command into simple-command token lists, unwrapping `bash -lc '...'`."""
    result: list[list[str]] = []
    current: list[str] = []
    command = _FD_DUP_RE.sub(" ", _strip_heredocs(command)).replace("\n", ";")
    for token in _tokens(command) + [";"]:
        if token in _SEGMENT_SPLIT or set(token) <= set(";&|"):
            current = _strip_redirects(current)
            if current:
                result.append(current)
            current = []
        else:
            current.append(token)
    expanded: list[list[str]] = []
    for segment in result:
        name = os.path.basename(segment[0])
        if depth < 3 and name in _SHELLS:
            inner = next((segment[i + 1] for i, arg in enumerate(segment[:-1])
                          if arg.startswith("-") and "c" in arg[1:] and not arg.startswith("--")), None)
            if inner is not None:
                expanded.extend(_segments(inner, depth + 1))
                continue
        expanded.append(segment)
    return expanded


def _read_paths(command: str) -> list[str]:
    """Operands of read commands (cat, head, tail, sed, nl, less, rg, grep, awk) outside heredoc bodies."""
    paths: list[str] = []
    for segment in _segments(command):
        name = os.path.basename(segment[0])
        args = segment[1:]
        if name == "cat":
            paths.extend(arg for arg in args if not arg.startswith("-") and arg != "-")
        elif name in {"head", "tail"}:
            skip = False
            for arg in args:
                if skip:
                    skip = False
                elif arg in {"-n", "-c"}:
                    skip = True
                elif not arg.startswith("-") and not arg.startswith("+"):
                    paths.append(arg)
        elif name in {"sed", "nl", "less"} and not any(
                arg.startswith("-") and not arg.startswith("--") and "i" in arg for arg in args):
            positional = [arg for arg in args if not arg.startswith("-")]
            paths.extend(positional[1:] if name == "sed" else positional)
        elif name in {"rg", "grep", "awk"}:
            positional, skip = [], False
            for arg in args:
                if skip:
                    skip = False
                elif arg in {"-e", "-g", "--glob", "-t", "--type", "-m", "--max-count", "-A", "-B", "-C", "-f"}:
                    skip = True
                elif not arg.startswith("-"):
                    positional.append(arg)
            # rg --files has no pattern operand; otherwise the first operand is a pattern or program.
            paths.extend(positional if "--files" in args else positional[1:])
    return paths


def _plugin_source_paths(text: str) -> list[str]:
    """Plugin-cache scripts/ or src/ paths named in `text`."""
    found: list[str] = []
    for marketplace in sorted({m.group("marketplace") for m in _ANY_PLUGIN_CACHE_PATH.finditer(text)}):
        version_re, _ = _plugin_cache_patterns(f"codex-science@{marketplace}")
        pattern = re.compile(version_re.pattern + _SOURCE_TAIL)
        found.extend(m.group(0) for m in pattern.finditer(text))
    return found


def _is_help(command: str) -> bool:
    return bool(re.search(r"(?<!\S)(?:--help|-h)(?!\S)", command))


def _example(command: str, item: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"command": _short(command), "item_id": item.get("id"), "t": item.get("t"), **extra}


def _section(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(rows), "examples": rows[:MAX_EXAMPLES]}


def collect_items(lines: Iterable[bytes | str | None]) -> dict[str, Any]:
    """Parse event lines (wrapped `{"t","event"}` or bare); tolerate malformed lines."""
    items: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    malformed = 0
    parsed = 0
    terminal = None
    for number, line in enumerate(lines):
        if line is None:
            malformed += 1
            continue
        try:
            record = json.loads(line)
        except (json.JSONDecodeError, UnicodeError, TypeError, RecursionError):
            malformed += 1
            continue
        if not isinstance(record, Mapping):
            malformed += 1
            continue
        timestamp_invalid = "t" in record and record["t"] is not None and _finite_t(record["t"]) is None
        if timestamp_invalid:
            malformed += 1
        parsed += 1
        t = None
        event = record
        if "event" in record:
            t = _finite_t(record.get("t"))
            event = record["event"]
        if not isinstance(event, Mapping):
            malformed += not timestamp_invalid
            continue
        event_type = event.get("type")
        if not isinstance(event_type, str):
            malformed += not timestamp_invalid
            continue
        if "status" in event and event["status"] is not None and not isinstance(event["status"], str):
            malformed += not timestamp_invalid
            continue
        if event_type in {"turn.completed", "turn.failed"}:
            terminal = "completed" if event_type == "turn.completed" else "failed"
        if not event_type.startswith("item."):
            continue
        item = event.get("item")
        if not isinstance(item, Mapping):
            malformed += not timestamp_invalid
            continue
        item_type = item.get("type")
        if not isinstance(item_type, str):
            malformed += not timestamp_invalid
            continue
        if item_type not in {"command_execution", "file_change"}:
            continue
        if "status" in item and item["status"] is not None and not isinstance(item["status"], str):
            malformed += not timestamp_invalid
            continue
        if item_type == "command_execution":
            if "command" in item and not isinstance(item["command"], str):
                malformed += not timestamp_invalid
                continue
            if ("exit_code" in item and item["exit_code"] is not None
                    and (not isinstance(item["exit_code"], int) or isinstance(item["exit_code"], bool))):
                malformed += not timestamp_invalid
                continue
        if item_type == "file_change" and "changes" in item:
            changes = item["changes"]
            if not isinstance(changes, list) or any(
                    not isinstance(change, Mapping)
                    or ("path" in change and not isinstance(change["path"], str))
                    for change in changes):
                malformed += not timestamp_invalid
                continue
        raw_id = item.get("id")
        slot = f"id:{raw_id}" if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool) else f"line:{number}"
        row = items.get(slot)
        if row is None:
            row = items[slot] = {"id": raw_id if slot.startswith("id:") else None, "type": item["type"],
                                "command": "", "exit_code": None, "output": "", "changes": [],
                                "t": t, "last_t": t}
            order.append(slot)
        if t is not None:
            row["t"] = t if row["t"] is None else min(row["t"], t)
            row["last_t"] = t if row["last_t"] is None else max(row["last_t"], t)
        if isinstance(item.get("command"), str):
            row["command"] = item["command"]
        exit_code = item.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            row["exit_code"] = exit_code
        if isinstance(item.get("aggregated_output"), str):
            row["output"] = item["aggregated_output"]
        if isinstance(item.get("changes"), list):
            row["changes"] = [c for c in item["changes"] if isinstance(c, Mapping)]
    return {"items": [items[slot] for slot in order], "malformed_lines": malformed,
            "event_lines": parsed, "turn_terminal": terminal}


def _json_object(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    text = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*)\n```", text, re.DOTALL)
    try:
        value = json.loads(fenced.group(1) if fenced else text)
    except (json.JSONDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _inside(root: Path, candidate: str, base: Path) -> Path | None:
    """Lexically resolve `candidate` against `base`; None when it leaves `root`."""
    if not candidate or "\x00" in candidate:
        return None
    joined = os.path.normpath(os.path.join(base, candidate))
    root_text = os.path.normpath(root)
    if joined != root_text and not joined.startswith(root_text + os.sep):
        return None
    return Path(joined)


def _lost_artifacts(project: Path | None, record: Mapping[str, Any] | None) -> dict[str, Any]:
    if project is None or not project.is_dir():
        return {"checked": False, "count": 0, "examples": []}
    named: list[tuple[str, str, Path]] = []
    if record is not None and isinstance(record.get("deliverables"), list):
        named.extend(("completion_record", p, project) for p in record["deliverables"] if isinstance(p, str))
    manifests: list[Path] = []
    for directory, subdirs, files in os.walk(project, followlinks=False):
        subdirs.sort()
        if "manifest.json" in files and len(manifests) < _MAX_MANIFESTS:
            manifests.append(Path(directory) / "manifest.json")
    for manifest in manifests:
        value = _json_object(_regular_text(manifest))
        for entry in (value or {}).get("artifacts", []) if isinstance((value or {}).get("artifacts"), list) else []:
            path = entry.get("path") if isinstance(entry, Mapping) else entry
            if isinstance(path, str):
                named.append((str(manifest.relative_to(project)), path, manifest.parent))
    rows = []
    for source, path, base in named:
        resolved = _inside(project, path, base)
        if resolved is None:
            rows.append({"path": _short(path), "source": source, "reason": "outside_project"})
        elif not os.path.lexists(resolved):
            rows.append({"path": _short(path), "source": source, "reason": "missing"})
    return {"checked": True, "count": len(rows), "examples": rows[:MAX_EXAMPLES]}


def _premature_closure(terminal: str | None, receipt: Mapping[str, Any] | None,
                       record: Mapping[str, Any] | None) -> dict[str, Any]:
    reasons: list[str] = []
    no_artifacts = False
    if terminal == "completed":
        report = receipt.get("completion_report") if receipt else None
        if isinstance(report, Mapping):
            runs = report.get("runs")
            if report.get("status") == "no_artifacts" or runs == []:
                no_artifacts = True
            elif isinstance(runs, list):
                for run in runs:
                    outcome = run.get("outcome") if isinstance(run, Mapping) else None
                    if outcome != "completed":
                        name = run.get("run_id") if isinstance(run, Mapping) else None
                        reasons.append(_short(f"completion_report run {name}: outcome {outcome}"))
            else:
                reasons.append(_short(f"completion_report status {report.get('status', 'unknown')}"))
        elif report is not None:
            reasons.append("completion_report is not an object")
        if record is not None and (not isinstance(record.get("status"), str)
                                   or record.get("status") not in {"completed", "quick_answer"}):
            reasons.append(_short(f"completion record status {record.get('status')!r} is not 'completed'"))
    return {"value": bool(reasons), "turn_completed": terminal == "completed", "no_artifacts": no_artifacts,
            "reasons": reasons[:MAX_EXAMPLES], "reason_count": len(reasons)}


def diagnose_items(parsed: Mapping[str, Any], *, receipt: Mapping[str, Any] | None = None,
                   record: Mapping[str, Any] | None = None, project: Path | None = None) -> dict[str, Any]:
    items = parsed["items"]
    commands = [i for i in items if i["type"] == "command_execution" and i["command"]]
    failed = {"plugin_script": [], "benign_search_miss": [], "other": []}
    reads: dict[str, list[dict[str, Any]]] = {}
    plugin_reads: list[dict[str, Any]] = []
    manifest_edits: list[dict[str, Any]] = []
    phases: dict[str, list[float | None]] = {}
    command_counts: dict[str, list[Any]] = {}
    for item in commands:
        raw = item["command"]
        command = _strip_heredocs(raw)
        names = [m.group("name") for m in _SCRIPT_RE.finditer(command)]
        norm = _normalize(raw)
        command_counts.setdefault(norm, []).append(item)
        exit_code = item["exit_code"]
        if exit_code not in (None, 0):
            segments = _segments(command)
            last = os.path.basename(segments[-1][0]) if segments else ""
            if exit_code == 1 and last in {"rg", "grep"}:
                failed["benign_search_miss"].append(_example(raw, item, exit_code=exit_code))
            elif names:
                failed["plugin_script"].append(_example(raw, item, exit_code=exit_code, script=names[0]))
            else:
                failed["other"].append(_example(raw, item, exit_code=exit_code))
        for name in dict.fromkeys(names):
            span = phases.setdefault(name, [item["t"], item["last_t"]])
            if item["t"] is not None:
                span[0] = item["t"] if span[0] is None else min(span[0], item["t"])
            if item["last_t"] is not None:
                span[1] = item["last_t"] if span[1] is None else max(span[1], item["last_t"])
        for path in _read_paths(command):
            reads.setdefault(_plugin_relative(path), []).append(item)
        if not _is_help(command):
            read_set = set(_read_paths(command))
            for source in _plugin_source_paths(command):
                if any(source in path for path in read_set):
                    plugin_reads.append(_example(raw, item, path=_short(source)))
                    break
        if not names and any(r.search(raw) for r in _MANIFEST_WRITE_RES):
            manifest_edits.append(_example(raw, item, via="command"))
    for item in items:
        if item["type"] != "file_change":
            continue
        for change in item["changes"]:
            path = change.get("path")
            if isinstance(path, str) and os.path.basename(path) == "manifest.json":
                manifest_edits.append({"command": None, "item_id": item["id"], "t": item["t"],
                                       "via": "file_change", "path": _short(path)})
    repeated_commands = [(c, -n) for n, c in sorted((-len(v), c) for c, v in command_counts.items()
                                                    if len(v) >= REPEAT_THRESHOLD)]
    repeated_reads = [(p, -n) for n, p in sorted((-len(v), p) for p, v in reads.items()
                                                 if len(v) >= REPEAT_THRESHOLD)]
    phase_rows = [row for *_, row in sorted(
        (span[0] is None, span[0] or 0.0, name, {"script": name, "first_t": span[0], "last_t": span[1]})
        for name, span in phases.items())]
    return {
        "schema_version": SCHEMA_VERSION,
        "event_lines": parsed["event_lines"],
        "malformed_lines": parsed["malformed_lines"],
        "command_count": len(commands),
        "failed_tool_use": {
            "count": sum(len(rows) for rows in failed.values()),
            **{kind: _section(rows) for kind, rows in failed.items()}},
        "repeated_exploration": {
            "threshold": REPEAT_THRESHOLD,
            "commands": {"count": len(repeated_commands),
                         "examples": [{"command": _short(c), "count": n} for c, n in repeated_commands[:MAX_EXAMPLES]]},
            "file_reads": {"count": len(repeated_reads),
                           "examples": [{"path": _short(p), "count": n} for p, n in repeated_reads[:MAX_EXAMPLES]]}},
        "plugin_source_reads": _section(plugin_reads),
        "manifest_hand_edits": _section(manifest_edits),
        "lost_artifacts": _lost_artifacts(project, record),
        "premature_closure": _premature_closure(parsed["turn_terminal"], receipt, record),
        "phase_seconds": phase_rows,
        "evidence_boundary": EVIDENCE_BOUNDARY,
    }


def diagnose_events(path: Path) -> dict[str, Any]:
    """Diagnose a bare events file (no receipt, completion record or project)."""
    return diagnose_items(collect_items(_bounded_lines(path)))


def diagnose_task_dir(task_dir: Path) -> dict[str, Any]:
    """Diagnose a directory written by scripts/run_literature_evaluation.py."""
    parsed = collect_items(_bounded_lines(task_dir / "events.jsonl"))
    receipt = _json_object(_regular_text(task_dir / "receipt.json"))
    record = _json_object(_regular_text(task_dir / "last.md"))
    project = task_dir / "project"
    return diagnose_items(parsed, receipt=receipt, record=record,
                          project=project if project.is_dir() and not project.is_symlink() else None)
