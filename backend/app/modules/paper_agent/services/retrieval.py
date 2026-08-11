"""PostgreSQL keyword + Qdrant vector retrieval for paper questions."""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.qdrant import ensure_question_collection, get_qdrant
from app.models import (
    KnowledgePointModel,
    QuestionKnowledgePointModel,
    QuestionModel,
    QuestionOptionModel,
)
from app.modules.paper_agent.schemas.retrieval import (
    DeduplicationReport,
    HybridQuestionCandidate,
    HybridQuestionSearchRequest,
    HybridQuestionSearchResponse,
    QuestionIndexRequest,
    QuestionIndexResponse,
)
from app.modules.paper_agent.services.deduplication import (
    DeduplicationCandidate,
    deduplicate_candidates,
)
from app.services.embedding import embed


EmbeddingFunction = Callable[[list[str]], Awaitable[list[list[float]]]]
POINT_NAMESPACE = uuid.UUID("6741f5be-5a0e-4f1f-81c7-25e59864249a")
RRF_CONSTANT = 60


class RetrievalFilterError(ValueError):
    pass


class QuestionIndexSelectionError(ValueError):
    pass


class QuestionVectorStoreError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class QuestionDocument:
    question_id: str
    source_id: str
    question_type: str
    difficulty: str
    stem: str
    knowledge_point_codes: tuple[str, ...]
    search_text: str
    deduplication_text: str


def question_point_id(question_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, question_id))


def _answer_text(answer) -> str:
    if answer is None:
        return ""
    if isinstance(answer, str):
        return answer
    return json.dumps(answer, ensure_ascii=False, sort_keys=True)


async def _load_question_documents(
    session: AsyncSession,
    *,
    question_ids: Sequence[str] | None = None,
    knowledge_point_codes: Sequence[str] | None = None,
    question_types: Sequence[str] | None = None,
    limit: int | None = None,
) -> list[QuestionDocument]:
    id_statement = (
        select(QuestionModel.id)
        .join(
            QuestionKnowledgePointModel,
            QuestionKnowledgePointModel.question_id == QuestionModel.id,
        )
        .where(QuestionModel.parent_question_id.is_(None))
        .distinct()
        .order_by(QuestionModel.id)
    )
    if question_ids:
        id_statement = id_statement.where(QuestionModel.id.in_(question_ids))
    if knowledge_point_codes:
        id_statement = id_statement.where(
            QuestionKnowledgePointModel.knowledge_point_code.in_(
                knowledge_point_codes
            )
        )
    if question_types:
        id_statement = id_statement.where(
            QuestionModel.question_type.in_(question_types)
        )
    if limit is not None:
        id_statement = id_statement.limit(limit)

    selected_ids = list(await session.scalars(id_statement))
    if not selected_ids:
        return []

    question_models = {
        question.id: question
        for question in await session.scalars(
            select(QuestionModel).where(QuestionModel.id.in_(selected_ids))
        )
    }
    option_rows = (
        await session.execute(
            select(
                QuestionOptionModel.question_id,
                QuestionOptionModel.label,
                QuestionOptionModel.content,
            )
            .where(QuestionOptionModel.question_id.in_(selected_ids))
            .order_by(
                QuestionOptionModel.question_id,
                QuestionOptionModel.position,
            )
        )
    ).all()
    knowledge_rows = (
        await session.execute(
            select(
                QuestionKnowledgePointModel.question_id,
                KnowledgePointModel.code,
                KnowledgePointModel.name,
                KnowledgePointModel.description,
            )
            .join(
                KnowledgePointModel,
                KnowledgePointModel.code
                == QuestionKnowledgePointModel.knowledge_point_code,
            )
            .where(
                QuestionKnowledgePointModel.question_id.in_(selected_ids),
                KnowledgePointModel.is_active.is_(True),
            )
            .order_by(
                QuestionKnowledgePointModel.question_id,
                KnowledgePointModel.code,
            )
        )
    ).all()

    options_by_question: dict[str, list[str]] = {}
    for question_id, label, content in option_rows:
        options_by_question.setdefault(question_id, []).append(
            f"{label}. {content or ''}".strip()
        )
    knowledge_by_question: dict[str, list[tuple[str, str, str]]] = {}
    for question_id, code, name, description in knowledge_rows:
        knowledge_by_question.setdefault(question_id, []).append(
            (code, name, description)
        )

    documents: list[QuestionDocument] = []
    for question_id in selected_ids:
        question = question_models[question_id]
        knowledge = knowledge_by_question.get(question_id, [])
        if not knowledge:
            continue
        sections = [
            question.stem,
            *options_by_question.get(question_id, []),
            _answer_text(question.answer),
            question.explanation or "",
            *[f"{code} {name} {description}" for code, name, description in knowledge],
        ]
        documents.append(
            QuestionDocument(
                question_id=question.id,
                source_id=question.source_id,
                question_type=question.question_type,
                difficulty=question.difficulty,
                stem=question.stem,
                knowledge_point_codes=tuple(code for code, _, _ in knowledge),
                search_text="\n".join(section for section in sections if section),
                deduplication_text="\n".join(
                    section
                    for section in [
                        question.stem,
                        *options_by_question.get(question_id, []),
                    ]
                    if section
                ),
            )
        )
    return documents


