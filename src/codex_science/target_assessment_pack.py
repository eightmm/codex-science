"""Read-only checks for a target-assessment workflow's recorded handoffs.

These checks establish internal consistency of declared evidence, never target
validity or independent review. They neither retrieve nor execute anything.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import stat
from pathlib import Path, PurePosixPath

from codex_science.checkpoints import validate_checkpoint
from codex_science.evidence import CLAIM_STATUSES


STAGES = tuple(f"stage-{i:02d}" for i in range(1, 7))
SKILLS = (
    ("biomedical-entity-normalization",),
    ("opentargets-search", "gwas-catalog-search", "gnomad-search", "clinvar-search"),
    ("expression-cell-context", "hpa-search", "gtex-search"),
    ("pdb-search", "alphafold-structure-analysis", "chembl-search", "pubchem-search"),
    ("openfda-search", "clinical-trials-search", "translational-pharmacology-evidence", "indication-dossier"),
    (),
)
IDENTITY_FIELDS = ("uniprot", "ensembl", "hgnc", "species", "isoform", "indication_id")
PATIENT_BOUNDARY = "This memo never recommends treatment for a patient."
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def _refuse(code, message):
    raise ValueError(f"{code}: {message}")


def _require(condition, message, code="PACK_FORMAT"):
    if not condition:
        _refuse(code, message)


def _object(value, label):
    _require(isinstance(value, dict), f"{label} must be an object")
    return value


def _rows(value, label):
    _require(isinstance(value, list), f"{label} must be a list")
    return value


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _strings(value):
    return isinstance(value, list) and all(_text(item) for item in value) and len(set(value)) == len(value)


def _enum(value, choices, label):
    _require(isinstance(value, str) and value in choices, f"invalid {label}")


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _pairs(items):
    result = {}
    for name, value in items:
        _require(name not in result, f"duplicate JSON key: {name}")
        result[name] = value
    return result


def _json(raw):
    try:
        return _object(json.loads(raw, object_pairs_hook=_pairs,
                                  parse_constant=lambda value: _refuse("PACK_FORMAT", "non-finite JSON")), "JSON")
    except (UnicodeError, ValueError, RecursionError) as error:
        _refuse("PACK_FORMAT", f"invalid JSON: {error}")


class _Bundle:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.reads = {}

    def read(self, ref):
        _object(ref, "artifact reference")
        _require(set(ref) == {"path", "sha256"}, "reference requires path and sha256")
        relative = ref["path"]
        _require(_text(relative), "empty artifact path", "PACK_PATH")
        path = PurePosixPath(relative)
        _require(not path.is_absolute() and ".." not in path.parts and str(path) == relative
                 and "\\" not in relative, "artifact path must be canonical and relative", "PACK_PATH")
        raw = self._read_bytes(relative)
        digest = hashlib.sha256(raw).hexdigest()
        if ref["sha256"] is not None:
            _require(ref["sha256"] == digest, f"hash mismatch: {relative}", "PACK_HASH")
        else:
            _require(relative == "dossier.json", "missing artifact hash", "PACK_HASH")
        self.reads[relative] = digest
        return _json(raw)

    def _read_bytes(self, relative):
        target = self.root / relative
        _require(not any(part.is_symlink() for part in [target, *target.parents] if part != self.root),
                 "symlink artifact refused", "PACK_PATH")
        _require(target.resolve().is_relative_to(self.root), "artifact escapes bundle", "PACK_PATH")
        try:
            info = target.lstat()
            _require(stat.S_ISREG(info.st_mode), "artifact must be a regular file", "PACK_INPUT")
            _require(info.st_size <= MAX_ARTIFACT_BYTES, "artifact exceeds 64 MiB", "PACK_INPUT")
            raw = target.read_bytes()
        except OSError as error:
            _refuse("PACK_INPUT", f"cannot read {relative}: {error.strerror}")
        _require(len(raw) <= MAX_ARTIFACT_BYTES, "artifact exceeds 64 MiB", "PACK_INPUT")
        return raw

    def unchanged(self):
        for relative, digest in self.reads.items():
            try:
                current = hashlib.sha256(self._read_bytes(relative)).hexdigest()
            except ValueError:
                _refuse("PACK_CHANGED", "artifact became unreadable during validation")
            _require(current == digest, "artifact changed during validation", "PACK_CHANGED")


def _check_identity(target, identity, sources):
    _require(set(target) == set(IDENTITY_FIELDS) and all(_text(target.get(k)) for k in IDENTITY_FIELDS),
             "complete target/indication identity required", "TARGET_IDENTITY")
    for other in [identity.get("target"), *(source.get("target") for source in sources)]:
        _require(other == target, "target, species, isoform or indication differs across sources", "TARGET_IDENTITY")


def _check_missingness(stages, sources):
    for stage in stages:
        observations = _rows(stage.get("observations"), "observations")
        expected = stage["source_ids"]
        _require(len(observations) == len(expected), "one observation per source required", "EVIDENCE_PRESERVATION")
        observed = []
        for item in observations:
            item = _object(item, "observation")
            source_id = item.get("source_id")
            _require(isinstance(source_id, str) and source_id in expected, "unknown observation source")
            observed.append(source_id)
            source = sources[source_id]
            if not source["records"]:
                _require(item.get("status") == "unavailable", "no record must remain unavailable", "SOURCE_UNAVAILABLE")
            else:
                _require(item.get("status") == "recorded", "returned evidence cannot be hidden", "EVIDENCE_PRESERVATION")
            _require(item.get("record_ids") == [row["id"] for row in source["records"]],
                     "preserve every returned record, including failed controls and negative results", "EVIDENCE_PRESERVATION")
        _require(len(set(observed)) == len(expected), "repeated observation source", "EVIDENCE_PRESERVATION")


def _check_genetics(genetics, sources, records):
    selected = genetics.get("support_record_ids")
    _require(_strings(selected), "genetic support IDs required", "GENETIC_DEPENDENCE")
    chosen = []
    for identifier in selected:
        _require(identifier in records and records[identifier][0]["id"] in genetics["source_ids"],
                 "genetic support must cite this stage", "GENETIC_DEPENDENCE")
        source, row = records[identifier]
        _require(row["kind"] == "associational" and row["result"] == "association",
                 "non-association cannot count as genetic support", "GENETIC_DEPENDENCE")
        chosen.append(source)
    groups = []
    for source in chosen:
        # Unknown cohorts share one unresolved group; portals never create replication.
        labels = {"cohort:" + x for x in source["cohorts"] or ["unknown"]}
        labels |= {"dependency:" + x for x in source["dependency_groups"]}
        labels.add("source:" + source["id"])
        overlaps = [group for group in groups if group & labels]
        for group in overlaps:
            labels |= group
            groups.remove(group)
        groups.append(labels)
    count = genetics.get("independent_support_count")
    _require(type(count) is int and 0 <= count <= len(groups),
             "independent support exceeds cohort/source dependency groups or is malformed", "GENETIC_DEPENDENCE")


def _check_availability(availability):
    _require(availability.get("interpretation") == "availability-only",
             "structure or ligand availability is not target druggability", "AVAILABILITY_NOT_DRUGGABILITY")


def _check_context(context, sources):
    for identifier in context["source_ids"]:
        for row in sources[identifier]["records"]:
            fields = row.get("context")
            _require(isinstance(fields, dict) and all(_text(fields.get(key)) for key in
                     ("tissue", "cell_state", "assay", "unit", "normalisation"))
                     and type(fields.get("donor_count")) is int and fields["donor_count"] > 0,
                     "recorded expression needs tissue, cell state, assay, units, normalisation and positive donor count", "EXPRESSION_CONTEXT")


def _check_potency(availability, records):
    for group in _rows(availability.get("potency_groups"), "potency groups"):
        group = _object(group, "potency group")
        ids = group.get("record_ids")
        _require(_strings(ids) and bool(ids), "potency group must cite records", "POTENCY_MIXING")
        scales = set()
        for identifier in ids:
            _require(identifier in records, "unknown potency record", "POTENCY_MIXING")
            source, row = records[identifier]
            _require(source["id"] in availability["source_ids"], "potency belongs to availability stage", "POTENCY_MIXING")
            potency = row.get("potency")
            _require(isinstance(potency, dict) and _number(potency.get("value"))
                     and _text(potency.get("assay")) and _text(potency.get("unit")),
                     "potency requires a finite nonnegative value, assay and unit", "POTENCY_MIXING")
            scales.add((potency["assay"], potency["unit"]))
        normalisation = group.get("normalisation")
        if len(scales) > 1 or normalisation is not None:
            _require(isinstance(normalisation, dict) and _text(normalisation.get("rationale"))
                     and _text(normalisation.get("assay")) and _text(normalisation.get("unit"))
                     and isinstance(normalisation.get("values"), dict)
                     and set(normalisation["values"]) == set(ids)
                     and all(_number(value) for value in normalisation["values"].values()),
                     "mixed assay types or units require explicit per-record normalisation and rationale", "POTENCY_MIXING")


def _check_direction(genetics, memo, records):
    expected = {("loss-of-function", "protective"): "inhibition", ("gain-of-function", "risk"): "inhibition",
                ("gain-of-function", "protective"): "activation", ("loss-of-function", "risk"): "activation"}
    _enum(memo.get("modality"), {"inhibition", "activation"}, "modality")
    mismatched = []
    for identifier in genetics["support_record_ids"]:
        effect = _object(records[identifier][1].get("effect"), "genetic effect")
        direction = (effect.get("perturbation"), effect.get("outcome"))
        _require(all(isinstance(x, str) for x in direction), "effect direction must be text")
        if expected.get(direction) != memo["modality"]:
            mismatched.append(identifier)
    if mismatched:
        rationale = memo.get("direction_rationale")
        _require(isinstance(rationale, dict) and _text(rationale.get("text"))
                 and _strings(rationale.get("evidence")) and set(mismatched) <= set(rationale["evidence"])
                 and set(rationale["evidence"]) <= set(records),
                 "genetic effect direction does not match modality; explicit cited rationale required", "MODALITY_DIRECTION")


def _check_go(genetics, safety, memo, records):
    _enum(memo.get("decision"), {"go", "no-go", "hold"}, "decision")
    liabilities = _rows(safety.get("liabilities"), "liabilities")
    for item in liabilities:
        item = _object(item, "liability")
        _require(_text(item.get("id")), "liability ID required")
        _enum(item.get("severity"), {"critical", "major", "minor"}, "liability severity")
        _enum(item.get("status"), {"open", "closed"}, "liability status")
        _require(_strings(item.get("evidence")) and bool(item["evidence"])
                 and set(item["evidence"]) <= set(records), "liability evidence required")
    if memo["decision"] == "go":
        _require(not any(item["severity"] == "critical" and item["status"] == "open" for item in liabilities),
                 "go decision has an open critical liability", "CRITICAL_LIABILITY")
        _require(genetics["independent_support_count"] >= 1, "go needs at least one independent genetic group", "GENETIC_DEPENDENCE")


def _check_claims(memo, records, claim_register):
    claims = _rows(memo.get("claims"), "memo claims")
    _require(bool(claims), "memo needs explicit claims", "MEMO_OVERCLAIM")
    by_id = {}
    for claim in claims:
        claim = _object(claim, "memo claim")
        identifier = claim.get("id")
        _require(_text(identifier) and identifier not in by_id, "unique claim ID required", "MEMO_OVERCLAIM")
        ids = claim.get("evidence")
        _require(_strings(ids) and bool(ids) and set(ids) <= set(records), "claim needs recorded evidence", "MEMO_OVERCLAIM")
        kind = claim.get("kind")
        _require(kind in ("descriptive", "associational"),
                 "association, numerical agreement or review approval cannot establish causal, physical or clinical validity or truth", "MEMO_OVERCLAIM")
        for ref in ids:
            source, row = records[ref]
            _require(kind == "descriptive" or row["kind"] == "associational",
                     "memo exceeds its cited evidence kind", "MEMO_OVERCLAIM")
        # Literal attribution is deliberately conservative. Semantic paraphrase
        # needs independent source review rather than a guessed entailment score.
        _require(claim.get("text") == "; ".join(records[ref][1]["statement"] for ref in ids),
                 "memo claim is stronger than or differs from its cited statements", "MEMO_OVERCLAIM")
        _require(isinstance(claim.get("status"), str) and claim["status"] in CLAIM_STATUSES,
                 "invalid claim-register status", "MEMO_OVERCLAIM")
        if claim["status"] == "supported":
            _require(all(records[ref][1]["kind"] not in ("review-approval", "computed") for ref in ids),
                     "review approval or computation cannot support a memo claim", "MEMO_OVERCLAIM")
            if kind == "descriptive":
                _require(not re.search(r"\b(?:efficacy|effective|effectiveness|efficacious)\b", claim["text"], re.IGNORECASE),
                         "descriptive evidence cannot support efficacy or effectiveness", "MEMO_OVERCLAIM")
        by_id[identifier] = claim
    _require(claim_register.get("schema_version") == 1, "claim-register schema_version must be 1")
    entries = _rows(claim_register.get("claims"), "claim register")
    _require(len(entries) == len(by_id), "claim register IDs must match memo", "MEMO_OVERCLAIM")
    seen = set()
    for entry in entries:
        entry = _object(entry, "claim-register entry")
        identifier = entry.get("id")
        _require(isinstance(identifier, str) and identifier in by_id and identifier not in seen,
                 "claim register IDs must match memo", "MEMO_OVERCLAIM")
        seen.add(identifier)
        claim = by_id[identifier]
        _require(entry.get("text") == claim["text"] and entry.get("permitted_inference") == claim["kind"]
                 and entry.get("status") == claim["status"], "claim register differs from memo", "MEMO_OVERCLAIM")
        _require(all(_text(entry.get(key)) for key in ("required_support", "falsifier", "uncertainty", "next_action")),
                 "claim-register decision fields required")


def _check_boundaries(dossier, memo):
    _require(memo.get("patient_treatment_recommendation") is False and memo.get("boundary") == PATIENT_BOUNDARY,
             "memo must exclude patient treatment recommendations", "PATIENT_BOUNDARY")
    _require(dossier.get("review_status") == "pending" and memo.get("review_handoff") == "$science-review",
             "pack cannot mark itself independently reviewed", "INDEPENDENT_REVIEW")
    experiment = _object(memo.get("next_experiment"), "next experiment")
    _require(all(_text(experiment.get(key)) for key in ("question", "control", "readout", "falsifier", "decision_rule")),
             "smallest discriminating next experiment needs a control and frozen decision rule")


def _validate_pack(directory):
    bundle = _Bundle(directory)
    dossier = bundle.read({"path": "dossier.json", "sha256": None})
    _require(dossier.get("schema") == "target-assessment-pack-v1", "unsupported dossier schema")
    _require(type(dossier.get("synthetic")) is bool, "synthetic label must be boolean")
    target = _object(dossier.get("target"), "target")
    snapshot = bundle.read(dossier.get("snapshots"))
    _require(snapshot.get("schema") == "target-assessment-snapshots-v1", "unsupported snapshot schema")
    _require(snapshot.get("synthetic") is dossier["synthetic"], "snapshot synthetic label differs")
    sources = {}
    records = {}
    for source in _rows(snapshot.get("sources"), "sources"):
        source = _object(source, "source")
        identifier = source.get("id")
        _require(_text(identifier) and identifier not in sources, "unique source ID required")
        _require(all(_text(source.get(k)) for k in ("skill", "release", "query")), "source provenance required")
        _require(_strings(source.get("cohorts")) and _strings(source.get("dependency_groups")), "source dependency groups required")
        sources[identifier] = source
        for row in _rows(source.get("records"), "source records"):
            row = _object(row, "source record")
            record_id = row.get("id")
            _require(_text(record_id) and record_id not in records and _text(row.get("statement")), "unique record ID and statement required")
            _enum(row.get("kind"), {"descriptive", "associational", "computed", "review-approval"}, "record kind")
            _enum(row.get("result"), {"association", "no-association", "availability", "expression", "safety-signal",
                                      "failed-control", "negative", "numerical-agreement", "review-approval", "identity"}, "record result")
            records[record_id] = (source, row)
    handoffs = _rows(dossier.get("stages"), "stages")
    _require(all(isinstance(s, dict) for s in handoffs) and [s.get("id") for s in handoffs] == list(STAGES),
             "exactly six ordered stage IDs required", "STAGE_ORDER")
    stages = []
    seen_sources = []
    for index, handoff in enumerate(handoffs):
        stage = bundle.read(handoff.get("output"))
        _require(stage.get("schema") == "target-assessment-stage-v1" and stage.get("id") == STAGES[index], "stage schema/ID mismatch")
        _require(stage.get("synthetic") is dossier["synthetic"], "stage synthetic label differs")
        expected_inputs = [dossier["snapshots"]] + ([handoffs[index - 1]["output"]] if index else [])
        _require(stage.get("inputs") == expected_inputs, "stage must bind snapshots and preceding output by path and hash", "STAGE_HANDOFF")
        for ref in expected_inputs:
            bundle.read(ref)
        data = _object(stage.get("data"), "stage data")
        ids = data.get("source_ids")
        _require(_strings(ids) and set(ids) <= set(sources), "invalid stage source IDs")
        _require(sorted(sources[x]["skill"] for x in ids) == sorted(SKILLS[index]), "stage must reuse its declared existing skills")
        seen_sources.extend(ids)
        stages.append(data)
    _require(len(seen_sources) == len(sources) and set(seen_sources) == set(sources), "every snapshot source belongs to one stage")
    checkpoint = bundle.read(dossier.get("checkpoint"))
    try:
        validate_checkpoint(checkpoint)
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        _refuse("PACK_CHECKPOINT", str(error))
    _require([step["id"] for step in checkpoint["steps"]] == list(STAGES), "one checkpoint must cover all ordered stages", "PACK_CHECKPOINT")
    claim_register = bundle.read(dossier.get("claim_register"))
    _check_identity(target, stages[0], list(sources.values()))
    _check_missingness(stages, sources)
    _check_genetics(stages[1], sources, records)
    _check_context(stages[2], sources)
    _check_availability(stages[3])
    _check_potency(stages[3], records)
    _check_direction(stages[1], stages[5], records)
    _check_go(stages[1], stages[4], stages[5], records)
    _check_claims(stages[5], records, claim_register)
    _check_boundaries(dossier, stages[5])
    bundle.unchanged()
    return {"status": "passed", "synthetic": dossier["synthetic"], "stage_count": 6,
            "review_status": "pending", "decision": stages[5]["decision"],
            "boundary": "Internal record consistency only; no scientific or clinical validity established."}


def validate_target_assessment_pack(directory):
    """Validate an offline directory, returning pending-review status or labelled ValueError."""
    try:
        return _validate_pack(directory)
    except (OSError, RuntimeError, UnicodeError, RecursionError) as error:
        _refuse("PACK_INPUT", f"cannot read bundle: {error}")
