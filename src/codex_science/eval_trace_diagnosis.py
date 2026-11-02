"""Read-only, deterministic diagnosis of a recorded Codex evaluation trace.

Every number is a pattern match over recorded command text; nothing from the
trace is executed and trace content is treated as untrusted text.
"""
from __future__ import annotations

import bisect
import json
import math
import os
import re
import shlex
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping

from .literature_evaluation_runner import _ANY_PLUGIN_CACHE_PATH

SCHEMA_VERSION = 1
MAX_EXAMPLES = 5
MAX_COMMAND_CHARS = 200
REPEAT_THRESHOLD = 3
_MAX_LINE_BYTES = 1 << 20
_MAX_FILE_BYTES = 64 << 20
_MAX_MANIFESTS = 200
_MAX_SCAN_CHARS = 8192  # per command: shell-word splitting is pure Python, so only this much is split
EVIDENCE_BOUNDARY = (
    "Counts are pattern matches over recorded commands, not judgments of scientific quality; "
    "regexes can miss shell indirection (variables, eval, scripts that run other commands).")

_SCRIPT_RE = re.compile(r"(?:(?<=/)|(?<![\w.-]))scripts/(?P<name>[\w.-]+\.py)(?![\w.-])")
_SOURCE_TAIL = r"/(?:scripts|src)/[^\s\"'<>;|&]+"
_MANIFEST = "manifest.json"
# Linear as written; the sed, tee and open( patterns are matched per run in _writes_manifest.
_MANIFEST_WRITE_RES = tuple(re.compile(pattern) for pattern in (
    r">>?\s*['\"]?[^\s'\"<>|;&]*manifest\.json",
    r"manifest\.json['\"]?\s*\)\s*\.write_(?:text|bytes)\(",
))
_SED_RE = re.compile(r"\bsed\b")
_SED_IN_PLACE_RE = re.compile(r"\s-[A-Za-z]*?i")
_TEE_RE = re.compile(r"\btee\b")
_WRITE_MODE_RE = re.compile(r"['\"][wax]\+?b?['\"]")
_RUN_END_RE = re.compile(r"[|;&\n]")
_OPEN_RUN_END_RE = re.compile(r"[)\n]")
_SHELLS = {"bash", "sh", "zsh", "dash"}
_SEGMENT_SPLIT = {";", "&&", "||", "|", "&"}


_PLUGIN_ROOT_RE = re.compile(
    r"(?<![^\s\"'<>;|&=:])[^\s\"'<>;|&=:]*plugins/cache/[A-Za-z0-9][A-Za-z0-9._-]*/codex-science/[^/\\\s\"'<>;|&]+(?=/|$|[\\\s\"'<>;|&])")
_HEREDOC_RE = re.compile(r"-?[^\S\n]*(?:'([^'\n]+)'|\"([^\"\n]+)\"|\\?([\w.-]+))")
_SHELL_ACTIVE_RE = re.compile(r"[\\'\"#()<;&|\s]")
_DOUBLE_QUOTE_STOP_RE = re.compile(r'[\\"]')
_DOUBLE_QUOTE_ESCAPE_RE = re.compile(r'\\([\\"$`\n])|\\.', re.DOTALL)
_PLAIN_RE = re.compile(r"[^'\"\\\s;&|()<>]+")
_C_FLAG_RE = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
_REDIRECT_RE = re.compile(r"^\d*(?:>>?|<)")
_FD_DUP_RE = re.compile(r"\d*>&(?:\d+|-)|&>>?")


def _plugin_relative(text: str) -> str:
    """Replace plugin cache roots (machine-specific prefixes) with `<plugin>`."""
    return _PLUGIN_ROOT_RE.sub("<plugin>", text)


def _short(text: str) -> str:
    return _plugin_relative(text)[:MAX_COMMAND_CHARS]


def _normalize(command: str) -> str:
    return " ".join(_plugin_relative(command).split())


def _double_quoted_end(text: str, index: int) -> int:
    """Index of the `"` closing a double-quoted word whose text starts at `index` (or len(text))."""
    while True:
        found = _DOUBLE_QUOTE_STOP_RE.search(text, index)
        if found is None:
            return len(text)
        if found.group() == '"':
            return found.start()
        index = found.start() + 2