def _compact_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def lexical_features(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    features = set(re.findall(r"[a-z0-9]+", normalized))
    chinese = "".join(re.findall(r"[\u3400-\u9fff]", normalized))
    features.update(chinese)
    features.update(chinese[index:index + 2] for index in range(len(chinese) - 1))
    compact = _compact_text(normalized)
    if compact:
        features.add(compact)
    return features


def keyword_relevance(query: str, document: str) -> float:
    query_features = lexical_features(query)
    if not query_features:
        return 0.0
    document_features = lexical_features(document)
    overlap = len(query_features & document_features) / len(query_features)
    compact_query = _compact_text(query)
    phrase_bonus = float(bool(compact_query and compact_query in _compact_text(document)))
    return min(1.0, 0.8 * overlap + 0.2 * phrase_bonus)


async def index_questions(
    session: AsyncSession,
    payload: QuestionIndexRequest,
    *,
    client: QdrantClient | None = None,
    embedder: EmbeddingFunction = embed,
) -> QuestionIndexResponse:
    documents = await _load_question_documents(
        session,
        question_ids=payload.question_ids or None,
    )
    if payload.question_ids:
        found = {document.question_id for document in documents}
        missing = sorted(set(payload.question_ids) - found)
        if missing:
            raise QuestionIndexSelectionError(
                "questions are missing or have no active knowledge point: "
                + ", ".join(missing)
            )
    if not documents:
        return QuestionIndexResponse(
            collection=settings.paper_agent_question_collection,
            indexed_count=0,
            requested_count=len(payload.question_ids) if payload.question_ids else None,
        )

    vectors = await embedder([document.search_text for document in documents])
    if len(vectors) != len(documents) or any(
        len(vector) != settings.embedding_dim for vector in vectors
    ):
        raise QuestionVectorStoreError("embedding output dimension is invalid")

    qdrant = await asyncio.to_thread(
        ensure_question_collection,
        client or get_qdrant(),
    )
    points = [
        qmodels.PointStruct(
            id=question_point_id(document.question_id),
            vector=vector,
            payload={
                "question_id": document.question_id,
                "question_type": document.question_type,
                "difficulty": document.difficulty,
                "knowledge_point_codes": list(document.knowledge_point_codes),
            },
        )
        for document, vector in zip(documents, vectors, strict=True)
    ]
    try:
        await asyncio.to_thread(
            qdrant.upsert,
            collection_name=settings.paper_agent_question_collection,
            points=points,
            wait=True,
        )
    except Exception as exc:
        raise QuestionVectorStoreError("question vector indexing failed") from exc
    return QuestionIndexResponse(
        collection=settings.paper_agent_question_collection,
        indexed_count=len(points),
        requested_count=len(payload.question_ids) if payload.question_ids else None,
    )


async def _validate_knowledge_points(
    session: AsyncSession,
    codes: Sequence[str],
) -> None:
    known = set(
        await session.scalars(
            select(KnowledgePointModel.code).where(
                KnowledgePointModel.code.in_(codes),
                KnowledgePointModel.is_active.is_(True),
            )
        )
    )
    missing = sorted(set(codes) - known)
    if missing:
        raise RetrievalFilterError(
            "unknown or inactive knowledge points: " + ", ".join(missing)
        )


async def hybrid_search_questions(
    session: AsyncSession,
    payload: HybridQuestionSearchRequest,
    *,
    client: QdrantClient | None = None,
    embedder: EmbeddingFunction = embed,
    candidate_limit: int | None = None,
) -> HybridQuestionSearchResponse:
    await _validate_knowledge_points(session, payload.knowledge_point_codes)
    pool_limit = candidate_limit or settings.paper_agent_retrieval_pool_size
    question_types = [question_type.value for question_type in payload.question_types]
    documents = await _load_question_documents(
        session,
        knowledge_point_codes=payload.knowledge_point_codes,
        question_types=question_types,
        limit=pool_limit,
    )
    documents_by_id = {document.question_id: document for document in documents}

    keyword_scores: dict[str, float] = {}
    keyword_ranked: list[str] = []
    if payload.keyword_weight > 0:
        keyword_scores = {
            document.question_id: keyword_relevance(
                payload.query,
                document.search_text,
            )
            for document in documents
        }
        keyword_ranked = [
            question_id
            for question_id, score in sorted(
                keyword_scores.items(),
                key=lambda item: (-item[1], item[0]),
            )
            if score > 0
        ]

    vector_scores: dict[str, float] = {}
    vector_ranked: list[str] = []
    if payload.vector_weight > 0 and documents:
        query_vectors = await embedder([payload.query])
        if len(query_vectors) != 1 or len(query_vectors[0]) != settings.embedding_dim:
            raise QuestionVectorStoreError("query embedding dimension is invalid")
        qdrant = await asyncio.to_thread(
            ensure_question_collection,
            client or get_qdrant(),
        )
        retrieval_filter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="knowledge_point_codes",
                    match=qmodels.MatchAny(any=payload.knowledge_point_codes),
                ),
                qmodels.FieldCondition(
                    key="question_type",
                    match=qmodels.MatchAny(any=question_types),
                ),
            ]
        )
        try:
            result = await asyncio.to_thread(
                qdrant.query_points,
                collection_name=settings.paper_agent_question_collection,
                query=query_vectors[0],
                query_filter=retrieval_filter,
                limit=min(pool_limit, max(payload.top_k * 10, payload.top_k)),
                with_payload=True,
            )
        except Exception as exc:
            raise QuestionVectorStoreError("question vector search failed") from exc
        returned_ids = [
            str((point.payload or {}).get("question_id", ""))
            for point in result.points
            if (point.payload or {}).get("question_id")
        ]
        vector_documents = await _load_question_documents(
            session,
            question_ids=returned_ids,
            knowledge_point_codes=payload.knowledge_point_codes,
            question_types=question_types,
        )
        documents_by_id.update(
            {document.question_id: document for document in vector_documents}
        )
        for point in result.points:
            question_id = str((point.payload or {}).get("question_id", ""))
            if question_id in documents_by_id:
                vector_ranked.append(question_id)
                vector_scores[question_id] = max(-1.0, min(1.0, float(point.score)))

    keyword_ranks = {
        question_id: rank
        for rank, question_id in enumerate(keyword_ranked, start=1)
    }
    vector_ranks = {
        question_id: rank
        for rank, question_id in enumerate(vector_ranked, start=1)
    }
    total_weight = payload.keyword_weight + payload.vector_weight
    fused: list[tuple[str, float]] = []
    for question_id in set(keyword_ranks) | set(vector_ranks):
        score = 0.0
        if question_id in keyword_ranks:
            score += payload.keyword_weight / (
                RRF_CONSTANT + keyword_ranks[question_id]
            )
        if question_id in vector_ranks:
            score += payload.vector_weight / (
                RRF_CONSTANT + vector_ranks[question_id]
            )
        fused.append((question_id, score / total_weight))
    fused.sort(
        key=lambda item: (
            -item[1],
            -keyword_scores.get(item[0], 0.0),
            -vector_scores.get(item[0], -1.0),
            item[0],
        )
    )

    fused_for_output = fused
    if payload.deduplicate and len(fused_for_output) > 1:
        deduplication_pool = fused_for_output[: min(pool_limit, payload.top_k * 5)]
        deduplication_documents = [
            documents_by_id[question_id]
            for question_id, _ in deduplication_pool
        ]
        deduplication_vectors = await embedder(
            [document.deduplication_text for document in deduplication_documents]
        )
        if len(deduplication_vectors) != len(deduplication_documents) or any(
            len(vector) != settings.embedding_dim
            for vector in deduplication_vectors
        ):
            raise QuestionVectorStoreError("deduplication embedding dimension is invalid")
        deduplication_result = deduplicate_candidates(
            [
                DeduplicationCandidate(
                    question_id=document.question_id,
                    question_type=document.question_type,
                    content=document.deduplication_text,
                )
                for document in deduplication_documents
            ],
            deduplication_vectors,
            semantic_similarity_threshold=payload.semantic_similarity_threshold,
        )
        retained_ids = set(deduplication_result.retained_ids)
        fused_for_output = [
            item for item in deduplication_pool if item[0] in retained_ids
        ]
        deduplication_report = deduplication_result.report
    else:
        input_count = min(len(fused_for_output), payload.top_k)
        deduplication_report = DeduplicationReport(
            input_count=input_count,
            exact_duplicate_count=0,
            semantic_duplicate_count=0,
            retained_count=input_count,
            output_count=input_count,
            remaining_duplicate_ratio=0.0,
        )

    candidates = []
    for rank, (question_id, hybrid_score) in enumerate(
        fused_for_output[:payload.top_k],
        start=1,
    ):
        document = documents_by_id[question_id]
        candidates.append(
            HybridQuestionCandidate(
                rank=rank,
                question_id=question_id,
                source_id=document.source_id,
                question_type=document.question_type,
                difficulty=document.difficulty,
                stem=document.stem,
                knowledge_point_codes=list(document.knowledge_point_codes),
                keyword_score=keyword_scores.get(question_id, 0.0),
                vector_score=vector_scores.get(question_id),
                hybrid_score=hybrid_score,
            )
        )
    return HybridQuestionSearchResponse(
        query=payload.query,
        candidates=candidates,
        keyword_candidate_count=len(keyword_ranked),
        vector_candidate_count=len(vector_ranked),
        deduplication=deduplication_report.model_copy(
            update={"output_count": len(candidates)}
        ),
    )
