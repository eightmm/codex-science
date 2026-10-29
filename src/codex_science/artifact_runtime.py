"""Bounded native scientific artifact views, selections, and edit proposals.

The runtime deliberately separates three concepts:

* a *view* is a bounded, derived description of validated artifact bytes;
* a *selection* is a typed, hash-bound pointer into those bytes;
* a *transform proposal* is a non-executing request that can feed impact and
  selective-rerun planning.

None of these objects are scientific evidence by themselves and no function in
this module mutates the source artifact.
"""

from __future__ import annotations

import codecs
import csv
import hashlib
import html
import io
import json
import struct
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from codex_science.artifact_store import describe_directory, stream_sha256


DEFAULT_MAX_BYTES = 1024 * 1024
DEFAULT_MAX_RECORDS = 100

VIEWER_SELECTIONS: dict[str, frozenset[str]] = {
    "structure-3d": frozenset({"atom", "residue", "chain", "ligand", "spatial-region"}),
    "molecule-2d": frozenset({"atom", "bond", "substructure", "record"}),
    "genome-track": frozenset({"variant", "locus", "interval", "track-record"}),
    "single-cell": frozenset({"cell", "cell-set", "feature", "cluster", "donor", "layer"}),
    "table": frozenset({"row", "column", "cell", "range"}),
    "figure": frozenset({"region", "axis", "legend", "panel"}),
    "evidence-graph": frozenset({"node", "edge", "claim", "component"}),
    "trajectory": frozenset({"frame", "frame-range", "atom", "atom-set"}),
    "directory": frozenset({"entry", "entry-set"}),
    "text": frozenset({"line", "line-range", "heading", "json-pointer"}),
    "binary": frozenset({"byte-range", "record"}),
}

MAX_RUNTIME_BYTES = 16 * 1024 * 1024
MAX_RUNTIME_RECORDS = 10_000
MAX_SELECTION_BYTES = 64 * 1024
MAX_PROPOSAL_PARAMETER_BYTES = 64 * 1024
MAX_REASON_CHARACTERS = 4_000
_COMPLETE_TABLE_HEADER_WARNING = "The byte-bounded table preview includes the complete header."

STRUCTURE_SUFFIXES = {".pdb", ".ent", ".cif", ".mmcif"}
MOLECULE_SUFFIXES = {".sdf", ".mol", ".mol2", ".smi", ".smiles"}
GENOME_SUFFIXES = {".vcf", ".bed", ".gff", ".gff3", ".gtf", ".wig", ".bedgraph", ".bigwig", ".bw"}
SINGLE_CELL_SUFFIXES = {".h5ad", ".loom"}
TABLE_SUFFIXES = {".csv", ".tsv", ".parquet", ".feather", ".arrow"}
FIGURE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".tif", ".tiff"}
GRAPH_SUFFIXES = {".graph.json", ".cyjs"}
TRAJECTORY_SUFFIXES = {".xyz", ".dcd", ".xtc", ".trr", ".nc", ".netcdf"}
TEXT_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".py", ".r", ".jl", ".sh"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _safe_relative(value: str, label: str = "path") -> str:
    pure = PurePosixPath(value)
    if not value or pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"{label} must be a safe relative path: {value}")
    return pure.as_posix()


