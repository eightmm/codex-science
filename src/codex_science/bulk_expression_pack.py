"""Offline synthetic bulk-expression reference; statistical evidence only."""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from pathlib import Path, PurePosixPath

from codex_science.cli_io import DEFAULT_MAX_JSON_BYTES


STAGES = ("01-design", "02-qc", "03-freeze", "04-testing", "05-enrichment", "06-handoff")
IDENTITIES = ("organism", "genome_version", "annotation_version", "identifier_namespace")
CLAIM_OVERREACH = re.compile(
    r"\b(caus\w*|mechanis\w*|driv(?:e|es|en|ing)|physical[\s-]+validity|clinical\w*|truth|"
    r"therap\w*|efficac\w*|effectiv\w*|treatment\w*|induc\w*|determin\w*|regulat\w*|"
    r"activat\w*|repress\w*|responsib\w*|biomarker\w*|prognos\w*|predict\w*)\b", re.I,
)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{code}: {message}")


def _object(value, label: str) -> dict:
    _require(isinstance(value, dict), "invalid-record", f"{label} must be an object")
    return value


def _list(value, label: str, *, empty: bool = False) -> list:
    _require(isinstance(value, list) and (empty or bool(value)), "invalid-record", f"{label} must be a list")
    return value


def _text(value, label: str) -> str:
    _require(isinstance(value, str) and bool(value.strip()), "invalid-record", f"{label} must be nonempty text")
    return value


def _names(value, label: str, *, empty: bool = False) -> list[str]:
    items = _list(value, label, empty=empty)
    for item in items:
        _text(item, label)
    _require(len(items) == len(set(items)), "invalid-record", f"{label} contains duplicates")
    return items


def _number(value, label: str, *, lower: float = 0, upper: float = math.inf) -> float:
    _require(type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper,
             "invalid-record", f"{label} must be finite in [{lower}, {upper}]")
    return value


def specification_hash(specification: dict) -> str:
    """Hash the canonical pre-test specification, including thresholds and families."""
    try:
        content = json.dumps(specification, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise ValueError("invalid-record: specification must be finite JSON") from error


def _pairs(items):
    result = {}
    for name, value in items:
        _require(name not in result, "invalid-record", f"duplicate JSON key: {name}")
        result[name] = value
    return result


def _json_object(raw: bytes, label: str) -> dict:
    try:
        return _object(json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs), label)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ValueError(f"invalid-record: {label} must be a UTF-8 JSON object: {error}") from error


def _json_bytes(path: Path) -> bytes:
    _require(path.is_file(), "invalid-record", "input must be an available regular JSON file")
    with path.open("rb") as handle:
        raw = handle.read(DEFAULT_MAX_JSON_BYTES + 1)
    _require(len(raw) <= DEFAULT_MAX_JSON_BYTES, "invalid-record", "input exceeds the repository JSON size bound")
    return raw


def _input(root: Path, ref, schema: str) -> dict:
    ref = _object(ref, "input identity")
    relative = PurePosixPath(_text(ref.get("path"), "input path"))
    _require(not relative.is_absolute() and ".." not in relative.parts, "input-identity", "input path must be relative")
    target = root / relative
    _require(target.resolve().is_relative_to(root.resolve()) and target.is_file(),
             "unavailable", "input must be an available file within the fixture bundle")
    raw = _json_bytes(target)
    _require(hashlib.sha256(raw).hexdigest() == ref.get("sha256"), "input-identity", "input hash mismatch")
    value = _json_object(raw, "input")
    _require(value.get("schema") == schema and value.get("fixture") is True,
             "invalid-record", "reference inputs must be labelled synthetic fixtures")
    return value


def _specification(spec, genes: list[str]) -> dict:
    spec = _object(spec, "specification")
    contrast = _names(spec.get("contrast"), "contrast")
    _require(len(contrast) == 2, "invalid-record", "contrast requires two groups")
    _require(spec.get("model") == "welch-log2-cpm", "unsupported-model", "reference supports only welch-log2-cpm")
    minimum = spec.get("minimum_replicates")
    _require(type(minimum) is int and minimum >= 2, "invalid-record", "minimum_replicates must be an integer at least two")
    for field in ("alpha", "enrichment_alpha"):
        _number(spec.get(field), field, upper=1)
    qc = _object(spec.get("qc"), "qc")
    for field in ("min_library_size", "min_detected_genes", "max_log_library_deviation"):
        _number(qc.get(field), field)
    _require(spec.get("correction") == "BH", "multiple-testing", "BH correction is mandatory")
    family = _names(spec.get("correction_genes"), "correction_genes")
    _require(set(family) == set(genes), "multiple-testing", "correct the complete tested family; no post-test subset")
    background = spec.get("enrichment_background")
    _require(isinstance(background, list) and bool(background), "enrichment-background", "explicit background universe required")
    background = _names(background, "enrichment_background")
    _require(set(genes) == set(background), "enrichment-background", "background must equal the tested gene universe")
    return spec


