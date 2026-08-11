"""Safe local resource access and canonical question recovery."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    QuestionImageModel,
    QuestionModel,
    QuestionOptionModel,
    QuestionResourceModel,
    QuestionSourceModel,
)
from app.modules.paper_agent.schemas.question import Question, QuestionImage, QuestionOption
from app.modules.paper_agent.schemas.source import QuestionSource


class StoredResourceNotFoundError(LookupError):
    pass


class StoredResourceIntegrityError(ValueError):
    pass


class UnsafeStoredResourceError(ValueError):
    pass


class QuestionNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class StoredResourceFile:
    resource: QuestionResourceModel
    source: QuestionSourceModel
    path: Path


def source_schema(source: QuestionSourceModel) -> QuestionSource:
    return QuestionSource(
        source_id=source.source_id,
        source_type=source.source_type,
        name=source.name,
        uri=source.uri,
        external_id=source.external_id,
        retrieved_at=source.retrieved_at,
        attribution=source.attribution,
        license=source.license,
    )


def _safe_local_path(storage_root: Path, uri: str) -> Path:
    root = storage_root.resolve()
    path = Path(uri).resolve()
    if not path.is_relative_to(root):
        raise UnsafeStoredResourceError("resource path is outside paper-agent storage")
    if not path.is_file():
        raise StoredResourceNotFoundError("resource file is missing")
    return path


def _verify_digest(path: Path, expected: str | None) -> None:
    if expected is None:
        return
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected:
        raise StoredResourceIntegrityError("resource checksum verification failed")


async def get_stored_resource_file(
    session: AsyncSession,
    resource_id: str,
    *,
    storage_root: Path,
) -> StoredResourceFile:
    resource = await session.get(QuestionResourceModel, resource_id)
    if resource is None:
        raise StoredResourceNotFoundError("resource was not found")
    source = await session.get(QuestionSourceModel, resource.source_id)
    if source is None:
        raise StoredResourceIntegrityError("resource source record is missing")
    path = await asyncio.to_thread(_safe_local_path, storage_root, resource.uri)
    await asyncio.to_thread(_verify_digest, path, resource.sha256)
    return StoredResourceFile(resource=resource, source=source, path=path)


async def _load_image(
    session: AsyncSession,
    image: QuestionImageModel,
) -> QuestionImage:
    resource = await session.get(QuestionResourceModel, image.resource_id)
    if resource is None or resource.resource_type != "image":
        raise StoredResourceIntegrityError("question image resource is missing or invalid")
    source = await session.get(QuestionSourceModel, resource.source_id)
    if source is None:
        raise StoredResourceIntegrityError("question image source is missing")
    return QuestionImage(
        resource_id=resource.resource_id,
        uri=resource.uri,
        source=source_schema(source),
        mime_type=resource.mime_type,
        sha256=resource.sha256,
        alt_text=image.alt_text,
        caption=image.caption,
    )


async def recover_question(
    session: AsyncSession,
    question_id: str,
) -> Question:
    model = await session.get(QuestionModel, question_id)
    if model is None:
        raise QuestionNotFoundError("question was not found")
    source = await session.get(QuestionSourceModel, model.source_id)
    if source is None:
        raise StoredResourceIntegrityError("question source is missing")

    question_images = list(
        await session.scalars(
            select(QuestionImageModel)
            .where(QuestionImageModel.question_id == model.id)
            .order_by(QuestionImageModel.position, QuestionImageModel.id)
        )
    )
    options: list[QuestionOption] = []
    option_models = list(
        await session.scalars(
            select(QuestionOptionModel)
            .where(QuestionOptionModel.question_id == model.id)
            .order_by(QuestionOptionModel.position, QuestionOptionModel.id)
        )
    )
    for option in option_models:
        option_images = list(
            await session.scalars(
                select(QuestionImageModel)
                .where(QuestionImageModel.option_id == option.id)
                .order_by(QuestionImageModel.position, QuestionImageModel.id)
            )
        )
        options.append(
            QuestionOption(
                label=option.label,
                content=option.content,
                images=[
                    await _load_image(session, image) for image in option_images
                ],
            )
        )

    children = list(
        await session.scalars(
            select(QuestionModel.id)
            .where(QuestionModel.parent_question_id == model.id)
            .order_by(QuestionModel.position, QuestionModel.id)
        )
    )
    return Question(
        id=model.id,
        question_type=model.question_type,
        difficulty=model.difficulty,
        stem=model.stem,
        source=source_schema(source),
        options=options,
        subquestions=[await recover_question(session, child_id) for child_id in children],
        answer=model.answer,
        explanation=model.explanation,
        images=[await _load_image(session, image) for image in question_images],
    )


async def image_schema_for_resource(
    session: AsyncSession,
    resource_id: str,
) -> QuestionImage:
    resource = await session.get(QuestionResourceModel, resource_id)
    if resource is None:
        raise StoredResourceNotFoundError(f"image resource was not found: {resource_id}")
    if resource.resource_type != "image":
        raise StoredResourceIntegrityError(f"resource is not an image: {resource_id}")
    source = await session.get(QuestionSourceModel, resource.source_id)
    if source is None:
        raise StoredResourceIntegrityError("image source record is missing")
    return QuestionImage(
        resource_id=resource.resource_id,
        uri=resource.uri,
        source=source_schema(source),
        mime_type=resource.mime_type,
        sha256=resource.sha256,
    )