def _sha256(value: Any, label: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{label} must be a SHA-256 digest")
    return text


def _json_value(value: Any, label: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _json_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{label} object keys must be strings")
            _json_value(item, f"{label}.{key}")
        return
    raise ValueError(f"{label} must contain JSON-compatible values")


def _read_head(path: Path, max_bytes: int) -> tuple[bytes, bool]:
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    return data[:max_bytes], len(data) > max_bytes


def _decode_text(data: bytes, *, truncated: bool = False) -> tuple[str, str]:
    for marker, encoding in ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
                             (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
        if data.startswith(marker):
            try:
                decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
                return decoder.decode(data, final=not truncated), encoding
            except UnicodeDecodeError as exc:
                raise ValueError(f"Incomplete or malformed {encoding} text inside the byte bound") from exc
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
            return decoder.decode(data, final=not truncated), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replacement"


def _is_json(path: Path, media_type: str | None = None) -> bool:
    media = (media_type or "").lower()
    return path.suffix.lower() == ".json" or media.endswith("+json") or media == "application/json"


def detect_viewer(path: Path, *, kind: str = "", media_type: str | None = None) -> str:
    if path.is_dir():
        return "directory"
    lower = path.name.lower()
    suffix = path.suffix.lower()
    kind_lower = kind.lower()
    media = (media_type or "").lower()
    if suffix in STRUCTURE_SUFFIXES or "structure" in kind_lower or "chemical/x-pdb" in media:
        return "structure-3d"
    if suffix in MOLECULE_SUFFIXES or "molecule" in kind_lower or "chemical/x-mdl" in media:
        return "molecule-2d"
    if suffix in GENOME_SUFFIXES or any(token in kind_lower for token in ("variant", "genome", "track")):
        return "genome-track"
    if suffix in SINGLE_CELL_SUFFIXES or "anndata" in kind_lower or "single-cell" in kind_lower:
        return "single-cell"
    if suffix in TABLE_SUFFIXES or media in {"text/csv", "text/tab-separated-values", "application/vnd.apache.parquet"}:
        return "table"
    if suffix in FIGURE_SUFFIXES or media.startswith("image/") or "figure" in kind_lower:
        return "figure"
    if lower.endswith(".graph.json") or suffix in GRAPH_SUFFIXES or "evidence-graph" in kind_lower:
        return "evidence-graph"
    if suffix in TRAJECTORY_SUFFIXES or "trajectory" in kind_lower:
        return "trajectory"
    if suffix in TEXT_SUFFIXES or media.startswith("text/") or _is_json(path, media_type):
        return "text"
    return "binary"


def _bounded(items: Iterable[Any], maximum: int) -> tuple[list[Any], bool]:
    result: list[Any] = []
    iterator = iter(items)
    for _ in range(maximum):
        try:
            result.append(next(iterator))
        except StopIteration:
            return result, False
    try:
        next(iterator)
    except StopIteration:
        return result, False
    return result, True


def _structure_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated_bytes = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated_bytes)
    warnings: list[str] = []
    atoms: list[dict[str, Any]] = []
    chains: set[str] = set()
    residues: set[str] = set()
    ligands: set[str] = set()
    if path.suffix.lower() in {".pdb", ".ent"}:
        for line in text.splitlines():
            if not line.startswith(("ATOM  ", "HETATM")):
                continue
            try:
                atom = {
                    "record": line[:6].strip(),
                    "serial": int(line[6:11].strip() or 0),
                    "atom": line[12:16].strip(),
                    "altloc": line[16:17].strip(),
                    "resname": line[17:20].strip(),
                    "chain": line[21:22].strip(),
                    "resseq": line[22:26].strip(),
                    "x": float(line[30:38]),
                    "y": float(line[38:46]),
                    "z": float(line[46:54]),
                    "element": line[76:78].strip() if len(line) >= 78 else "",
                }
            except (ValueError, IndexError):
                warnings.append("At least one coordinate record could not be normalized.")
                continue
            chains.add(atom["chain"] or "_")
            residues.add(f"{atom['chain'] or '_'}:{atom['resname']}:{atom['resseq']}:{line[26:27].strip()}")
            if atom["record"] == "HETATM" and atom["resname"] not in {"HOH", "WAT"}:
                ligands.add(atom["resname"])
            if len(atoms) < max_records:
                atoms.append(atom)
        preview = {
            "format": "pdb",
            "encoding": encoding,
            "atoms_preview": atoms,
            "chains_seen": sorted(chains),
            "residues_seen": len(residues),
            "ligands_seen": sorted(ligands),
        }
    else:
        categories = sorted({line.split(".", 1)[0] for line in text.splitlines() if line.startswith("_")})
        atom_lines = [line for line in text.splitlines() if line.startswith("ATOM ") or line.startswith("HETATM ")]
        preview = {
            "format": "mmcif",
            "encoding": encoding,
            "categories_preview": categories[:max_records],
            "coordinate_rows_preview": atom_lines[:max_records],
        }
        if len(categories) > max_records or len(atom_lines) > max_records:
            warnings.append("The mmCIF preview is record bounded.")
    if truncated_bytes:
        warnings.append("The structure preview is byte bounded; counts describe only the inspected prefix.")
    return preview, warnings


def _molecule_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated_bytes = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated_bytes)
    warnings: list[str] = []
    suffix = path.suffix.lower()
    if suffix in {".smi", ".smiles"}:
        records = []
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            fields = stripped.split()
            records.append({"line": line_number, "smiles": fields[0], "name": " ".join(fields[1:])})
            if len(records) >= max_records:
                break
        preview = {"format": "smiles", "encoding": encoding, "records_preview": records}
    else:
        blocks = text.split("$$$$")
        records = []
        for index, block in enumerate(blocks):
            lines = block.strip("\r\n").splitlines()
            if not lines:
                continue
            atom_count = bond_count = None
            if len(lines) >= 4:
                counts = lines[3]
                try:
                    atom_count = int(counts[0:3])
                    bond_count = int(counts[3:6])
                except ValueError:
                    pass
            properties = [line[4:-1] for line in lines if line.startswith(">  <") and line.endswith(">")]
            records.append({
                "record_index": index,
                "name": lines[0].strip() if lines else "",
                "atom_count": atom_count,
                "bond_count": bond_count,
                "properties": properties[:25],
            })
            if len(records) >= max_records:
                break
        preview = {"format": suffix.lstrip(".") or "mol", "encoding": encoding, "records_preview": records}
    if truncated_bytes:
        warnings.append("The molecular preview is byte bounded and may end inside a record.")
    return preview, warnings


def _genome_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    if path.suffix.lower() in {".bigwig", ".bw"}:
        data, truncated = _read_head(path, min(max_bytes, 4096))
        return ({"format": "bigwig", "magic_hex": data[:4].hex(), "header_bytes_preview": data[:64].hex()}, ["bigWig is represented by bounded binary metadata; track values require a dedicated indexed reader."] + (["Header preview truncated."] if truncated else []))
    data, truncated_bytes = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated_bytes)
    headers: list[str] = []
    records: list[dict[str, Any]] = []
    suffix = path.suffix.lower()
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line:
            continue
        if line.startswith("#") or line.startswith("track") or line.startswith("browser"):
            if len(headers) < 50:
                headers.append(line)
            continue
        fields = line.split("\t")
        if suffix == ".vcf" and len(fields) >= 8:
            record = {"line": line_number, "chrom": fields[0], "pos": fields[1], "id": fields[2], "ref": fields[3], "alt": fields[4], "qual": fields[5], "filter": fields[6]}
        elif suffix in {".gff", ".gff3", ".gtf"} and len(fields) >= 5:
            record = {"line": line_number, "chrom": fields[0], "start": fields[3], "end": fields[4], "fields": fields[5:10]}
        elif suffix not in {".gff", ".gff3", ".gtf"} and len(fields) >= 3:
            record = {"line": line_number, "chrom": fields[0], "start": fields[1], "end": fields[2], "fields": fields[3:10]}
        else:
            record = {"line": line_number, "raw": line[:500]}
        records.append(record)
        if len(records) >= max_records:
            break
    warnings = ["The genome-track preview is byte bounded."] if truncated_bytes else []
    return {"format": suffix.lstrip("."), "encoding": encoding, "headers_preview": headers, "records_preview": records}, warnings