def _claims(claims) -> None:
    claims = _list(claims, "claims", empty=True)
    for value in claims:
        claim = _object(value, "claim")
        _text(claim.get("id"), "claim id")
        text = _text(claim.get("text"), "claim text")
        _require(isinstance(claim.get("kind"), str) and claim["kind"] in {"descriptive", "associational"}
                 and CLAIM_OVERREACH.search(text) is None,
                 "claim-boundary", "only descriptive or associational wording is allowed; no mechanistic, therapeutic, efficacy or outcome assertions")
        basis = claim.get("evidence_basis")
        _require(isinstance(basis, str) and basis in {"statistical", "unavailable"}, "claim-boundary", "only statistical evidence or unavailable records are allowed")
        _require(isinstance(claim.get("status"), str) and claim["status"] in {"planned", "supported", "suggestive", "conflicting", "unsupported", "withdrawn", "unavailable"},
                 "claim-boundary", "claim status must preserve statistical uncertainty; review approval is never truth")
        _require(basis != "unavailable" or claim.get("status") == "unavailable",
                 "unavailable-evidence", "absence of a record is unavailable, never negative evidence")
    _names([claim["id"] for claim in claims], "claim ids", empty=True)


def _prepare(path: Path) -> tuple[dict, dict, dict, list, list, dict]:
    record = _json_object(_json_bytes(path), "pack")
    _require(record.get("schema") == "bulk-expression-pack-v1" and record.get("fixture") is True,
             "invalid-record", "reference accepts only bulk-expression-pack-v1 synthetic fixtures")
    _require(record.get("stages") == list(STAGES), "stage-order", "six stages must retain their fixed order")
    inputs = _object(record.get("inputs"), "inputs")
    expression = _input(path.parent, inputs.get("expression"), "bulk-expression-counts-v1")
    collection = _input(path.parent, inputs.get("gene_sets"), "bulk-expression-gene-sets-v1")
    design = _object(record.get("design"), "design")
    for field in IDENTITIES:
        identity = _text(design.get(field), field)
        _require(identity == expression.get(field) == collection.get(field), "identifier-mismatch", f"{field} differs between design, counts and gene sets")
    samples = _list(design.get("samples"), "samples")
    for sample in samples:
        _object(sample, "sample")
        for field in ("id", "condition", "batch"):
            _text(sample.get(field), f"sample {field}")
        _require(sample.get("covariates") == {}, "unsupported-covariates", "reference cannot adjust covariates; use a gated external model")
    ids = _names([sample["id"] for sample in samples], "sample ids")
    _require(expression.get("sample_ids") == ids, "invalid-record", "sample order must match counts")
    rows = _list(expression.get("genes"), "genes")
    for row in rows:
        _object(row, "gene row")
        counts = _list(row.get("counts"), "counts")
        _require(len(counts) == len(samples), "invalid-record", "count vector length differs from samples")
        for count in counts:
            _require(type(count) is int and count >= 0, "invalid-record", "counts must be nonnegative integers")
    genes = _names([row.get("id") for row in rows], "gene ids")
    frozen = _specification(record.get("frozen_spec"), genes)
    _require(record.get("frozen_sha256") == specification_hash(frozen), "freeze-hash", "frozen specification hash mismatch")
    _require(record.get("freeze_before_testing") is True, "freeze-order", "freeze must precede any test statistic")
    spec = _specification(record.get("analysis_spec"), genes)
    exploratory = record.get("exploratory")
    _require(type(exploratory) is bool, "invalid-record", "exploratory must be boolean")
    _require(frozen == spec or exploratory, "post-result-change", "changed contrast or thresholds require an exploratory label")
    _claims(record.get("claims"))
    sets = _list(collection.get("sets"), "gene sets")
    for gene_set in sets:
        _object(gene_set, "gene set")
        _text(gene_set.get("id"), "gene set id")
        _names(gene_set.get("genes"), "set members", empty=True)
    _names([item["id"] for item in sets], "gene set ids")
    return record, expression, collection, samples, rows, spec


