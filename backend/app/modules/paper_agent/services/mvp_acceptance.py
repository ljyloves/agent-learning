"""Repeatable BIO-036 MVP acceptance blueprint and data preparation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    QuestionAnalysisModel,
    QuestionCoreCompetencyModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionSourceModel,
)


BIO036_SOURCE_EXTERNAL_ID = "BIO-016"
BIO036_ANALYSIS_MODEL = "bio036-deterministic-acceptance-v1"
BIO036_REVIEWER = "bio036-acceptance-teacher"
BIO036_KNOWLEDGE_POINTS = tuple(f"BIO-M1-K0{index}" for index in range(1, 8))
BIO036_LEVEL_COUNTS = {2: 4, 3: 4, 4: 2}
BIO036_DIFFICULTY_NAMES = {2: "easy", 3: "medium", 4: "hard"}
BIO036_NAMESPACE = uuid.UUID("fca230ea-75fc-4c13-a20b-f760bcf20638")


@dataclass(frozen=True, slots=True)
class Bio036CandidateSet:
    question_ids: tuple[str, ...]
    excluded_question_ids: tuple[str, ...]
    core_competency_count: int


def _analysis_id(question_id: str, analysis_type: str) -> str:
    return str(uuid.uuid5(BIO036_NAMESPACE, f"{question_id}:{analysis_type}"))


def _selection_plan() -> tuple[tuple[str, str], ...]:
    return (
        ("BIO-M1-K01", "easy"),
        ("BIO-M1-K02", "easy"),
        ("BIO-M1-K03", "easy"),
        ("BIO-M1-K04", "easy"),
        ("BIO-M1-K05", "medium"),
        ("BIO-M1-K06", "medium"),
        ("BIO-M1-K07", "medium"),
        ("BIO-M1-K01", "medium"),
        ("BIO-M1-K02", "hard"),
        ("BIO-M1-K03", "hard"),
    )


async def _upsert_analysis(
    session: AsyncSession,
    *,
    question_id: str,
    analysis_type: str,
    result: dict,
    created_at: datetime,
) -> None:
    analysis_id = _analysis_id(question_id, analysis_type)
    analysis = await session.get(QuestionAnalysisModel, analysis_id)
    if analysis is None:
        session.add(
            QuestionAnalysisModel(
                analysis_id=analysis_id,
                question_id=question_id,
                analysis_type=analysis_type,
                model=BIO036_ANALYSIS_MODEL,
                result=result,
                created_at=created_at,
            )
        )
        return
    analysis.question_id = question_id
    analysis.analysis_type = analysis_type
    analysis.model = BIO036_ANALYSIS_MODEL
    analysis.result = result
    analysis.created_at = created_at


async def prepare_bio036_candidates(
    session: AsyncSession,
) -> Bio036CandidateSet:
    """Select ten stable seed questions and add auditable acceptance analyses."""

    rows = (
        await session.execute(
            select(
                QuestionModel.id,
                QuestionModel.difficulty,
                QuestionKnowledgePointModel.knowledge_point_code,
            )
            .join(
                QuestionSourceModel,
                QuestionSourceModel.source_id == QuestionModel.source_id,
            )
            .join(
                QuestionKnowledgePointModel,
                QuestionKnowledgePointModel.question_id == QuestionModel.id,
            )
            .where(
                QuestionSourceModel.external_id == BIO036_SOURCE_EXTERNAL_ID,
                QuestionModel.parent_question_id.is_(None),
                QuestionModel.question_type == "single_choice",
                QuestionModel.answer.is_not(None),
                QuestionModel.explanation.is_not(None),
            )
            .order_by(QuestionModel.id)
        )
    ).all()
    by_slot: dict[tuple[str, str], list[str]] = {}
    for question_id, difficulty, knowledge_point in rows:
        by_slot.setdefault((knowledge_point, difficulty), []).append(question_id)

    selected: list[str] = []
    levels: dict[str, int] = {}
    reverse_difficulty = {name: level for level, name in BIO036_DIFFICULTY_NAMES.items()}
    for slot in _selection_plan():
        available = [item for item in by_slot.get(slot, ()) if item not in selected]
        if not available:
            raise RuntimeError(f"BIO-036 candidate slot is unavailable: {slot}")
        question_id = available[0]
        selected.append(question_id)
        levels[question_id] = reverse_difficulty[slot[1]]

    actual_counts = {
        level: sum(value == level for value in levels.values())
        for level in BIO036_LEVEL_COUNTS
    }
    if actual_counts != BIO036_LEVEL_COUNTS:
        raise RuntimeError(f"BIO-036 difficulty blueprint mismatch: {actual_counts}")

    competencies = set(
        await session.scalars(
            select(QuestionCoreCompetencyModel.competency_code).where(
                QuestionCoreCompetencyModel.question_id.in_(selected)
            )
        )
    )
    if len(competencies) < 2:
        raise RuntimeError("BIO-036 candidates do not cover two core competencies")

    now = datetime.now(timezone.utc)
    correct_rates = {2: 0.75, 3: 0.55, 4: 0.30}
    for question_id in selected:
        level = levels[question_id]
        await _upsert_analysis(
            session,
            question_id=question_id,
            analysis_type="difficulty_estimation",
            result={
                "difficulty_level": level,
                "estimated_correct_rate": correct_rates[level],
                "confidence": 1.0,
                "rationale": (
                    "BIO-036 deterministic acceptance mapping from the seeded "
                    "easy, medium, or hard difficulty; this is not LLM output."
                ),
            },
            created_at=now,
        )
        await _upsert_analysis(
            session,
            question_id=question_id,
            analysis_type="quality_review",
            result={
                "issues": [],
                "summary": (
                    "BIO-036 deterministic acceptance check passed for this "
                    "traceable BIO-016 seed question."
                ),
                "passed": True,
            },
            created_at=now,
        )

    all_question_ids = set(await session.scalars(select(QuestionModel.id)))
    excluded = tuple(sorted(all_question_ids - set(selected)))
    if len(excluded) > 1000:
        raise RuntimeError("BIO-036 exclusion list exceeds API contract limit")
    await session.commit()
    return Bio036CandidateSet(
        question_ids=tuple(selected),
        excluded_question_ids=excluded,
        core_competency_count=len(competencies),
    )


def bio036_optimization_payload(candidates: Bio036CandidateSet) -> dict:
    return {
        "optimization": {
            "module_code": "BIO-M1",
            "question_count": 10,
            "total_score": 50,
            "difficulty_quotas": [
                {
                    "question_type": "single_choice",
                    "difficulty_level": level,
                    "count": count,
                    "score_per_question": 5,
                }
                for level, count in BIO036_LEVEL_COUNTS.items()
            ],
            "coverage": {
                "targets": [
                    {"code": code, "minimum_count": 1}
                    for code in BIO036_KNOWLEDGE_POINTS
                ],
                "minimum_coverage_rate": 1.0,
            },
            "diversity": {
                "minimum_distinct_knowledge_points": 7,
                "minimum_distinct_core_competencies": 2,
                "minimum_distinct_sources": 1,
                "maximum_questions_per_knowledge_point": 3,
                "maximum_questions_per_source": 10,
                "semantic_similarity_threshold": 1.0,
            },
            "exclude_question_ids": list(candidates.excluded_question_ids),
            "random_seed": 36,
        }
    }


def optimized_paper_to_assembly(paper: dict) -> dict:
    sections = []
    for section in paper["sections"]:
        level = section["difficulty_level"]
        sections.append(
            {
                "section_index": section["section_index"],
                "question_type": section["question_type"],
                "difficulty": BIO036_DIFFICULTY_NAMES[level],
                "count": section["count"],
                "score_per_question": section["score_per_question"],
                "questions": [
                    {
                        "question_id": question["question_id"],
                        "question_type": question["question_type"],
                        "difficulty": BIO036_DIFFICULTY_NAMES[
                            question["difficulty_level"]
                        ],
                        "score": question["score"],
                    }
                    for question in section["questions"]
                ],
            }
        )
    return {
        "module_code": paper["module_code"],
        "question_count": paper["question_count"],
        "total_score": paper["total_score"],
        "sections": sections,
    }


__all__ = [
    "BIO036_ANALYSIS_MODEL",
    "BIO036_KNOWLEDGE_POINTS",
    "BIO036_LEVEL_COUNTS",
    "BIO036_REVIEWER",
    "Bio036CandidateSet",
    "bio036_optimization_payload",
    "optimized_paper_to_assembly",
    "prepare_bio036_candidates",
]
