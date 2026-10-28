"""Build a validated study table from screening decisions and extraction data."""
from __future__ import annotations

import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import Any

from codex_science.cli_io import write_json_atomic
from codex_science.evidence import EVIDENCE_TYPES, _normalise_excerpt, _support_source_path, _validate_study_table
from codex_science.literature_v2 import normalize_identifier
from codex_science.open_fulltext import MAX_BODY_BYTES, _plain_text
from codex_science.screening_pool import _load_snapshot, _relative_path, _safe_file


def _input_file(root: Path, value: str | Path, label: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        try:
            relative = path.absolute().relative_to(root)
        except ValueError as error:
            raise ValueError(f"{label} must be inside the run directory") from error
    else:
        try:
            relative = path.absolute().relative_to(root)
        except ValueError:
            relative = path
    result = _safe_file(root, _relative_path(relative.as_posix(), label))
    assert result is not None
    return result


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must be a list of non-empty strings")
    return value


def _validate_extraction_numbers(value: Any, label: str, field: str = "") -> None:
    if isinstance(value, bool) and field in {"sample_size", "effect_estimate", "standard_error"}:
        raise ValueError(f"{label} must not be boolean")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    if isinstance(value, dict):
        for key, item in value.items():
            _validate_extraction_numbers(item, f"{label}.{key}", key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _validate_extraction_numbers(item, f"{label}[{index}]", field)


_PMCID_STEM = re.compile(r"PMC\d+")  # exactly the names fetch_open_fulltext writes


def _excerpt_line_spans(text: str, source: str, locator_line: int) -> tuple[list[tuple[int, int]], bool]:
    """Return bounded source spans, checking the locator before collecting error examples."""
    normalized_excerpt = _normalise_excerpt(text)
    normalized_source = _normalise_excerpt(source)
    tokens = list(re.finditer(r"\S+", source))
    token_lines = []
    line = 1
    newlines = iter(match.start() for match in re.finditer("\n", source))
    next_newline = next(newlines, None)
    for token in tokens:
        while next_newline is not None and next_newline < token.start():
            line += 1
            next_newline = next(newlines, None)
        start_line = line
        while next_newline is not None and next_newline < token.end():
            line += 1
            next_newline = next(newlines, None)
        token_lines.append((start_line, line))
    # Map normalized characters back to source lines; the separator covers intervening lines.
    char_spans: list[tuple[int, int]] = []
    for index, token in enumerate(tokens):
        char_spans.extend([token_lines[index]] * len(_normalise_excerpt(token.group())))
        if index + 1 < len(tokens):
            char_spans.append((token_lines[index][1], token_lines[index + 1][0]))

    if not normalized_excerpt and char_spans:
        span = (char_spans[0][0], char_spans[-1][1])
        if span[0] <= locator_line <= span[1]:
            return [span], False
    elif normalized_excerpt and char_spans:
        first_target = next((i for i, (_, end) in enumerate(char_spans) if end >= locator_line), None)
        last_target = next((i for i in range(len(char_spans) - 1, -1, -1)
                            if char_spans[i][0] <= locator_line), None)
        if first_target is not None and last_target is not None:
            first_start = max(0, first_target - len(normalized_excerpt) + 1)
            position = normalized_source.find(normalized_excerpt, first_start)
            while position >= 0 and position <= last_target:
                end = position + len(normalized_excerpt) - 1
                span = (char_spans[position][0], char_spans[end][1])
                if span[0] <= locator_line <= span[1]:
                    return [span], False
                position = normalized_source.find(normalized_excerpt, position + 1)

    spans: list[tuple[int, int]] = []
    start = 0
    while len(spans) < 64 and (position := normalized_source.find(normalized_excerpt, start)) >= 0:
        end = position + len(normalized_excerpt) - 1
        if position < len(char_spans) and end < len(char_spans):
            spans.append((char_spans[position][0], char_spans[end][1]))
        start = position + 1
    truncated = normalized_source.find(normalized_excerpt, start) >= 0
    return spans, truncated


def _local(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1] if isinstance(node.tag, str) else ""


def _fulltext_front_ids(path: Path) -> dict[str, set[str]]:
    """Return every normalized pmcid/pmid/doi in article/front/article-meta of a fetched JATS file; {} if unusable."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BODY_BYTES:
            return {}
        body = path.read_bytes()
        _plain_text(body)  # same refusal rules as fetch: no entities, UTF-8 only, well-formed
        root = ET.fromstring(body.removeprefix(b"\xef\xbb\xbf"), parser=ET.XMLParser(encoding="utf-8"))
    except (OSError, ValueError, ET.ParseError, RecursionError):
        return {}
    found: dict[str, set[str]] = {}
    if _local(root) != "article":
        return found
    for front in (node for node in root if _local(node) == "front"):
        for meta in (node for node in front if _local(node) == "article-meta"):
            for node in meta:
                kind = node.get("pub-id-type")
                if _local(node) == "article-id" and kind in {"pmcid", "pmid", "doi"} and node.text and node.text.strip():
                    found.setdefault(kind, set()).add(normalize_identifier(f"{kind}:{node.text.strip()}"))
    return found


def _alias_fulltext_pmcids(root: Path, studies: list[dict[str, Any]]) -> None:
    """Append pmcid:PMC... of fetched full text to the single study matching its pmid/doi/pmcid."""
    directory = root / "fulltext"
    if directory.is_symlink() or not directory.is_dir():
        return
    by_id: dict[str, set[int]] = {}
    original: list[set[str]] = []  # aliases appended below must not contradict later files
    for index, study in enumerate(studies):
        original.append({normalize_identifier(value) for value in study["identifiers"]})
        for value in original[index]:
            by_id.setdefault(value, set()).add(index)
    for path in sorted(directory.glob("*.xml")):
        if not _PMCID_STEM.fullmatch(path.stem):
            continue
        ids = _fulltext_front_ids(path)
        if any(len(values) > 1 for values in ids.values()):
            continue  # conflicting front-matter ids are ambiguous
        pmcid = next(iter(ids.get("pmcid", ())), None)
        if pmcid is None or pmcid != normalize_identifier("pmcid:" + path.stem):
            continue
        matches = set().union(*(by_id.get(value, set()) for kind in ("pmid", "doi", "pmcid") for value in ids.get(kind, ())))
        if len(matches) != 1:
            continue
        index = next(iter(matches))
        study = studies[index]
        if any(
            ids.get(kind) and (known := {value for value in original[index] if value.startswith(kind + ":")})
            and not known & ids[kind]
            for kind in ("pmid", "doi", "pmcid")
        ):
            continue  # a contradictory identifier in any namespace outweighs a match in another
        if pmcid not in {normalize_identifier(value) for value in study["identifiers"]}:
            study["identifiers"] = [*study["identifiers"], pmcid]
            study["persistent_ids"] = list(study["identifiers"])
            by_id.setdefault(pmcid, set()).add(index)


def build_study_table(
    run_dir: str | Path, extraction_file: str | Path, output: str | Path = "studies.json",
) -> dict[str, Any]:
    """Build studies.json; refuse incomplete or invalid extraction without writing."""
    root_arg = Path(run_dir).absolute()
    if root_arg.is_symlink() or not root_arg.is_dir():
        raise ValueError("run directory must be an existing, non-symlink directory")
    root = root_arg.resolve()
    screening_path = _safe_file(root, PurePosixPath("screening.json"))
    candidates_path = _safe_file(root, PurePosixPath("candidates.json"))
    extraction_path = _input_file(root, extraction_file, "extraction file")
    assert screening_path is not None and candidates_path is not None
    screening, screening_sha256 = _load_snapshot(screening_path)
    candidates, candidates_sha256 = _load_snapshot(candidates_path)
    extraction, extraction_sha256 = _load_snapshot(extraction_path)
    if screening.get("schema") != "screening-table-v1" or not isinstance(screening.get("records"), list):
        raise ValueError("unsupported or malformed screening.json")
    if candidates.get("schema") != "literature-candidates-v1" or not isinstance(candidates.get("records"), list):
        raise ValueError("unsupported or malformed candidates.json")
    if screening.get("candidates_sha256") != candidates_sha256:
        raise ValueError("screening.json candidates_sha256 does not match candidates.json; rerun screen_candidates.py apply against the current pool")
    if extraction.get("schema") != "study-extraction-v1":
        raise ValueError("extraction schema must be study-extraction-v1")
    rows, not_extracted = extraction.get("studies"), extraction.get("not_extracted", [])
    if not isinstance(rows, list) or not isinstance(not_extracted, list):
        raise ValueError("extraction studies and not_extracted must be lists")

    screen_by_id: dict[str, dict[str, Any]] = {}
    for row in screening["records"]:
        if not isinstance(row, dict) or not isinstance(row.get("record_id"), str) or row["record_id"] in screen_by_id:
            raise ValueError("screening.json contains invalid or duplicate record_id")
        screen_by_id[row["record_id"]] = row
    candidate_by_id: dict[str, dict[str, Any]] = {}
    for row in candidates["records"]:
        if not isinstance(row, dict) or not isinstance(row.get("record_id"), str) or row["record_id"] in candidate_by_id:
            raise ValueError("candidates.json contains invalid or duplicate record_id")
        candidate_by_id[row["record_id"]] = row
    unknown = sorted(screen_by_id.keys() - candidate_by_id.keys())
    if unknown:
        raise ValueError(f"screening.json record_id not in candidates.json: {', '.join(unknown)}")
    includes = {key for key, row in screen_by_id.items() if row.get("decision") == "include"}

    problems: list[str] = []
    assigned: dict[str, dict[str, Any] | None] = {}
    for kind, items in (("study", rows), ("not_extracted", not_extracted)):
        for index, item in enumerate(items):
            if not isinstance(item, dict) or not isinstance(item.get("record_id"), str) or not item["record_id"].strip():
                problems.append(f"{kind}[{index}]: record_id must be a non-empty string")
                continue
            record_id = item["record_id"]
            if record_id not in candidate_by_id:
                problems.append(f"{record_id}: record_id not in candidates.json")
            if record_id not in screen_by_id:
                problems.append(
                    f"{record_id}: unknown record_id (not in screening.json; screen it before extraction)"
                )
            elif record_id not in includes:
                problems.append(f"{record_id}: record is not included")
            if record_id in assigned:
                problems.append(f"{record_id}: duplicate extraction assignment")
            assigned[record_id] = item if kind == "study" else None
            if kind == "not_extracted" and (not isinstance(item.get("reason"), str) or not item["reason"].strip()):
                problems.append(f"{record_id}: not_extracted reason must be a non-empty string")
    for record_id in sorted(includes - assigned.keys()):
        problems.append(f"{record_id}: included record is missing from studies and not_extracted")

    studies: list[dict[str, Any]] = []
    excerpt_problems: list[str] = []
    for item in rows:
        if not isinstance(item, dict) or not isinstance(item.get("record_id"), str):
            continue
        record_id = item["record_id"]
        screening_row = screen_by_id.get(record_id, {})
        if record_id not in screen_by_id:
            continue
        candidate = candidate_by_id.get(record_id, {})
        evidence_path = None
        screening_content = b""
        try:
            if screening_row.get("evidence_artifact") is not None:
                evidence_relative = _relative_path(screening_row["evidence_artifact"], f"{record_id} evidence_artifact")
                evidence_path = _safe_file(root, evidence_relative)
                assert evidence_path is not None
                screening_content = evidence_path.read_bytes()
                if hashlib.sha256(screening_content).hexdigest() != screening_row.get("evidence_sha256"):
                    raise ValueError(f"{record_id}: evidence_sha256 does not match screening evidence_artifact; rerun screening")
        except (ValueError, OSError, TypeError) as error:
            problems.append(str(error))
        ids_a = screening_row.get("identifiers", [])
        ids_b = candidate.get("identifiers", [])
        if (not isinstance(ids_a, list) or not isinstance(ids_b, list)
                or any(not isinstance(x, str) or not x.strip() for x in ids_a + ids_b)):
            problems.append(f"{record_id}: screening and candidate identifiers must be non-empty string lists")
            identifiers: list[str] = []
        else:
            identifiers = list(dict.fromkeys(ids_a + ids_b))
        persistent = next((value for value in identifiers if value.lower().startswith("doi:")), None)
        persistent = persistent or (identifiers[0] if identifiers else None)
        if persistent is None:
            problems.append(f"{record_id}: cannot build study; no persistent identifier is available")
            continue
        study_id = item.get("study_id", "S" + "".join(c for c in record_id if c.isalnum()))
        if not isinstance(study_id, str) or not study_id.strip():
            problems.append(f"{record_id}: study_id must be a non-empty string")
            continue
        evidence_type = item.get("evidence_type")
        if not isinstance(evidence_type, str) or evidence_type not in EVIDENCE_TYPES:
            problems.append(f"{record_id}: evidence_type must be one of {sorted(EVIDENCE_TYPES)}")
        try:
            supports = _string_list(item.get("supports_claim_ids", []), f"{record_id} supports_claim_ids")
            contradicts = _string_list(item.get("contradicts_claim_ids", []), f"{record_id} contradicts_claim_ids")
        except ValueError as error:
            problems.append(str(error))
            supports, contradicts = [], []
        fields = item.get("fields", {})
        if not isinstance(fields, dict):
            problems.append(f"{record_id}: fields must be an object")
            fields = {}
        try:
            _validate_extraction_numbers(fields, f"{record_id} fields")
        except ValueError as error:
            problems.append(str(error))
        owned = {"study_id", "record_id", "title", "identifiers", "persistent_id", "persistent_ids", "included",
                 "evidence_type", "supports_claim_ids", "contradicts_claim_ids", "support_excerpts", "publication_date", "query_ids", "cohort_id"}
        for key in fields:
            if key in owned:
                problems.append(f"{record_id}: fields cannot override builder-owned key {key}")
        title = screening_row.get("title") or candidate.get("title")
        if not isinstance(title, str) or not title.strip():
            problems.append(f"{record_id}: title is missing")
            title = ""
        study: dict[str, Any] = {
            **{key: value for key, value in fields.items() if key not in owned},
            "study_id": study_id, "record_id": record_id, "title": title,
            "identifiers": identifiers, "persistent_id": persistent, "persistent_ids": identifiers,
            "included": True, "evidence_type": evidence_type,
            "supports_claim_ids": supports, "contradicts_claim_ids": contradicts,
            "query_ids": [],
        }
        if "cohort_id" in item:
            cohort_id = item["cohort_id"]
            if not isinstance(cohort_id, str) or not cohort_id.strip():
                problems.append(f"{record_id}: cohort_id must be a non-empty string")
            else:
                study["cohort_id"] = cohort_id
        screen_queries, candidate_queries = screening_row.get("query_ids", []), candidate.get("query_ids", [])
        if (not isinstance(screen_queries, list) or not isinstance(candidate_queries, list)
                or any(not isinstance(value, str) for value in screen_queries + candidate_queries)):
            problems.append(f"{record_id}: screening and candidate query_ids must be string lists")
        else:
            study["query_ids"] = list(dict.fromkeys(screen_queries + candidate_queries))
        if isinstance(candidate.get("publication_date"), str):
            study["publication_date"] = candidate["publication_date"]
        excerpts = item.get("excerpts", [])
        if not isinstance(excerpts, list):
            excerpt_problems.append(f"{record_id}, <unknown>, excerpts must be a list")
            excerpts = []
        support_excerpts = []
        for excerpt in excerpts:
            claim_id = excerpt.get("claim_id", "<unknown>") if isinstance(excerpt, dict) else "<unknown>"
            label = f"{record_id}, {claim_id}"
            if not isinstance(excerpt, dict):
                excerpt_problems.append(f"{label}, excerpt must be an object")
                continue
            claim_id, text = excerpt.get("claim_id"), excerpt.get("text")
            if not isinstance(claim_id, str) or claim_id not in set(supports) | set(contradicts):
                excerpt_problems.append(f"{label}, claim_id is not linked to this study")
            valid_excerpt_text = isinstance(text, str) and 20 <= len(text) <= 2000
            if not valid_excerpt_text:
                got = f"{len(text)} characters" if isinstance(text, str) else f"type {type(text).__name__}"
                excerpt_problems.append(
                    f"{label}, text length must be 20..2000 characters (got {got}); "
                    "quote only the verbatim claim-bearing sentences, not the whole abstract"
                )
            source = excerpt.get("source_artifact", screening_row.get("evidence_artifact"))
            try:
                relative = _relative_path(source, f"{label} source_artifact")
                source_file = _safe_file(root, relative)
                assert source_file is not None
                source_path = _support_source_path(root, source, study_id, str(claim_id))
                content = screening_content if source_path == evidence_path else source_path.read_bytes()
                if isinstance(text, str):
                    try:
                        source_text = content.decode("utf-8")
                        normalized_excerpt = _normalise_excerpt(text)
                        normalized_source = _normalise_excerpt(source_text)
                        if normalized_excerpt not in normalized_source:
                            excerpt_problems.append(f"{label}, excerpt text does not occur in source")
                        elif valid_excerpt_text:
                            locator = excerpt.get("locator")
                            line = locator.get("line") if isinstance(locator, dict) else None
                            if isinstance(line, int) and not isinstance(line, bool):
                                spans, truncated = _excerpt_line_spans(text, source_text, line)
                                if not any(start <= line <= end for start, end in spans):
                                    starts = list(dict.fromkeys(start for start, _ in spans))[:5]
                                    starts_text = ", ".join(str(value) for value in starts)
                                    if len(set(start for start, _ in spans)) > 5 or truncated:
                                        starts_text += ", ..."
                                    excerpt_problems.append(
                                        f"{label}, locator.line {line} does not contain the excerpt; text starts at line {starts_text}"
                                    )
                    except UnicodeDecodeError:
                        excerpt_problems.append(f"{label}, source is not UTF-8")
                excerpt_row = {"claim_id": claim_id, "text": text, "source_artifact": source_path.relative_to(root).as_posix(),
                               "source_sha256": hashlib.sha256(content).hexdigest()}
                if "locator" in excerpt:
                    if not isinstance(excerpt["locator"], dict):
                        excerpt_problems.append(f"{label}, locator must be an object")
                    else:
                        excerpt_row["locator"] = excerpt["locator"]
                support_excerpts.append(excerpt_row)
            except (ValueError, OSError, TypeError) as error:
                excerpt_problems.append(f"{label}, {error}")
        study["support_excerpts"] = support_excerpts
        studies.append(study)

    _alias_fulltext_pmcids(root, studies)
    if problems:
        raise ValueError("extraction coverage errors: " + "; ".join(problems + excerpt_problems))
    if excerpt_problems:
        raise ValueError("excerpt errors: " + "; ".join(excerpt_problems))
    payload = {"schema_version": 1, "studies": studies}
    _validate_study_table(payload, root)
    output_arg = Path(output)
    if output_arg.is_absolute():
        try:
            output_value = output_arg.absolute().relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError("output file must be inside the run directory") from error
    else:
        output_value = output_arg.as_posix()
    output_relative = _relative_path(output_value, "output file")
    output_path = root / Path(*output_relative.parts)
    # Reject symlinked ancestors and an existing symlink destination before atomic replacement.
    _safe_file(root, output_relative, required=False)
    protected_paths = {screening_path.absolute(), candidates_path.absolute(), extraction_path.absolute()}
    excerpt_source_paths = {
        root / Path(*PurePosixPath(excerpt["source_artifact"]).parts)
        for study in studies for excerpt in study["support_excerpts"]
    }
    if output_path.absolute() in protected_paths or output_path.absolute() in excerpt_source_paths:
        raise ValueError("output file must not replace screening.json, candidates.json, the extraction input, or an excerpt source")
    write_json_atomic(output_path, payload)
    return {"schema": "study-table-build-v1", "output": output_path.relative_to(root).as_posix(),
            "counts": {"studies": len(studies), "not_extracted": len(not_extracted), "excerpts": sum(len(s["support_excerpts"]) for s in studies)},
            "extraction_sha256": extraction_sha256, "screening_sha256": screening_sha256,
            "not_extracted": not_extracted}