def _csv_sample_shape(
    sample: str, delimiter: str, *, quotechar: str, skipinitialspace: bool, truncated: bool
) -> bool | None:
    """Use completed records to distinguish a contradiction from missing sample bytes."""
    stream = io.StringIO(sample, newline="")
    width = None
    count = 0
    try:
        for row in csv.reader(stream, delimiter=delimiter, quotechar=quotechar, skipinitialspace=skipinitialspace,
                              doublequote=True, escapechar=None, strict=True):
            if truncated and stream.tell() == len(sample) and not sample.endswith(("\r", "\n")):
                break
            if width is None:
                width = len(row)
            elif len(row) != width:
                return False
            count += 1
    except csv.Error:
        return None if truncated else False
    return None if truncated and count < 2 else True


def _table_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    suffix = path.suffix.lower()
    if suffix in {".parquet", ".feather", ".arrow"}:
        data, truncated = _read_head(path, min(max_bytes, 8192))
        magic = {"prefix": data[:8].hex(), "suffix_available": False}
        if path.stat().st_size >= 8:
            with path.open("rb") as handle:
                handle.seek(max(0, path.stat().st_size - 8))
                magic["suffix"] = handle.read(8).hex()
                magic["suffix_available"] = True
        return ({"format": suffix.lstrip("."), "binary_metadata": magic}, ["Column statistics and rows require a dedicated Arrow/Parquet reader; no schema is inferred from filename alone."] + (["Header preview truncated."] if truncated else []))
    data, truncated_bytes = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated_bytes)
    delimiter = "\t" if suffix == ".tsv" else ","
    options = {"quotechar": '"', "skipinitialspace": False, "doublequote": True, "escapechar": None}
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t;|")
        delimiter = dialect.delimiter
    except csv.Error:
        dialect = None
    if dialect is not None and (dialect.quotechar != '"' or dialect.skipinitialspace):
        sample = text[:8192]
        sample_truncated = truncated_bytes or len(text) > len(sample)
        if _csv_sample_shape(sample, delimiter, quotechar='"', skipinitialspace=False, truncated=sample_truncated) is False:
            candidates = [('"', True)]
            if dialect.quotechar != '"':
                candidates.append((dialect.quotechar, dialect.skipinitialspace))
            for quotechar, skipinitialspace in candidates:
                if _csv_sample_shape(sample, delimiter, quotechar=quotechar, skipinitialspace=skipinitialspace,
                                     truncated=sample_truncated) is True:
                    options.update(quotechar=quotechar, skipinitialspace=skipinitialspace)
                    break
    stream = io.StringIO(text, newline="")
    reader = csv.reader(stream, delimiter=delimiter, **options)
    try:
        rows, more = _bounded(reader, max_records + 1)
    except csv.Error as exc:
        raise ValueError(f"CSV records could not be parsed within runtime bounds: {exc}") from exc
    warnings = []
    header = rows[0] if rows else []
    body = rows[1:max_records + 1] if rows else []
    if truncated_bytes or more:
        warnings.append("The table preview is bounded and is not a complete row count.")
    if truncated_bytes:
        header_stream = io.StringIO(text, newline="")
        header_complete = False
        try:
            next(csv.reader(header_stream, delimiter=delimiter, strict=True, **options), [])
        except csv.Error:
            pass
        else:
            header_end = header_stream.tell()
            header_complete = header_end > 0 and text[header_end - 1] in "\r\n"
        warnings.append(_COMPLETE_TABLE_HEADER_WARNING if header_complete else
                        "The table header preview is byte bounded; columns may be incomplete.")
    return {"format": "delimited-text", "encoding": encoding, "delimiter": delimiter, "columns": header, "rows_preview": body}, warnings


def _png_dimensions(data: bytes) -> tuple[int, int] | None:
    if len(data) >= 24 and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    return None


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            break
        length = int.from_bytes(data[offset:offset + 2], "big")
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and offset + 7 < len(data):
            height = int.from_bytes(data[offset + 3:offset + 5], "big")
            width = int.from_bytes(data[offset + 5:offset + 7], "big")
            return width, height
        if length < 2:
            break
        offset += length
    return None


