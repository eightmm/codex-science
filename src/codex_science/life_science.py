"""Deterministic planning primitives for agentic life-science research."""

from __future__ import annotations

import re
from typing import Any


VARIANT_RE = re.compile(r"\brs\d+\b|\b(?:chr)?[0-9XYM]+:\d+[-:][ACGT]+[-:][ACGT]+\b", re.I)

LANES = (
    (
        "human_genetics",
        (
            "variant", "gwas", "genetic", "locus", "heritability", "ancestry", "cohort",
            "변이", "유전", "유전체", "좌위", "조상", "코호트",
        ),
    ),
    (
        "phewas_replication",
        (
            "phewas", "across cohorts", "across ancestries", "replication", "finngen", "biobank", "topmed",
            "표현형", "재현", "핀젠", "바이오뱅크", "인구집단",
        ),
    ),
    (
        "expression_cell_context",
        (
            "expression", "tissue", "cell", "single-cell", "microglia", "eqtl",
            "발현", "조직", "세포", "단일세포", "미세아교",
        ),
    ),
    (
        "structure_mechanism",
        (
            "structure", "protein", "mechanism", "domain", "alphafold", "pdb",
            "구조", "단백질", "기전", "도메인",
        ),
    ),
    (
        "chemistry_pharmacology",
        (
            "ligand", "compound", "drug", "chemistry", "pharmacology", "metabolite",
            "리간드", "화합물", "약물", "화학", "약리", "대사체",
        ),
    ),
    (
        "clinical_translational",
        (
            "clinical", "trial", "patient", "cancer", "therapy", "translational",
            "임상", "환자", "종양", "암종", "치료", "중개",
        ),
    ),
    (
        "public_dataset_discovery",
        (
            "dataset", "study", "archive", "proteomics", "metabolomics", "microbiome",
            "데이터셋", "아카이브", "단백질체", "대사체", "마이크로바이옴",
        ),
    ),
)


def plan_life_science_research(question: str) -> dict[str, Any]:
    question = question.strip()
    if not question or len(question) > 500:
        raise ValueError("Question must contain 1 to 500 characters")
    lowered = question.lower()
    ranked: list[tuple[int, str]] = []
    for lane, terms in LANES:
        score = sum(term in lowered for term in terms)
        if score:
            ranked.append((score, lane))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    lanes = [lane for _, lane in ranked[:4]] or ["literature_evidence"]
    if VARIANT_RE.search(question) and "human_genetics" not in lanes:
        lanes.insert(0, "human_genetics")
    if "across" in lowered and "cohort" in lowered and "phewas_replication" not in lanes:
        lanes.append("phewas_replication")
    lanes = lanes[:4]
    entities = []
    for match in VARIANT_RE.finditer(question):
        entities.append({"kind": "variant", "value": match.group(0), "normalization": "assembly-and-allele-required"})
    if not entities:
        entities.append({"kind": "unresolved", "value": question, "normalization": "resolve-before-retrieval"})
    return {
        "question": question,
        "entities": entities,
        "lanes": lanes,
        "execution_order": ["normalize-first", "retrieve-independent-lanes", "reconcile", "review"],
        "parallelizable": len(lanes) > 1,
        "record_fields": ["source", "source_release", "query", "retrieved_at", "entity_ids", "artifact_hash"],
        "synthesis_sections": ["working_conclusion", "evidence_by_lane", "conflicts", "limitations", "next_tests"],
        "required_caveats": [
            "association is not causality",
            "report assembly, ancestry, tissue, assay, cohort, and release",
            "distinguish missing evidence from negative evidence",
        ],
    }
