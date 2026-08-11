"""Parse an uploaded document, archive its assets, and persist questions."""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QuestionKnowledgePointModel

from app.modules.paper_agent.schemas.parsing import ParsedQuestionsResponse
from app.modules.paper_agent.schemas.question import Question, QuestionImage
from app.modules.paper_agent.schemas.parsing import QuestionParseRequest
from app.modules.paper_agent.services.document_extraction import (
    DocumentExtractionError,
    ExtractedAsset,
    extract_document,
)
from app.modules.paper_agent.services.persistence import (
    QuestionPersistenceContext,
    require_taxonomy_codes,
)
from app.modules.paper_agent.services.question_parser import IMAGE_RE, parse_question_text
from app.modules.paper_agent.services.resource_storage import (
    get_stored_resource_file,
    image_schema_for_resource,
    recover_question,
    source_schema,
)
from app.modules.paper_agent.services.webpage_question_parser import (
    parse_openstax_questions,
)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _asset_image(
    asset: ExtractedAsset,
    *,
    source,
    storage_root: Path,
    source_resource_id: str,
) -> tuple[QuestionImage, Path]:
    resource_id = str(uuid.uuid4())
    destination = (
        storage_root
        / "assets"
        / source_resource_id
        / f"{resource_id}{asset.suffix}"
    )
    return (
        QuestionImage(
            resource_id=resource_id,
            uri=str(destination),
            source=source,
            mime_type=asset.mime_type,
            sha256=hashlib.sha256(asset.data).hexdigest(),
            alt_text=asset.original_name,
        ),
        destination,
    )


def _question_resource_ids(questions: list[Question]) -> list[str]:
    resource_ids: list[str] = []
    seen: set[str] = set()

    def visit(question: Question) -> None:
        for image in question.images:
            if image.resource_id not in seen:
                seen.add(image.resource_id)
                resource_ids.append(image.resource_id)
        for option in question.options:
            for image in option.images:
                if image.resource_id not in seen:
                    seen.add(image.resource_id)
                    resource_ids.append(image.resource_id)
        for child in question.subquestions:
            visit(child)

    for question in questions:
        visit(question)
    return resource_ids


async def parse_uploaded_questions(
    session: AsyncSession,
    source_resource_id: str,
    payload: QuestionParseRequest,
    *,
    storage_root: Path,
    max_asset_bytes: int,
) -> ParsedQuestionsResponse:
    stored = await get_stored_resource_file(
        session,
        source_resource_id,
        storage_root=storage_root,
    )
    source = source_schema(stored.source)
    image_map: dict[str, QuestionImage] = {}
    pending_files: list[tuple[Path, bytes]] = []
    warnings: list[str] = []
    if stored.resource.resource_type == "document":
        extracted = await asyncio.to_thread(
            extract_document,
            stored.path,
            stored.resource.mime_type,
        )
        total_asset_bytes = sum(len(asset.data) for asset in extracted.assets)
        if total_asset_bytes > max_asset_bytes:
            raise DocumentExtractionError(
                f"embedded images exceed {max_asset_bytes} bytes"
            )
        for asset in extracted.assets:
            image, destination = _asset_image(
                asset,
                source=source,
                storage_root=storage_root,
                source_resource_id=source_resource_id,
            )
            image_map[asset.marker] = image
            pending_files.append((destination, asset.data))
        for marker in set(IMAGE_RE.findall(extracted.text)) - set(image_map):
            await get_stored_resource_file(
                session,
                marker,
                storage_root=storage_root,
            )
            image_map[marker] = await image_schema_for_resource(session, marker)
        questions = parse_question_text(
            extracted.text,
            source=source,
            difficulty=payload.difficulty,
            images=image_map,
        )
        warnings = extracted.warnings
    elif stored.resource.resource_type == "webpage":
        html = await asyncio.to_thread(
            stored.path.read_text,
            encoding="utf-8",
            errors="replace",
        )
        questions = parse_openstax_questions(
            html,
            source=source,
            difficulty=payload.difficulty,
        )
    else:
        raise DocumentExtractionError(
            "only uploaded documents and collected webpages can be parsed"
        )

    if payload.knowledge_point_codes:
        await require_taxonomy_codes(
            session,
            payload.knowledge_point_codes,
            [],
        )
    referenced_ids = set(_question_resource_ids(questions))
    unreferenced_assets = [
        image.resource_id
        for image in image_map.values()
        if image.resource_id not in referenced_ids
    ]
    if unreferenced_assets:
        raise DocumentExtractionError("one or more embedded images were not assigned to a question")

    written_paths: list[Path] = []
    try:
        for path, data in pending_files:
            await asyncio.to_thread(_write_atomic, path, data)
            written_paths.append(path)
        context = QuestionPersistenceContext(session)
        for position, question in enumerate(questions):
            question_id = await context.save_question(question, position=position)
            session.add_all(
                QuestionKnowledgePointModel(
                    question_id=question_id,
                    knowledge_point_code=code,
                )
                for code in payload.knowledge_point_codes
            )
        await session.flush()
        recovered = [
            await recover_question(session, question.id or "")
            for question in questions
        ]
        await session.commit()
    except Exception:
        await session.rollback()
        for path in written_paths:
            await asyncio.to_thread(path.unlink, missing_ok=True)
        raise

    return ParsedQuestionsResponse(
        source_resource_id=source_resource_id,
        question_ids=[question.id or "" for question in recovered],
        questions=recovered,
        asset_resource_ids=_question_resource_ids(recovered),
        warnings=warnings,
    )