def _figure_preview(path: Path, max_bytes: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated = _read_head(path, min(max_bytes, 2 * 1024 * 1024))
    dimensions = _png_dimensions(data) or _jpeg_dimensions(data)
    preview: dict[str, Any] = {"format": path.suffix.lower().lstrip("."), "dimensions": None if dimensions is None else {"width": dimensions[0], "height": dimensions[1]}}
    warnings: list[str] = []
    if path.suffix.lower() == ".svg":
        text, encoding = _decode_text(data, truncated=truncated)
        preview["encoding"] = encoding
        preview["markup_preview"] = text[:5000]
        warnings.append("SVG markup is escaped in the runtime and is never executed as active content.")
    if dimensions is None and path.suffix.lower() not in {".svg"}:
        warnings.append("Image dimensions were not decoded by the bounded standard-library reader.")
    if truncated:
        warnings.append("Figure byte preview was truncated.")
    return preview, warnings


def _graph_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated = _read_head(path, max_bytes)
    warnings: list[str] = []
    try:
        text = _decode_text(data, truncated=truncated)[0]
    except ValueError:
        return {"format": "json", "parsed": False, "text_preview": data.decode("utf-8", errors="replace")[:5000]}, ["The bounded prefix contains malformed or incomplete Unicode graph text."]
    try:
        payload = json.loads(text.removeprefix("\ufeff"))
    except json.JSONDecodeError:
        return {"format": "json", "parsed": False, "text_preview": text[:5000]}, ["The bounded prefix did not contain a complete JSON graph."]
    nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
    edges = payload.get("edges", []) if isinstance(payload, dict) else []
    if isinstance(payload, dict) and "elements" in payload:
        elements = payload["elements"]
        if isinstance(elements, dict):
            nodes, edges = elements.get("nodes", []), elements.get("edges", [])
            if not {"nodes", "edges"}.intersection(elements):
                warnings.append("Unsupported Cytoscape elements layout; counts are unavailable.")
        elif isinstance(elements, list):
            nodes = [item for item in elements if isinstance(item, dict) and item.get("group") == "nodes"]
            edges = [item for item in elements if isinstance(item, dict) and item.get("group") == "edges"]
            if len(nodes) + len(edges) != len(elements):
                warnings.append("Cytoscape elements without a supported nodes/edges group were not counted.")
        else:
            warnings.append("Unsupported Cytoscape elements layout; counts are unavailable.")
            nodes, edges = [], []
    elif not isinstance(payload, dict) or not {"nodes", "edges"}.intersection(payload):
        warnings.append("JSON does not expose a supported graph layout; counts are unavailable.")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        warnings.append("JSON does not expose list-valued nodes and edges.")
        nodes, edges = [], []
    preview = {
        "format": "evidence-graph-json",
        "schema_version": payload.get("schema_version") if isinstance(payload, dict) else None,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_preview": nodes[:max_records],
        "edges_preview": edges[:max_records],
    }
    if truncated:
        warnings.append("Graph JSON happened to parse from a bounded prefix; verify full artifact validation before relying on counts.")
    return preview, warnings


def _trajectory_preview(path: Path, max_bytes: int, max_records: int) -> tuple[dict[str, Any], list[str]]:
    if path.suffix.lower() != ".xyz":
        data, truncated = _read_head(path, min(max_bytes, 4096))
        return ({"format": path.suffix.lower().lstrip("."), "header_hex": data[:128].hex()}, ["Binary trajectory frames require a format-specific reader; only bounded metadata is exposed."] + (["Header preview truncated."] if truncated else []))
    data, truncated = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated)
    lines = text.splitlines()
    offset = 0
    frames: list[dict[str, Any]] = []
    while offset < len(lines) and len(frames) < max_records:
        try:
            atom_count = int(lines[offset].strip())
        except (ValueError, IndexError):
            break
        comment = lines[offset + 1] if offset + 1 < len(lines) else ""
        atom_lines = lines[offset + 2:offset + 2 + atom_count]
        if len(atom_lines) < atom_count:
            break
        frames.append({"frame": len(frames), "atom_count": atom_count, "comment": comment, "atoms_preview": atom_lines[:20]})
        offset += atom_count + 2
    warnings = ["XYZ trajectory preview is byte or frame bounded."] if truncated or offset < len(lines) else []
    return {"format": "xyz", "encoding": encoding, "frames_preview": frames}, warnings