def _payload(text: str, quote: int, depth: int) -> tuple[list[tuple[int, int]], int]:
    """Heredoc cuts inside the shell code of the word starting at `text[quote]`, and the index after it.

    The word is decoded as the shell would (quoted and unquoted parts joined, as in `'a'"'"'b'`)
    and each cut removes only the decoded characters it covers, so the quotes stay balanced.
    """
    parts: list[str] = []
    # (decoded start, decoded length, raw start with any escaping backslash, raw start, raw end)
    pieces: list[tuple[int, int, int, int, int]] = []
    decoded = 0

    def take(start: int, end: int, prefix: int = 0) -> None:
        nonlocal decoded
        if end > start:
            pieces.append((decoded, end - start, start - prefix, start, end))
            parts.append(text[start:end])
            decoded += end - start

    index, size = quote, len(text)
    while index < size:
        char = text[index]
        if char == "'":
            end = text.find("'", index + 1)
            end = size if end < 0 else end
            take(index + 1, end)
        elif char == '"':
            end = _double_quoted_end(text, index + 1)
            chunk = index + 1
            for escape in _DOUBLE_QUOTE_ESCAPE_RE.finditer(text, index + 1, end):
                if escape.group(1) is not None:
                    take(chunk, escape.start())
                    if escape.group(1) == "\n":  # a line continuation decodes to nothing
                        pieces.append((decoded, 0, escape.start(), escape.end(), escape.end()))
                    else:
                        take(escape.start() + 1, escape.end(), 1)
                    chunk = escape.end()
            take(chunk, end)
        elif char == "\\":
            end = index + 1
            if end == size:  # a trailing backslash stays literal
                take(index, end)
            elif text[end] == "\n":
                pieces.append((decoded, 0, index, end + 1, end + 1))
            else:
                take(end, end + 1, 1)
        else:
            plain = _PLAIN_RE.match(text, index)
            if plain is None:
                break
            take(index, plain.end())
            index = plain.end()
            continue
        index = end + 1
    keys = [piece[0] for piece in pieces]
    cuts: list[tuple[int, int]] = []
    for low, high in _heredoc_cuts("".join(parts), depth):
        for position in range(max(bisect.bisect_right(keys, low) - 1, 0), len(pieces)):
            at, length, outer, inner, stop = pieces[position]
            if at >= high:
                break
            first, last = max(low, at), min(high, at + length)
            if length == 0 and low < at:
                cut = (outer, stop)
            elif first < last:
                cut = (outer if first == at else inner + first - at, stop if last == at + length else inner + last - at)
            else:
                continue
            if cuts and cuts[-1][1] == cut[0]:
                cuts[-1] = (cuts[-1][0], cut[1])
            else:
                cuts.append(cut)
    return cuts, min(index, size)


def _heredoc_end(text: str, lines: tuple[list[int], dict[str, list[int]]], newline: int,
                 delimiters: list[str]) -> int | None:
    """End of the terminator line of the heredocs opened before `newline`; None if one never terminates."""
    starts, by_content = lines
    number = bisect.bisect_right(starts, newline)
    for delimiter in delimiters:
        found = by_content.get(delimiter, [])
        position = bisect.bisect_left(found, number)
        if position == len(found):
            return None
        number = found[position] + 1
    return starts[number] - 1 if number < len(starts) else len(text)