def _qc(record: dict, samples: list, rows: list, spec: dict) -> tuple[list[int], list[dict]]:
    limits = spec["qc"]
    libraries = [sum(row["counts"][index] for row in rows) for index in range(len(samples))]
    _require(all(libraries), "qc-failed", "zero library size prevents normalization")
    center = statistics.median([math.log2(size) for size in libraries])
    removals = _list(record.get("removed_samples"), "removed_samples", empty=True)
    removed = {}
    for item in removals:
        item = _object(item, "sample removal")
        sample_id = _text(item.get("sample_id"), "removed sample")
        _require(sample_id in {sample["id"] for sample in samples} and sample_id not in removed,
                 "outlier-removal", "removed sample must exist exactly once")
        _require(isinstance(item.get("reason"), str) and bool(item["reason"].strip())
                 and item.get("threshold") == limits["max_log_library_deviation"],
                 "outlier-removal", "outlier removal needs a recorded reason and the frozen threshold")
        removed[sample_id] = item
    keep, measurements = [], []
    for index, sample in enumerate(samples):
        deviation = abs(math.log2(libraries[index]) - center)
        detected = sum(row["counts"][index] > 0 for row in rows)
        excluded = sample["id"] in removed
        if excluded:
            _require(deviation > limits["max_log_library_deviation"], "outlier-removal", "removal does not meet frozen outlier threshold")
        else:
            _require(libraries[index] >= limits["min_library_size"] and detected >= limits["min_detected_genes"]
                     and deviation <= limits["max_log_library_deviation"], "qc-failed", "sample failed a pre-stated QC threshold")
            keep.append(index)
        measurements.append({"sample_id": sample["id"], "library_size": libraries[index], "detected_genes": detected,
                             "log_library_deviation": deviation, "excluded": excluded, "removal": removed.get(sample["id"])})
    groups = spec["contrast"]
    _require({samples[i]["condition"] for i in keep} == set(groups), "invalid-record", "retained groups must match contrast")
    _require(all(sum(samples[i]["condition"] == group for i in keep) >= spec["minimum_replicates"] for group in groups),
             "insufficient-replicates", "fewer replicates than the declared minimum; significance refused")
    batches = [{samples[i]["batch"] for i in keep if samples[i]["condition"] == group} for group in groups]
    _require(bool(batches[0] & batches[1]), "batch-confounding", "batch perfectly confounded with condition; effect refused")
    return keep, measurements


def benjamini_hochberg(values: list[float]) -> list[float]:
    """Adjust the complete supplied hypothesis family, retaining its order."""
    for value in values:
        _number(value, "p value", upper=1)
    order = sorted(range(len(values)), key=values.__getitem__)
    adjusted = [1.0] * len(values)
    running = 1.0
    for rank in range(len(values), 0, -1):
        index = order[rank - 1]
        running = min(running, values[index] * len(values) / rank)
        adjusted[index] = running
    return adjusted


def _beta_fraction(a: float, b: float, x: float) -> float:
    # Continued fraction for regularized incomplete beta (two-sided Student t).
    tiny = 1e-300
    c = 1.0
    d = 1 - (a + b) * x / (a + 1)
    d = 1 / (d if abs(d) > tiny else tiny)
    result = d
    for index in range(1, 201):
        for term in (index * (b - index) * x / ((a + 2 * index - 1) * (a + 2 * index)),
                     -(a + index) * (a + b + index) * x / ((a + 2 * index) * (a + 2 * index + 1))):
            d = 1 + term * d
            c = 1 + term / c
            d = 1 / (d if abs(d) > tiny else tiny)
            c = c if abs(c) > tiny else tiny
            delta = d * c
            result *= delta
        if abs(delta - 1) <= 3e-14:
            return result
    raise ValueError("numerical-failure: incomplete beta did not converge")


