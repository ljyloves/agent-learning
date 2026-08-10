"""Transactional persistence for Paper Agent jobs and questions."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CoreCompetencyModel,
    KnowledgePointModel,
    PaperJobModel,
    PaperJobQuestionModel,
    QuestionCoreCompetencyModel,
    QuestionImageModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionOptionModel,
    QuestionResourceModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.schemas.question import (
    Question,
    QuestionImage,
)
from app.modules.paper_agent.schemas.source import QuestionSource
from app.modules.paper_agent.schemas.taxonomy import (
    PaperJobQuestionCreate,
    PaperJobQuestionCreated,
)


class PersistenceConflictError(ValueError):
    pass


class UnknownTaxonomyCodeError(ValueError):
    pass


def new_id() -> str:
    return str(uuid.uuid4())


class QuestionPersistenceContext:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.source_ids: set[str] = set()
        self.resource_ids: set[str] = set()
        self.question_ids: set[str] = set()

    async def ensure_source(self, source: QuestionSource) -> None:
        if source.source_id in self.source_ids:
            return

        existing = await self.session.get(QuestionSourceModel, source.source_id)
        if existing is None:
            self.session.add(
                QuestionSourceModel(
                    source_id=source.source_id,
                    source_type=source.source_type.value,
                    name=source.name,
                    uri=source.uri,
                    external_id=source.external_id,
                    retrieved_at=source.retrieved_at,
                    attribution=source.attribution,
                    license=source.license,
                )
            )
            await self.session.flush()
        self.source_ids.add(source.source_id)

    async def save_image(
        self,
        image: QuestionImage,
        *,
        question_id: str | None,
        option_id: str | None,
        position: int,
    ) -> None:
        await self.ensure_source(image.source)
        if image.resource_id in self.resource_ids:
            raise PersistenceConflictError(
                f"duplicate resource_id in request: {image.resource_id}"
            )
        if await self.session.get(QuestionResourceModel, image.resource_id):
            raise PersistenceConflictError(
                f"resource already exists: {image.resource_id}"
            )

        self.session.add(
            QuestionResourceModel(
                resource_id=image.resource_id,
                resource_type=image.resource_type.value,
                uri=image.uri,
                source_id=image.source.source_id,
                mime_type=image.mime_type,
                sha256=image.sha256,
            )
        )
        await self.session.flush()
        self.session.add(
            QuestionImageModel(
                id=new_id(),
                resource_id=image.resource_id,
                question_id=question_id,
                option_id=option_id,
                alt_text=image.alt_text,
                caption=image.caption,
                position=position,
            )
        )
        self.resource_ids.add(image.resource_id)

    async def save_question(
        self,
        question: Question,
        *,
        parent_question_id: str | None = None,
        position: int = 0,
    ) -> str:
        question_id = question.id or new_id()
        if question_id in self.question_ids:
            raise PersistenceConflictError(
                f"duplicate question id in request: {question_id}"
            )
        if await self.session.get(QuestionModel, question_id):
            raise PersistenceConflictError(
                f"question already exists: {question_id}"
            )

        await self.ensure_source(question.source)
        self.session.add(
            QuestionModel(
                id=question_id,
                parent_question_id=parent_question_id,
                source_id=question.source.source_id,
                question_type=question.question_type.value,
                stem=question.stem,
                answer=question.answer,
                explanation=question.explanation,
                position=position,
            )
        )
        await self.session.flush()
        self.question_ids.add(question_id)

        for image_position, image in enumerate(question.images):
            await self.save_image(
                image,
                question_id=question_id,
                option_id=None,
                position=image_position,
            )

        for option_position, option in enumerate(question.options):
            option_id = new_id()
            self.session.add(
                QuestionOptionModel(
                    id=option_id,
                    question_id=question_id,
                    label=option.label,
                    content=option.content,
                    position=option_position,
                )
            )
            await self.session.flush()
            for image_position, image in enumerate(option.images):
                await self.save_image(
                    image,
                    question_id=None,
                    option_id=option_id,
                    position=image_position,
                )

        for child_position, child in enumerate(question.subquestions):
            await self.save_question(
                child,
                parent_question_id=question_id,
                position=child_position,
            )

        return question_id


async def require_taxonomy_codes(
    session: AsyncSession,
    knowledge_point_codes: list[str],
    competency_codes: list[str],
) -> None:
    known_points = set(
        await session.scalars(
            select(KnowledgePointModel.code).where(
                KnowledgePointModel.code.in_(knowledge_point_codes),
                KnowledgePointModel.is_active.is_(True),
            )
        )
    )
    known_competencies = set(
        await session.scalars(
            select(CoreCompetencyModel.code).where(
                CoreCompetencyModel.code.in_(competency_codes),
                CoreCompetencyModel.is_active.is_(True),
            )
        )
    )

    missing_points = sorted(set(knowledge_point_codes) - known_points)
    missing_competencies = sorted(set(competency_codes) - known_competencies)
    if missing_points or missing_competencies:
        details = []
        if missing_points:
            details.append(f"unknown knowledge points: {', '.join(missing_points)}")
        if missing_competencies:
            details.append(
                f"unknown core competencies: {', '.join(missing_competencies)}"
            )
        raise UnknownTaxonomyCodeError("; ".join(details))


async def create_job_with_question(
    session: AsyncSession,
    payload: PaperJobQuestionCreate,
) -> PaperJobQuestionCreated:
    if await session.get(PaperJobModel, payload.job.job_id):
        raise PersistenceConflictError(
            f"paper job already exists: {payload.job.job_id}"
        )

    await require_taxonomy_codes(
        session,
        payload.knowledge_point_codes,
        payload.core_competency_codes,
    )

    review_result = (
        payload.job.review_result.model_dump(mode="json")
        if payload.job.review_result is not None
        else None
    )
    session.add(
        PaperJobModel(
            job_id=payload.job.job_id,
            status=payload.job.status.value,
            failure_reason=payload.job.failure_reason,
            review_status=payload.job.review_status.value,
            review_result=review_result,
            created_at=payload.job.created_at,
            updated_at=payload.job.updated_at,
        )
    )
    await session.flush()

    context = QuestionPersistenceContext(session)
    question_id = await context.save_question(payload.question)
    session.add(
        PaperJobQuestionModel(
            job_id=payload.job.job_id,
            question_id=question_id,
            position=0,
        )
    )
    session.add_all(
        [
            QuestionKnowledgePointModel(
                question_id=question_id,
                knowledge_point_code=code,
            )
            for code in payload.knowledge_point_codes
        ]
    )
    session.add_all(
        [
            QuestionCoreCompetencyModel(
                question_id=question_id,
                competency_code=code,
            )
            for code in payload.core_competency_codes
        ]
    )
    await session.flush()

    return PaperJobQuestionCreated(
        job_id=payload.job.job_id,
        question_id=question_id,
        job_status=payload.job.status.value,
        knowledge_point_codes=payload.knowledge_point_codes,
        core_competency_codes=payload.core_competency_codes,
    )
