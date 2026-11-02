"""Deterministic planning primitives for agentic life-science research."""

from __future__ import annotations

import re
from typing import Any


# Nuclear positions need at least three digits so clock times such as 10:30-A-C are not
# variants; 100 keeps short connector fixtures such as 1:100-A-G while staying inside the
# unassembled first 10 kb of GRCh37/GRCh38 nuclear chromosomes. Mitochondrial positions start at 1.
VARIANT_RE = re.compile(
    r"\brs\d+\b"
    r"|\b(?:chr)?(?:(?:1[0-9]|2[0-2]|[1-9]|X|Y)[:-][1-9]\d{2,}|MT?[:-][1-9]\d*)[:-][ACGT]+[:-][ACGT]+\b",
    re.I,
)
ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
NON_RESEARCH_PHRASES_RE = re.compile(r"\bpublic domain\b")
MAX_LANES = 4

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


def _has_term(text: str, term: str) -> bool:
    """Hangul terms match inside words; ASCII terms match whole words with an optional plural."""
    if not term.isascii():
        return term in text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?:e?s)?(?![a-z0-9])", text) is not None


def plan_life_science_research(question: str) -> dict[str, Any]:
    if not isinstance(question, str):
        raise ValueError("Question must be a string of 1 to 500 characters")
    question = question.strip()
    if not ZERO_WIDTH_RE.sub("", question).strip() or len(question) > 500:
        raise ValueError("Question must contain 1 to 500 characters")
    lowered = NON_RESEARCH_PHRASES_RE.sub(" ", question.lower())
    ranked: list[tuple[int, str]] = []
    for lane, terms in LANES:
        score = sum(_has_term(lowered, term) for term in terms)
        if score:
            ranked.append((score, lane))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    forced: set[str] = set()
    if VARIANT_RE.search(question):
        forced.add("human_genetics")
    if _has_term(lowered, "across") and _has_term(lowered, "cohort"):
        forced.add("phewas_replication")
    # Forced lanes keep their ranked position when already selected; otherwise they
    # displace the lowest-ranked keyword lanes so the cap never drops them.
    kept = [lane for _, lane in ranked[:MAX_LANES]] or ["literature_evidence"]
    missing = [lane for lane in ("human_genetics", "phewas_replication") if lane in forced and lane not in kept]
    while len(kept) + len(missing) > MAX_LANES:
        kept.pop(max(index for index, lane in enumerate(kept) if lane not in forced))
    front = ["human_genetics"] if "human_genetics" in missing else []
    back = ["phewas_replication"] if "phewas_replication" in missing else []
    lanes = [*front, *kept, *back]
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
