"""Deterministic strict-constraint paper assembly service."""

from __future__ import annotations

import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgePointModel,
    QuestionKnowledgePointModel,
    QuestionModel,
)
from app.modules.paper_agent.schemas.assembly import (
    AssembledQuestion,
    AssembledSection,
    PaperAssemblyRequest,
    PaperAssemblyResult,
    PaperSectionConstraint,
)


class InsufficientQuestionBankError(ValueError):
    def __init__(
        self,
        section: PaperSectionConstraint,
        *,
        required: int,
        available: int,
    ) -> None:
        self.section = section
        self.required = required
        self.available = available
        super().__init__(
            "insufficient questions for "
            f"{section.question_type.value}/{section.difficulty.value}: "
            f"required {required}, available {available}"
        )


async def _candidate_question_ids(
    session: AsyncSession,
    request: PaperAssemblyRequest,
    section: PaperSectionConstraint,
    excluded_ids: set[str],
) -> list[str]:
    statement = (
        select(QuestionModel.id)
        .join(
            QuestionKnowledgePointModel,
            QuestionKnowledgePointModel.question_id == QuestionModel.id,
        )
        .join(
            KnowledgePointModel,
            KnowledgePointModel.code
            == QuestionKnowledgePointModel.knowledge_point_code,
        )
        .where(
            KnowledgePointModel.module_code == request.module_code,
            QuestionModel.question_type == section.question_type.value,
            QuestionModel.difficulty == section.difficulty.value,
        )
        .distinct()
        .order_by(QuestionModel.id)
    )
    if excluded_ids:
        statement = statement.where(QuestionModel.id.not_in(excluded_ids))
    return list(await session.scalars(statement))


async def assemble_paper(
    session: AsyncSession,
    request: PaperAssemblyRequest,
) -> PaperAssemblyResult:
    selected_ids = set(request.exclude_question_ids)
    assembled_sections: list[AssembledSection] = []

    for section_index, section in enumerate(request.sections):
        candidate_ids = await _candidate_question_ids(
            session,
            request,
            section,
            selected_ids,
        )
        if len(candidate_ids) < section.count:
            raise InsufficientQuestionBankError(
                section,
                required=section.count,
                available=len(candidate_ids),
            )

        randomizer = random.Random(
            f"{request.random_seed}:{section_index}:"
            f"{section.question_type.value}:{section.difficulty.value}"
        )
        randomizer.shuffle(candidate_ids)
        chosen_ids = candidate_ids[: section.count]
        selected_ids.update(chosen_ids)
        assembled_sections.append(
            AssembledSection(
                section_index=section_index,
                question_type=section.question_type,
                difficulty=section.difficulty,
                count=section.count,
                score_per_question=section.score_per_question,
                questions=[
                    AssembledQuestion(
                        question_id=question_id,
                        question_type=section.question_type,
                        difficulty=section.difficulty,
                        score=section.score_per_question,
                    )
                    for question_id in chosen_ids
                ],
            )
        )

    return PaperAssemblyResult(
        module_code=request.module_code,
        question_count=request.question_count,
        total_score=request.total_score,
        sections=assembled_sections,
    )


async def candidate_question_ids_for_request(
    session: AsyncSession,
    request: PaperAssemblyRequest,
) -> list[str]:
    """Return every question eligible for at least one blueprint section."""

    excluded_ids = set(request.exclude_question_ids)
    candidate_ids: set[str] = set()
    for section in request.sections:
        candidate_ids.update(
            await _candidate_question_ids(
                session,
                request,
                section,
                excluded_ids,
            )
        )
    return sorted(candidate_ids)
