"""Queries and processing-state transitions for teacher resources."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuestionModel, QuestionResourceModel, QuestionSourceModel
from app.modules.paper_agent.schemas.library import (
    QuestionLibraryItem,
    QuestionLibraryResponse,
    SourceLibraryItem,
    SourceLibraryResponse,
    SourceProcessingStatus,
)
from app.modules.paper_agent.schemas.parsing import ParsedQuestionsResponse, QuestionParseRequest
from app.modules.paper_agent.schemas.question import QuestionDifficulty, QuestionType
from app.modules.paper_agent.schemas.source import ResourceType, SourceType
from app.modules.paper_agent.services.question_ingestion import parse_uploaded_questions
from app.modules.paper_agent.services.resource_storage import StoredResourceNotFoundError


def _source_locator(source: QuestionSourceModel) -> str | None:
    if source.source_type == SourceType.WEBSITE.value:
        return source.uri
    return source.external_id or source.name


def _choose_primary_resource(
    resources: list[QuestionResourceModel],
) -> QuestionResourceModel | None:
    priority = {ResourceType.DOCUMENT.value: 0, ResourceType.WEBPAGE.value: 0}
    return min(
        resources,
        key=lambda item: (priority.get(item.resource_type, 1), item.resource_id),
        default=None,
    )


async def list_sources(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
    source_type: SourceType | None = None,
) -> SourceLibraryResponse:
    filters = []
    if keyword:
        pattern = f"%{keyword.strip()}%"
        filters.append(
            or_(
                QuestionSourceModel.name.ilike(pattern),
                QuestionSourceModel.external_id.ilike(pattern),
                QuestionSourceModel.attribution.ilike(pattern),
            )
        )
    if source_type is not None:
        filters.append(QuestionSourceModel.source_type == source_type.value)

    total = int(
        await session.scalar(
            select(func.count()).select_from(QuestionSourceModel).where(*filters)
        )
        or 0
    )
    sources = list(
        (
            await session.scalars(
                select(QuestionSourceModel)
                .where(*filters)
                .order_by(
                    QuestionSourceModel.retrieved_at.desc(),
                    QuestionSourceModel.source_id,
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    source_ids = [source.source_id for source in sources]
    resources_by_source: dict[str, list[QuestionResourceModel]] = {
        source_id: [] for source_id in source_ids
    }
    question_counts: dict[str, int] = {}
    if source_ids:
        resources = (
            await session.scalars(
                select(QuestionResourceModel).where(
                    QuestionResourceModel.source_id.in_(source_ids)
                )
            )
        ).all()
        for resource in resources:
            resources_by_source[resource.source_id].append(resource)
        count_rows = await session.execute(
            select(QuestionModel.source_id, func.count(QuestionModel.id))
            .where(
                QuestionModel.source_id.in_(source_ids),
                QuestionModel.parent_question_id.is_(None),
            )
            .group_by(QuestionModel.source_id)
        )
        question_counts = {source_id: int(count) for source_id, count in count_rows}

    items = []
    for source in sources:
        resource = _choose_primary_resource(resources_by_source[source.source_id])
        items.append(
            SourceLibraryItem(
                source_id=source.source_id,
                resource_id=resource.resource_id if resource else None,
                name=source.name,
                source_type=SourceType(source.source_type),
                resource_type=(
                    ResourceType(resource.resource_type) if resource else None
                ),
                mime_type=resource.mime_type if resource else None,
                locator=_source_locator(source),
                attribution=source.attribution,
                retrieved_at=source.retrieved_at,
                processing_status=SourceProcessingStatus(source.processing_status),
                failure_reason=source.parse_failure_reason,
                processed_at=source.processed_at,
                question_count=question_counts.get(source.source_id, 0),
                can_parse=(
                    resource is not None
                    and resource.resource_type
                    in {ResourceType.DOCUMENT.value, ResourceType.WEBPAGE.value}
                ),
            )
        )

    return SourceLibraryResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def list_library_questions(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    keyword: str | None = None,
    question_type: QuestionType | None = None,
    source_id: str | None = None,
) -> QuestionLibraryResponse:
    filters = [QuestionModel.parent_question_id.is_(None)]
    if keyword:
        pattern = f"%{keyword.strip()}%"
        filters.append(
            or_(
                QuestionModel.stem.ilike(pattern),
                QuestionSourceModel.name.ilike(pattern),
            )
        )
    if question_type is not None:
        filters.append(QuestionModel.question_type == question_type.value)
    if source_id:
        filters.append(QuestionModel.source_id == source_id)

    joined = select(QuestionModel).join(
        QuestionSourceModel,
        QuestionSourceModel.source_id == QuestionModel.source_id,
    )
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(QuestionModel)
            .join(
                QuestionSourceModel,
                QuestionSourceModel.source_id == QuestionModel.source_id,
            )
            .where(*filters)
        )
        or 0
    )
    questions = list(
        (
            await session.scalars(
                joined.where(*filters)
                .order_by(QuestionModel.created_at.desc(), QuestionModel.id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    source_ids = {question.source_id for question in questions}
    sources = {
        source.source_id: source
        for source in (
            await session.scalars(
                select(QuestionSourceModel).where(
                    QuestionSourceModel.source_id.in_(source_ids)
                )
            )
        ).all()
    } if source_ids else {}

    items = []
    for question in questions:
        source = sources[question.source_id]
        items.append(
            QuestionLibraryItem(
                question_id=question.id,
                question_type=QuestionType(question.question_type),
                difficulty=QuestionDifficulty(question.difficulty),
                stem=question.stem,
                has_answer=question.answer is not None,
                created_at=question.created_at,
                source_id=source.source_id,
                source_name=source.name,
                source_type=SourceType(source.source_type),
                source_locator=_source_locator(source),
                attribution=source.attribution,
            )
        )
    return QuestionLibraryResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if total else 0,
    )


async def _set_processing_status(
    session: AsyncSession,
    resource_id: str,
    processing_status: SourceProcessingStatus,
    *,
    failure_reason: str | None = None,
) -> None:
    source = await session.scalar(
        select(QuestionSourceModel)
        .join(
            QuestionResourceModel,
            QuestionResourceModel.source_id == QuestionSourceModel.source_id,
        )
        .where(QuestionResourceModel.resource_id == resource_id)
    )
    if source is None:
        raise StoredResourceNotFoundError("resource was not found")
    source.processing_status = processing_status.value
    source.parse_failure_reason = (
        failure_reason[:2000] if processing_status == SourceProcessingStatus.FAILED and failure_reason
        else None
    )
    source.processed_at = (
        datetime.now(timezone.utc)
        if processing_status in {SourceProcessingStatus.COMPLETED, SourceProcessingStatus.FAILED}
        else None
    )
    await session.commit()


async def parse_questions_with_status(
    session: AsyncSession,
    source_resource_id: str,
    payload: QuestionParseRequest,
    *,
    storage_root: Path,
    max_asset_bytes: int,
) -> ParsedQuestionsResponse:
    await _set_processing_status(
        session,
        source_resource_id,
        SourceProcessingStatus.PROCESSING,
    )
    try:
        result = await parse_uploaded_questions(
            session,
            source_resource_id,
            payload,
            storage_root=storage_root,
            max_asset_bytes=max_asset_bytes,
        )
    except Exception as exc:
        await session.rollback()
        await _set_processing_status(
            session,
            source_resource_id,
            SourceProcessingStatus.FAILED,
            failure_reason=str(exc) or exc.__class__.__name__,
        )
        raise
    await _set_processing_status(
        session,
        source_resource_id,
        SourceProcessingStatus.COMPLETED,
    )
    return result