def _heredoc_cuts(text: str, depth: int = 0) -> list[tuple[int, int]]:
    """Spans of heredoc bodies with their terminator lines, also inside a shell's `-c` code.

    Not heredocs: `<<<`, quoted `<<` in an ordinary argument, `<<` inside `((...))`, and a
    delimiter that never terminates (its lines stay).
    """
    cuts: list[tuple[int, int]] = []
    pending: list[str] = []
    stack: list[bool] = []  # open parentheses; True marks an arithmetic `((`
    arithmetic = 0  # count of True entries in stack, so the `<<` check stays O(1)
    first = previous = None  # first and last complete word of the current simple command
    word = -1  # start of the word being read
    lines: tuple[list[int], dict[str, list[int]]] | None = None
    index, size = 0, len(text)
    while index < size:
        found = _SHELL_ACTIVE_RE.search(text, index)
        if found is None:
            break
        if word < 0 and found.start() > index:
            word = index
        index = found.start()
        char = text[index]
        if char in "'\"":
            if word < 0:
                word = index
                if (depth < 3 and first is not None and os.path.basename(first) in _SHELLS
                        and _C_FLAG_RE.fullmatch(previous or "")):
                    inner, index = _payload(text, index, depth + 1)
                    cuts.extend(inner)
                    continue
            end = text.find("'", index + 1) if char == "'" else _double_quoted_end(text, index + 1)
            index = (size if end < 0 else end) + 1
            continue
        if char == "\\":
            word = index if word < 0 else word
            index += 2
            continue
        if char == "#":
            if word >= 0:
                index += 1
                continue
            index = text.find("\n", index)
            if index < 0:
                break
            continue
        if word >= 0:
            if first is None:
                first = text[word:index]
            previous = text[word:index]
            word = -1
        if char == "<":
            if index > 0 and text[index - 1] == "<" or text.startswith("<<<", index):
                index += 3 if text.startswith("<<<", index) else 2
            elif text.startswith("<<", index):
                match = _HEREDOC_RE.match(text, index + 2)
                if match and not arithmetic:
                    pending.append(next(g for g in match.groups() if g))
                    index = match.end()
                else:
                    index += 2
            else:
                index += 1
            continue
        if char == "\n":
            first = previous = None
            if pending:
                if lines is None:
                    starts = [0, *(m.end() for m in re.finditer("\n", text))]
                    by_content: dict[str, list[int]] = {}
                    for number, line in enumerate(text.split("\n")):
                        by_content.setdefault(line.strip(), []).append(number)
                    lines = (starts, by_content)
                end = _heredoc_end(text, lines, index, pending)
                pending = []
                if end is not None:
                    cuts.append((index, end))
                    index = end
                    continue
        elif char in ";&|()":
            first = previous = None
            if char == "(":
                stack.append(index > 0 and text[index - 1] == "(")
                arithmetic += stack[-1]
            elif char == ")" and stack:
                arithmetic -= stack.pop()
        index += 1
    return cuts


def _strip_heredocs(command: str) -> str:
    """Drop heredoc bodies (data written by the command, not commands it runs)."""
    kept: list[str] = []
    index = 0
    for start, end in _heredoc_cuts(command):
        kept.append(command[index:start])
        index = end
    kept.append(command[index:])
    return "".join(kept)


def _runs(text: str, separator: re.Pattern[str]) -> Iterable[tuple[int, int, str]]:
    """(start, end, separator) of each stretch of `text` between separator characters."""
    start = 0
    while True:
        found = separator.search(text, start)
        end = found.start() if found else len(text)
        yield start, end, found.group() if found else ""
        if found is None:
            return
        start = end + 1


def _writes_manifest(text: str) -> bool:
    """Whether `text` writes a manifest.json by redirect, tee, sed -i, open(..., 'w') or write_text.

    Matches what one regex search per pattern would, in linear time: within a run without a
    separator only the first keyword matters, since a match from a later one is also a match from it.
    """
    if _MANIFEST not in text:
        return False
    if any(pattern.search(text) for pattern in _MANIFEST_WRITE_RES):
        return True
    sed_before = False  # the run before, ended by a newline, has `sed` (a newline can be the `\s` before `-i`)
    for start, end, separator in _runs(text, _RUN_END_RE):
        sed = _SED_RE.search(text, start, end)
        flag = None
        if sed_before and text.startswith("-", start):
            flag = _SED_IN_PLACE_RE.match(text, start - 1, end)
        if flag is None and sed is not None:
            flag = _SED_IN_PLACE_RE.search(text, sed.end(), end)
        if flag is not None and text.find(_MANIFEST, flag.end(), end) >= 0:
            return True
        tee = _TEE_RE.search(text, start, end)
        if tee is not None and text.find(_MANIFEST, tee.end(), end) >= 0:
            return True
        sed_before = sed is not None and separator == "\n"
    for start, end, _ in _runs(text, _OPEN_RUN_END_RE):
        opened = text.find("open(", start, end)
        named = text.find(_MANIFEST, opened + 5, end) if opened >= 0 else -1
        if named >= 0 and _WRITE_MODE_RE.search(text, named + len(_MANIFEST), end):
            return True
    return False


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
    """Yield lines; None marks a line over the size cap (rest of it is skipped).

    Only a regular file is read, at most `_MAX_FILE_BYTES` in total (else OSError).
    """
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise OSError(f"{path}: not a regular file")
    if info.st_size > _MAX_FILE_BYTES:
        raise OSError(f"{path}: larger than {_MAX_FILE_BYTES} bytes")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError(f"{path}: not a regular file")
        total = 0
        while True:
            line = handle.readline(_MAX_LINE_BYTES + 1)
            total += len(line)
            if not line:
                return
            if len(line) > _MAX_LINE_BYTES and not line.endswith(b"\n"):
                while True:
                    chunk = handle.readline(_MAX_LINE_BYTES)
                    total += len(chunk)
                    if total > _MAX_FILE_BYTES:
                        raise OSError(f"{path}: larger than {_MAX_FILE_BYTES} bytes")
                    if not chunk or chunk.endswith(b"\n"):
                        break
                yield None
            else:
                if total > _MAX_FILE_BYTES:
                    raise OSError(f"{path}: larger than {_MAX_FILE_BYTES} bytes")
                yield line