def _single_cell_preview(path: Path, max_bytes: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated = _read_head(path, min(max_bytes, 8192))
    is_hdf5 = data.startswith(b"\x89HDF\r\n\x1a\n")
    return ({"format": path.suffix.lower().lstrip("."), "container": "hdf5" if is_hdf5 else "unknown", "header_hex": data[:128].hex()}, ["AnnData/Loom matrices are not loaded without an explicit HDF5-aware backend; dimensions, layers, donors, and embeddings must not be guessed."] + (["Header preview truncated."] if truncated else []))


def _directory_preview(path: Path, max_records: int, media_type: str | None) -> tuple[dict[str, Any], list[str]]:
    descriptor = describe_directory(path, media_type=media_type)
    return ({"format": "directory-tree", "root_sha256": descriptor.root_sha256, "total_bytes": descriptor.total_bytes, "entry_count": descriptor.entry_count, "entries_preview": list(descriptor.entries[:max_records])}, ["Directory view is entry bounded."] if descriptor.entry_count > max_records else [])


def _text_preview(
    path: Path, max_bytes: int, max_records: int, *, media_type: str | None = None
) -> tuple[dict[str, Any], list[str]]:
    data, truncated = _read_head(path, max_bytes)
    text, encoding = _decode_text(data, truncated=truncated)
    if _is_json(path, media_type):
        # JSON strings may contain Unicode separators that are not physical line ends.
        lines = [line.removesuffix("\n") for line in io.StringIO(text, newline=None)]
    else:
        lines = text.splitlines()
    preview: dict[str, Any] = {"encoding": encoding, "line_count_in_prefix": len(lines), "lines_preview": [{"line": index + 1, "text": line} for index, line in enumerate(lines[:max_records])]}
    if _is_json(path, media_type) and not truncated:
        try:
            payload = json.loads(text.removeprefix("\ufeff"))
            preview["json_type"] = type(payload).__name__
            if isinstance(payload, dict):
                preview["top_level_keys"] = sorted(map(str, payload.keys()))[:max_records]
        except json.JSONDecodeError:
            preview["json_type"] = "invalid"
    return preview, ["Text preview is byte or line bounded."] if truncated or len(lines) > max_records else []


def _binary_preview(path: Path, max_bytes: int) -> tuple[dict[str, Any], list[str]]:
    data, truncated = _read_head(path, min(max_bytes, 4096))
    return {"header_hex": data[:256].hex(), "header_ascii": "".join(chr(byte) if 32 <= byte < 127 else "." for byte in data[:256])}, ["Binary preview is metadata only."] + (["Header preview truncated."] if truncated else [])


@dataclass(frozen=True)
class ArtifactRuntimeDescriptor:
    schema_version: int
    artifact_path: str
    artifact_sha256: str
    artifact_kind: str
    artifact_type: str
    media_type: str | None
    size_bytes: int
    viewer: str
    generated_at: str
    bounds: dict[str, int]
    preview: dict[str, Any]
    warnings: tuple[str, ...]
    evidence_boundary: str
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["warnings"] = list(self.warnings)
        return payload


def describe_runtime(
    path: Path,
    *,
    artifact_path: str | None = None,
    artifact_sha256: str | None = None,
    kind: str = "artifact",
    artifact_type: str | None = None,
    media_type: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_records: int = DEFAULT_MAX_RECORDS,
    generated_at: str | None = None,
) -> ArtifactRuntimeDescriptor:
    path = path.resolve()
    if not path.exists():
        raise ValueError(f"artifact does not exist: {path}")
    if max_bytes < 1 or max_records < 1:
        raise ValueError("max_bytes and max_records must be positive")
    if max_bytes > MAX_RUNTIME_BYTES:
        raise ValueError(f"max_bytes exceeds hard runtime ceiling: {MAX_RUNTIME_BYTES}")
    if max_records > MAX_RUNTIME_RECORDS:
        raise ValueError(f"max_records exceeds hard runtime ceiling: {MAX_RUNTIME_RECORDS}")
    relative = _safe_relative(artifact_path or path.name, "artifact_path")
    viewer = detect_viewer(path, kind=kind, media_type=media_type)
    if path.is_dir():
        directory = describe_directory(path, media_type=media_type)
        digest, size, resolved_type = directory.root_sha256, directory.total_bytes, "directory-tree"
    else:
        digest, size = stream_sha256(path)
        resolved_type = artifact_type or "file"
    if artifact_sha256 is not None and _sha256(artifact_sha256, "artifact_sha256") != digest:
        raise ValueError("artifact bytes do not match artifact_sha256")
    parsers = {
        "structure-3d": lambda: _structure_preview(path, max_bytes, max_records),
        "molecule-2d": lambda: _molecule_preview(path, max_bytes, max_records),
        "genome-track": lambda: _genome_preview(path, max_bytes, max_records),
        "single-cell": lambda: _single_cell_preview(path, max_bytes),
        "table": lambda: _table_preview(path, max_bytes, max_records),
        "figure": lambda: _figure_preview(path, max_bytes),
        "evidence-graph": lambda: _graph_preview(path, max_bytes, max_records),
        "trajectory": lambda: _trajectory_preview(path, max_bytes, max_records),
        "directory": lambda: _directory_preview(path, max_records, media_type),
        "text": lambda: _text_preview(path, max_bytes, max_records, media_type=media_type),
        "binary": lambda: _binary_preview(path, max_bytes),
    }
    preview, warnings = parsers[viewer]()
    if path.is_dir():
        if preview["root_sha256"] != digest:
            raise ValueError("artifact directory changed while building the preview")
    elif stream_sha256(path) != (digest, size):
        raise ValueError("artifact bytes changed while building the preview")
    material = {
        "schema_version": 1,
        "artifact_path": relative,
        "artifact_sha256": digest,
        "artifact_kind": kind,
        "artifact_type": resolved_type,
        "media_type": media_type,
        "size_bytes": size,
        "viewer": viewer,
        "generated_at": generated_at or _now(),
        "bounds": {"max_bytes": max_bytes, "max_records": max_records},
        "preview": preview,
        "warnings": warnings,
        "evidence_boundary": "This is a bounded derived view of hash-validated bytes. It does not prove a scientific claim, execute an edit, or replace format-specific validation.",
    }
    return ArtifactRuntimeDescriptor(
        **{**material, "warnings": tuple(warnings)},
        fingerprint=_fingerprint(material),
    )


def validate_runtime_descriptor(payload: Mapping[str, Any]) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported artifact runtime descriptor schema")
    _safe_relative(str(payload.get("artifact_path", "")), "artifact_path")
    _sha256(payload.get("artifact_sha256"), "artifact_sha256")
    viewer = str(payload.get("viewer", ""))
    if viewer not in VIEWER_SELECTIONS:
        raise ValueError(f"unsupported artifact viewer: {viewer}")
    if int(payload.get("size_bytes", -1)) < 0:
        raise ValueError("size_bytes must be non-negative")
    for field in ("artifact_kind", "artifact_type", "generated_at", "evidence_boundary"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"{field} is required")
    if not isinstance(payload.get("preview"), Mapping) or not isinstance(payload.get("bounds"), Mapping):
        raise ValueError("preview and bounds must be objects")
    warnings = payload.get("warnings")
    if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
        raise ValueError("warnings must be a string list")
    material = dict(payload)
    fingerprint = _sha256(material.pop("fingerprint", ""), "fingerprint")
    if _fingerprint(material) != fingerprint:
        raise ValueError("artifact runtime descriptor fingerprint mismatch")


def _validate_selector_coordinates(selector_type: str, selector: Mapping[str, Any]) -> None:
    """Reject contradictions in understood coordinates; retain opaque legacy shapes."""
    scalar_fields = {
        "row": ("row",), "column": ("column",), "cell": ("row", "column"),
        "line": ("line",), "frame": ("frame",),
    }
    endpoint_pairs = {
        "range": (("start", "end"), ("row_start", "row_end"), ("column_start", "column_end"),
                  ("start_row", "end_row"), ("start_column", "end_column")),
        "line-range": (("start", "end"), ("line_start", "line_end")),
        "byte-range": (("start", "end"),), "frame-range": (("start", "end"),),
        "interval": (("start", "end"),), "locus": (("start", "end"),),
    }
    pairs = endpoint_pairs.get(selector_type, ())
    endpoints = tuple(field for pair in pairs for field in pair)
    minimum = 1 if selector_type in {"line", "line-range"} else 0
    for field in (*scalar_fields.get(selector_type, ()), *endpoints):
        value = selector.get(field)
        if type(value) is int and value < minimum:
            qualifier = "positive" if minimum else "non-negative"
            raise ValueError(f"selector {field} must be a {qualifier} integer")
    for start, end in pairs:
        if type(selector.get(start)) is int and type(selector.get(end)) is int and selector[start] > selector[end]:
            raise ValueError("selector range is reversed")


def _validate_selection_region(payload: Mapping[str, Any], descriptor: Mapping[str, Any]) -> bool:
    """Resolve available coordinates without inventing undocumented index origins."""
    viewer, kind, selector = payload["viewer"], payload["selector_type"], payload["selector"]
    _validate_selector_coordinates(kind, selector)
    preview = descriptor["preview"]
    bytes_complete = descriptor["size_bytes"] <= descriptor["bounds"]["max_bytes"]

    def index(value: Any, count: int, label: str, *, one_based: bool = False, complete: bool = True) -> bool:
        # Table indices have no documented origin; only reject impossible values.
        if type(value) is not int:
            return False
        if value < int(one_based) or (complete and (count == 0 or value > count)):
            raise ValueError(f"selector {label} does not resolve in the inspected artifact region")
        return count > 0 and value <= count

    if viewer == "table" and preview.get("format") == "delimited-text":
        rows, columns = preview["rows_preview"], preview["columns"]
        rows_complete = bytes_complete and not descriptor["warnings"]
        columns_complete = bytes_complete or bool(rows) or _COMPLETE_TABLE_HEADER_WARNING in descriptor["warnings"]
        row_fields = (("row",) if kind in {"row", "cell"} else
                      ("row_start", "row_end", "start_row", "end_row", "start", "end") if kind == "range" else ())
        column_fields = (("column",) if kind in {"column", "cell"} else
                         ("column_start", "column_end", "start_column", "end_column") if kind == "range" else ())
        resolved = {}
        for field in row_fields:
            if field in selector:
                resolved[field] = index(selector[field], len(rows), field, complete=rows_complete)
        for field in column_fields:
            if field not in selector:
                continue
            value = selector[field]
            if isinstance(value, str):
                if columns_complete and value not in columns:
                    raise ValueError("selector column does not resolve in the artifact")
                resolved[field] = columns_complete and value in columns
            else:
                resolved[field] = index(value, len(columns), field, complete=columns_complete)
        if (kind == "cell" and rows_complete and type(selector.get("row")) is int
                and (isinstance(selector.get("column"), str) or type(selector.get("column")) is int)):
            row, column = selector["row"], selector["column"]
            row_indices = [item for item in (row - 1, row) if 0 <= item < len(rows)]
            column_indices = ([columns.index(column)] if isinstance(column, str) else
                              [item for item in (column - 1, column) if 0 <= item < len(columns)])
            if not any(col < len(rows[item]) for item in row_indices for col in column_indices):
                raise ValueError("selector cell does not resolve in the artifact")
        if kind in {"row", "column"}:
            return resolved.get(kind, False)
        if kind == "cell":
            return rows_complete and resolved.get("row", False) and resolved.get("column", False)
        pairs = (("start", "end"), ("row_start", "row_end"), ("start_row", "end_row"),
                 ("column_start", "column_end"), ("start_column", "end_column"))
        present = [pair for pair in pairs if any(field in selector for field in pair)]
        return bool(present) and all(all(resolved.get(field, False) for field in pair) for pair in present)
    elif viewer == "text":
        if kind in {"line", "line-range"}:
            fields = ("line",) if kind == "line" else ("start", "end", "line_start", "line_end")
            resolved = {field: index(selector[field], preview["line_count_in_prefix"], field,
                                     one_based=True, complete=bytes_complete)
                        for field in fields if field in selector}
            if kind == "line":
                return resolved.get("line", False)
            pairs = (("start", "end"), ("line_start", "line_end"))
            present = [pair for pair in pairs if any(field in selector for field in pair)]
            return bool(present) and all(all(resolved.get(field, False) for field in pair) for pair in present)
        elif kind == "json-pointer":
            if not _is_json(Path(descriptor["artifact_path"]), descriptor.get("media_type")):
                return False
            pointer = selector.get("pointer", selector.get("json_pointer"))
            if not isinstance(pointer, str):
                return False
            if pointer and not pointer.startswith("/"):
                raise ValueError("selector JSON pointer must be empty or start with /")
            segments = pointer.split("/")[1:] if pointer else []
            for segment in segments:
                for position, character in enumerate(segment):
                    if character == "~" and (position + 1 == len(segment) or segment[position + 1] not in "01"):
                        raise ValueError("invalid JSON pointer escape")
            lines = preview.get("lines_preview", [])
            starts_with_bom = bool(lines) and lines[0]["text"].startswith("\ufeff")
            if bytes_complete and preview.get("json_type") == "invalid" and not starts_with_bom:
                raise ValueError("selector JSON pointer does not resolve in the artifact")
            # Missing preview content establishes uncertainty, not non-existence.
            if not bytes_complete or len(lines) != preview["line_count_in_prefix"]:
                return False
            try:
                text = "\n".join(item["text"] for item in lines)
                value = json.loads(text.removeprefix("\ufeff"))
                for segment in segments:
                    segment = segment.replace("~1", "/").replace("~0", "~")
                    if isinstance(value, list):
                        if not segment.isascii() or not segment.isdecimal() or (len(segment) > 1 and segment[0] == "0"):
                            raise ValueError("invalid JSON pointer array index")
                        value = value[int(segment)]
                    elif isinstance(value, dict):
                        value = value[segment]
                    else:
                        raise ValueError("JSON pointer traverses a scalar")
            except (ValueError, KeyError, IndexError) as exc:
                raise ValueError("selector JSON pointer does not resolve in the artifact") from exc
            return True
    elif viewer == "binary" and kind == "byte-range":
        resolved = [index(selector.get(field), descriptor["size_bytes"], field) for field in ("start", "end")]
        return all(resolved)
    return False


def build_selection(
    descriptor: Mapping[str, Any],
    *,
    selector_type: str,
    selector: Mapping[str, Any],
    selected_by: str,
    reason: str,
    label: str = "",
    created_at: str | None = None,
) -> dict[str, Any]:
    if not isinstance(descriptor, Mapping):
        raise ValueError("selection descriptor must be an object")
    for field in ("artifact_path", "artifact_sha256", "artifact_kind", "artifact_type", "viewer",
                  "generated_at", "evidence_boundary", "fingerprint"):
        if not isinstance(descriptor.get(field), str):
            raise ValueError(f"selection descriptor {field} must be a string")
    if type(descriptor.get("schema_version")) is not int or descriptor["schema_version"] != 1:
        raise ValueError("selection descriptor schema_version: unsupported artifact runtime descriptor schema")
    if descriptor.get("media_type") is not None and not isinstance(descriptor["media_type"], str):
        raise ValueError("selection descriptor media_type must be a string or null")
    _json_value(dict(descriptor), "selection descriptor")
    if type(descriptor.get("size_bytes")) is not int or descriptor["size_bytes"] < 0:
        raise ValueError("selection descriptor size_bytes must be a non-negative integer")
    validate_runtime_descriptor(descriptor)
    max_bytes = descriptor["bounds"].get("max_bytes")
    if type(max_bytes) is not int or max_bytes < 1:
        raise ValueError("selection descriptor bounds.max_bytes must be a positive integer")
    viewer = str(descriptor["viewer"])
    preview = descriptor["preview"]
    if viewer == "table" and not isinstance(preview.get("format"), str):
        raise ValueError("selection descriptor preview.format must be a string")
    if viewer == "text" and "json_type" in preview and not isinstance(preview["json_type"], str):
        raise ValueError("selection descriptor preview.json_type must be a string")
    if viewer == "table" and preview.get("format") == "delimited-text":
        columns, rows = preview.get("columns"), preview.get("rows_preview")
        if not isinstance(columns, list) or not all(isinstance(value, str) for value in columns):
            raise ValueError("selection descriptor preview.columns must be a string list")
        if not isinstance(rows, list) or not all(
            isinstance(row, list) and all(isinstance(value, str) for value in row) for row in rows
        ):
            raise ValueError("selection descriptor preview.rows_preview must be a list of string lists")
    elif viewer == "text":
        count = preview.get("line_count_in_prefix")
        if type(count) is not int or count < 0:
            raise ValueError("selection descriptor preview.line_count_in_prefix must be a non-negative integer")
        lines = preview.get("lines_preview")
        if not isinstance(lines, list) or not all(
            isinstance(line, Mapping) and isinstance(line.get("text"), str) for line in lines
        ):
            raise ValueError("selection descriptor preview.lines_preview must contain text records")
    if selector_type not in VIEWER_SELECTIONS[viewer]:
        raise ValueError(f"selector {selector_type} is not valid for viewer {viewer}")
    if not isinstance(selector, Mapping) or not selector:
        raise ValueError("selector must be a non-empty object")
    _json_value(dict(selector), "selector")
    if len(reason) > MAX_REASON_CHARACTERS:
        raise ValueError("selection reason is too long")
    if len(_canonical_bytes(selector)) > MAX_SELECTION_BYTES:
        raise ValueError("selection payload exceeds the runtime limit")
    for value, field in ((selected_by, "selected_by"), (reason, "reason")):
        if not value.strip():
            raise ValueError(f"{field} is required")
    _validate_selection_region({"viewer": viewer, "selector_type": selector_type, "selector": selector}, descriptor)
    material = {
        "schema_version": 1,
        "artifact_path": descriptor["artifact_path"],
        "artifact_sha256": descriptor["artifact_sha256"],
        "viewer": viewer,
        "selector_type": selector_type,
        "selector": dict(selector),
        "selected_by": selected_by,
        "reason": reason,
        "label": label,
        "created_at": created_at or _now(),
        "status": "active",
        "evidence_boundary": "A selection identifies part of an artifact; it does not validate the selected interpretation.",
    }
    fingerprint = _fingerprint(material)
    return {**material, "selection_id": f"selection-{fingerprint[:20]}", "fingerprint": fingerprint}


def validate_selection(payload: Mapping[str, Any], artifact_hashes: Mapping[str, str] | None = None) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported artifact selection schema")
    artifact_path = _safe_relative(str(payload.get("artifact_path", "")), "artifact_path")
    artifact_sha = _sha256(payload.get("artifact_sha256"), "artifact_sha256")
    viewer = str(payload.get("viewer", ""))
    selector_type = str(payload.get("selector_type", ""))
    if viewer not in VIEWER_SELECTIONS or selector_type not in VIEWER_SELECTIONS[viewer]:
        raise ValueError("artifact selection viewer or selector_type is invalid")
    if not isinstance(payload.get("selector"), Mapping) or not payload["selector"]:
        raise ValueError("artifact selection selector must be non-empty")
    for field in ("selection_id", "selected_by", "reason", "created_at", "status", "evidence_boundary"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"selection {field} is required")
    material = dict(payload)
    fingerprint = _sha256(material.pop("fingerprint", ""), "selection fingerprint")
    material.pop("selection_id", None)
    if _fingerprint(material) != fingerprint:
        raise ValueError("artifact selection fingerprint mismatch")
    if str(payload["selection_id"]) != f"selection-{fingerprint[:20]}":
        raise ValueError("artifact selection ID does not match fingerprint")
    if artifact_hashes is not None and artifact_hashes.get(artifact_path) != artifact_sha:
        raise ValueError("stale artifact selection anchor")


def stale_selection(payload: Mapping[str, Any], artifact_hashes: Mapping[str, str]) -> dict[str, Any]:
    validate_selection(payload)
    result = dict(payload)
    if artifact_hashes.get(str(payload["artifact_path"])) != str(payload["artifact_sha256"]).lower():
        result["status"] = "stale-anchor"
    return result


def build_transform_proposal(
    selection: Mapping[str, Any],
    *,
    operation: str,
    parameters: Mapping[str, Any],
    reason: str,
    affected_steps: Iterable[str],
    expected_outputs: Iterable[str],
    proposed_by: str,
    requires_approval: bool = True,
    approval_boundary: str = "artifact mutation and rerun",
    created_at: str | None = None,
) -> dict[str, Any]:
    validate_selection(selection)
    if not operation.strip() or not reason.strip() or not proposed_by.strip():
        raise ValueError("operation, reason, and proposed_by are required")
    if not isinstance(parameters, Mapping):
        raise ValueError("parameters must be an object")
    _json_value(dict(parameters), "parameters")
    if len(reason) > MAX_REASON_CHARACTERS:
        raise ValueError("proposal reason is too long")
    if len(_canonical_bytes(parameters)) > MAX_PROPOSAL_PARAMETER_BYTES:
        raise ValueError("proposal parameters exceed the runtime limit")
    steps = sorted({_safe_relative(str(item), "affected step") for item in affected_steps})
    outputs = sorted({_safe_relative(str(item), "expected output") for item in expected_outputs})
    if not steps:
        raise ValueError("affected_steps must be non-empty")
    material = {
        "schema_version": 1,
        "selection_id": selection["selection_id"],
        "selection_fingerprint": selection["fingerprint"],
        "artifact_path": selection["artifact_path"],
        "artifact_sha256": selection["artifact_sha256"],
        "operation": operation,
        "parameters": dict(parameters),
        "reason": reason,
        "affected_steps": steps,
        "expected_outputs": outputs,
        "proposed_by": proposed_by,
        "requires_approval": bool(requires_approval),
        "approval_boundary": approval_boundary,
        "created_at": created_at or _now(),
        "status": "proposed",
        "executed": False,
        "evidence_boundary": "This proposal describes a possible transform. It does not mutate bytes, execute a workflow, or establish a result.",
    }
    fingerprint = _fingerprint(material)
    return {**material, "proposal_id": f"transform-{fingerprint[:20]}", "fingerprint": fingerprint}


def validate_transform_proposal(payload: Mapping[str, Any], selection: Mapping[str, Any] | None = None) -> None:
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported transform proposal schema")
    for field in ("proposal_id", "selection_id", "selection_fingerprint", "artifact_path", "artifact_sha256", "operation", "reason", "proposed_by", "approval_boundary", "created_at", "status", "evidence_boundary"):
        if not str(payload.get(field, "")).strip():
            raise ValueError(f"transform proposal {field} is required")
    _safe_relative(str(payload["artifact_path"]), "artifact_path")
    _sha256(payload["artifact_sha256"], "artifact_sha256")
    _sha256(payload["selection_fingerprint"], "selection_fingerprint")
    if payload.get("executed") is not False or payload.get("status") != "proposed":
        raise ValueError("a transform proposal must remain non-executing and proposed")
    for field in ("affected_steps", "expected_outputs"):
        if not isinstance(payload.get(field), list) or (field == "affected_steps" and not payload[field]):
            raise ValueError(f"{field} must be a {'non-empty ' if field == 'affected_steps' else ''}list")
    if not isinstance(payload.get("parameters"), Mapping):
        raise ValueError("transform proposal parameters must be an object")
    material = dict(payload)
    fingerprint = _sha256(material.pop("fingerprint", ""), "transform fingerprint")
    material.pop("proposal_id", None)
    if _fingerprint(material) != fingerprint or str(payload["proposal_id"]) != f"transform-{fingerprint[:20]}":
        raise ValueError("transform proposal fingerprint or ID mismatch")
    if selection is not None:
        validate_selection(selection)
        if payload["selection_id"] != selection["selection_id"] or payload["selection_fingerprint"] != selection["fingerprint"]:
            raise ValueError("transform proposal references a different selection")
        if payload["artifact_path"] != selection["artifact_path"] or payload["artifact_sha256"] != selection["artifact_sha256"]:
            raise ValueError("transform proposal artifact differs from its selection")


def render_runtime_html(descriptor: Mapping[str, Any], *, title: str | None = None) -> str:
    validate_runtime_descriptor(descriptor)
    viewer = html.escape(str(descriptor["viewer"]))
    artifact = html.escape(str(descriptor["artifact_path"]))
    heading = html.escape(title or f"Scientific artifact: {descriptor['artifact_path']}")
    preview_json = html.escape(json.dumps(descriptor["preview"], indent=2, sort_keys=True, ensure_ascii=False))
    warnings = "".join(f"<li>{html.escape(str(item))}</li>" for item in descriptor.get("warnings", [])) or "<li>None</li>"
    metadata = {
        "SHA-256": descriptor["artifact_sha256"],
        "Kind": descriptor["artifact_kind"],
        "Type": descriptor["artifact_type"],
        "Media type": descriptor.get("media_type"),
        "Size": descriptor["size_bytes"],
        "Viewer": descriptor["viewer"],
        "Fingerprint": descriptor["fingerprint"],
    }
    cards = "".join(f"<div class='card'><strong>{html.escape(str(key))}</strong><br><code>{html.escape(str(value))}</code></div>" for key, value in metadata.items())
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{heading}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#17202a}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.7rem}}.card{{border:1px solid #ccd4dc;border-radius:.4rem;padding:.7rem;overflow:auto}}pre{{white-space:pre-wrap;word-break:break-word;border:1px solid #ccd4dc;background:#f6f8fa;padding:1rem;max-height:70vh;overflow:auto}}code{{font-size:.78rem}}.boundary{{border-left:4px solid #8a5a00;padding:.7rem;background:#fff8e6}}</style></head>
<body><h1>{heading}</h1><p><strong>Artifact:</strong> {artifact} · <strong>Viewer:</strong> {viewer}</p>
<div class='grid'>{cards}</div><h2>Warnings</h2><ul>{warnings}</ul><h2>Bounded preview</h2><pre>{preview_json}</pre>
<p class='boundary'>{html.escape(str(descriptor['evidence_boundary']))}</p></body></html>\n"""