def welch_test(first: list[float], second: list[float]) -> dict:
    """Two-sided Welch, second minus first; two constant groups are untestable (p=1)."""
    for group in (first, second):
        _require(isinstance(group, list) and len(group) >= 2, "invalid-record", "Welch requires two replicates per group")
        for value in group:
            _number(value, "log expression", lower=-math.inf)
    difference = statistics.mean(second) - statistics.mean(first)
    a, b = statistics.variance(first) / len(first), statistics.variance(second) / len(second)
    if a + b == 0:
        return {"log2_fold_change": difference, "t": None, "df": None, "p_value": 1.0}
    t = difference / math.sqrt(a + b)
    df = (a + b) ** 2 / (a * a / (len(first) - 1) + b * b / (len(second) - 1))
    x = df / (df + t * t)
    aa, bb = df / 2, 0.5
    if x == 1:
        p = 1.0
    elif x == 0:
        p = 0.0
    else:
        factor = math.exp(math.lgamma(aa + bb) - math.lgamma(aa) - math.lgamma(bb) + aa * math.log(x) + bb * math.log1p(-x))
        p = (factor * _beta_fraction(aa, bb, x) / aa if x < (aa + 1) / (aa + bb + 2)
             else 1 - factor * _beta_fraction(bb, aa, 1 - x) / bb)
    return {"log2_fold_change": difference, "t": t, "df": df, "p_value": min(1.0, max(0.0, p))}


def hypergeometric_tail(population: int, members: int, draws: int, overlap: int) -> float:
    """Probability of at least overlap successes without replacement."""
    _require(all(type(v) is int for v in (population, members, draws, overlap))
             and population >= 0 and 0 <= members <= population and 0 <= draws <= population
             and 0 <= overlap <= min(members, draws), "invalid-record", "invalid hypergeometric counts")
    denominator = math.comb(population, draws)
    return min(1.0, sum(math.comb(members, k) * math.comb(population - members, draws - k)
                        for k in range(max(overlap, draws - (population - members)), min(members, draws) + 1)) / denominator)


def analyze_bulk_expression(path: Path | str) -> dict:
    """Validate all controls before computing statistics; never execute external tools."""
    path = Path(path)
    record, expression, collection, samples, rows, spec = _prepare(path)
    keep, qc = _qc(record, samples, rows, spec)
    differential = []
    for row in rows:
        groups = [[math.log2(1 + row["counts"][i] * 1_000_000 / qc[i]["library_size"])
                   for i in keep if samples[i]["condition"] == group] for group in spec["contrast"]]
        differential.append({"gene_id": row["id"], **welch_test(*groups)})
    for row, q_value in zip(differential, benjamini_hochberg([row["p_value"] for row in differential])):
        row.update(q_value=q_value, significant=row["t"] is not None and q_value <= spec["alpha"])
    selected = {row["gene_id"] for row in differential if row["significant"]}
    background = set(spec["enrichment_background"])
    enrichment = []
    for gene_set in collection["sets"]:
        members = set(gene_set["genes"]) & background
        overlap = selected & members
        enrichment.append({"set_id": gene_set["id"], "overlap": sorted(overlap), "members_in_background": len(members),
                           "p_value": hypergeometric_tail(len(background), len(members), len(selected), len(overlap))})
    for row, q_value in zip(enrichment, benjamini_hochberg([row["p_value"] for row in enrichment])):
        row.update(q_value=q_value, significant=q_value <= spec["enrichment_alpha"])
    return {"schema": "bulk-expression-result-v1", "fixture": True, "evidence_level": "statistical-only",
            "inputs": record["inputs"], "frozen_sha256": record["frozen_sha256"], "analysis_sha256": specification_hash(spec),
            "stages": list(STAGES), "exploratory": record["exploratory"], "qc": qc,
            "differential": differential, "enrichment": enrichment, "claims": record["claims"],
            "review": "unavailable", "limitations": ["Synthetic fixture; no biological, physical or clinical validation.",
            "Welch on log2(CPM+1) does not model count dispersion or adjust batch/covariates.",
            "Enrichment depends on selection, universe and gene correlation; association is never causality.",
            "Freeze records are declarations with hashes, not independent proof of historical timing.",
            "Independent science-review and rigor classification remain with the coordinator."] + [
            f"Untestable gene {row['gene_id']}: zero within-group variance in both groups; "
            "Welch is undefined. Retained in BH with p=1 and never selected as significant."
            for row in differential if row["t"] is None]}


def validate_bulk_expression_pack(path: Path | str) -> dict:
    """Return the unreviewed statistical reference result or a labelled ValueError."""
    try:
        return analyze_bulk_expression(path)
    except (OSError, RuntimeError, OverflowError, RecursionError, UnicodeError) as error:
        raise ValueError(f"invalid-pack: {type(error).__name__}") from error