def _regular_text(path: Path) -> str | None:
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _tokens(command: str, cut: bool = False) -> list[str]:
    """Shell words; when `command` was cut short, a word left open at the cut ends there."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    tokens: list[str] = []
    try:
        for token in lexer:
            tokens.append(token)
    except ValueError:
        if not cut:
            return command.split()
        if lexer.token:
            tokens.append(lexer.token)
    return tokens


def _segments(command: str, depth: int = 0, cut: bool = False) -> list[list[str]]:
    """Split a command into simple-command token lists, unwrapping `bash -lc '...'`."""
    result: list[list[str]] = []
    current: list[str] = []
    command = _FD_DUP_RE.sub(" ", _strip_heredocs(command)).replace("\n", ";")
    for token in _tokens(command, cut) + [";"]:
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
                expanded.extend(_segments(inner, depth + 1, cut))
                continue
        expanded.append(segment)
    return expanded


def _read_paths(command: str, cut: bool = False) -> list[str]:
    """Operands of read commands (cat, head, tail, sed, nl, less, rg, grep, awk) outside heredoc bodies."""
    paths: list[str] = []
    for segment in _segments(command, cut=cut):
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


_PLUGIN_SOURCE_RE = re.compile(_ANY_PLUGIN_CACHE_PATH.pattern + _SOURCE_TAIL)


def _plugin_source_paths(text: str) -> list[str]:
    """Distinct plugin-cache scripts/ or src/ paths named in `text`, grouped by marketplace.

    A plugin-cache path nested inside another path's scripts/ or src/ tail is part of that match
    and is not listed separately. The caller's substring check usually still finds it, but not
    when the outer tail holds a backslash that shell word splitting removes.

    One pass over `text`: a pattern per named marketplace made the scan quadratic.
    """
    matches = sorted(
        ((m.group("marketplace"), m.group(0)) for m in _PLUGIN_SOURCE_RE.finditer(text)),
        key=lambda pair: pair[0],
    )
    return list(dict.fromkeys(path for _, path in matches))


def _is_help(command: str) -> bool:
    return bool(re.search(r"(?<!\S)(?:--help|-h)(?!\S)", command))


def _item_id(value: Any) -> Any:
    return _short(value) if isinstance(value, str) else value


def _example(command: str, item: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"command": _short(command), "item_id": _item_id(item.get("id")), "t": item.get("t"), **extra}


def _section(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {"count": len(rows), "examples": rows[:MAX_EXAMPLES]}


def collect_items(lines: Iterable[bytes | str | None]) -> dict[str, Any]:
    """Parse event lines (wrapped `{"t","event"}` or bare); tolerate malformed lines."""
    items: dict[Any, dict[str, Any]] = {}
    order: list[Any] = []
    malformed = 0
    parsed = 0
    terminal = None
    previous: tuple[str, str, str, str, Any] | None = None  # the line before: slot kind, event, item type, command, slot key
    for number, line in enumerate(lines):
        prior, previous = previous, None
        if line is None:
            malformed += 1
            continue
        try:
            record = json.loads(line)
        except (UnicodeError, TypeError, RecursionError, ValueError):
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
        command_text = item["command"] if isinstance(item.get("command"), str) else ""
        if isinstance(raw_id, (str, int)) and not isinstance(raw_id, bool):
            slot: Any = ("id", item_type, type(raw_id).__name__, raw_id)
        elif (prior is not None and prior[0] == "line" and prior[1] == "item.started"
                and event_type == "item.completed" and prior[2] == item_type
                and command_text and prior[3] == command_text):
            slot = ("line", prior[4])
        else:
            slot = ("line", number)
        row = items.get(slot)
        if row is None:
            row = items[slot] = {"id": raw_id if slot[0] == "id" else None, "type": item["type"],
                                "command": "", "exit_code": None, "changes": [],
                                "t": t, "last_t": t}
            order.append(slot)
        previous = (slot[0], event_type, item_type, command_text, slot[1])
        if t is not None:
            row["t"] = t if row["t"] is None else min(row["t"], t)
            row["last_t"] = t if row["last_t"] is None else max(row["last_t"], t)
        if isinstance(item.get("command"), str):
            row["command"] = item["command"]
        if isinstance(item.get("status"), str):
            row["status"] = item["status"]
        exit_code = item.get("exit_code")
        if isinstance(exit_code, int) and not isinstance(exit_code, bool):
            row["exit_code"] = exit_code
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
    except (RecursionError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _inside(root: Path, candidate: str, base: Path) -> Path | None:
    """Refuse lexical escapes without collapsing symlink-sensitive parent steps."""
    if not candidate or "\x00" in candidate:
        return None
    joined = os.path.join(base, candidate)
    normalized = os.path.normpath(joined)
    root_text = os.path.normpath(root)
    if normalized != root_text and not normalized.startswith(root_text + os.sep):
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
    root = project.resolve()
    for source, path, base in named:
        resolved = _inside(project, path, base)
        if resolved is None:
            rows.append({"path": _short(path), "source": source, "reason": "outside_project"})
        else:
            try:
                target = resolved.resolve()
                if not target.is_relative_to(root):
                    rows.append({"path": _short(path), "source": source, "reason": "outside_project"})
                elif not os.path.exists(resolved):
                    rows.append({"path": _short(path), "source": source, "reason": "missing"})
            except (OSError, RuntimeError, ValueError):
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
                run_id = record.get("run_id") if record else None
                if run_id is not None and not any(isinstance(run, Mapping) and run.get("run_id") == run_id
                                                 for run in runs):
                    reasons.append(_short(f"completion record run {run_id!r} is absent from completion_report"))
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
        words, cut = command[:_MAX_SCAN_CHARS], len(command) > _MAX_SCAN_CHARS
        names = [m.group("name") for m in _SCRIPT_RE.finditer(command)]
        norm = _normalize(raw)
        command_counts.setdefault(norm, []).append(item)
        exit_code = item["exit_code"]
        if exit_code not in (None, 0) or item.get("status") == "failed":
            segments = _segments(words, cut=cut)
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
        for path in _read_paths(words, cut):
            reads.setdefault(_plugin_relative(path), []).append(item)
        if not _is_help(command):
            read_set = set(_read_paths(words, cut))
            for source in _plugin_source_paths(command):
                if any(source in path for path in read_set):
                    plugin_reads.append(_example(raw, item, path=_short(source)))
                    break
        if not names and _writes_manifest(raw):
            manifest_edits.append(_example(raw, item, via="command"))
    for item in items:
        if item["type"] != "file_change":
            continue
        for change in item["changes"]:
            path = change.get("path")
            if isinstance(path, str) and os.path.basename(path) == "manifest.json":
                manifest_edits.append({"command": None, "item_id": _item_id(item["id"]), "t": item["t"],
                                       "via": "file_change", "path": _short(path)})
    repeated_commands = [(c, -n) for n, c in sorted((-len(v), c) for c, v in command_counts.items()
                                                    if len(v) >= REPEAT_THRESHOLD)]
    repeated_reads = [(p, -n) for n, p in sorted((-len(v), p) for p, v in reads.items()
                                                 if len(v) >= REPEAT_THRESHOLD)]
    phase_rows = [row for *_, row in sorted(
        (span[0] is None, span[0] or 0.0, name, {"script": name, "first_t": span[0], "last_t": span[1]})
        for name, span in phases.items())][:MAX_EXAMPLES]
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
