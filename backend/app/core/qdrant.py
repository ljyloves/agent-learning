from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

from app.config import settings


def get_qdrant() -> QdrantClient:
    return QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_rest_port,
        api_key=settings.qdrant_api_key,
        https=False,
    )


def _ensure_collection(
    client: QdrantClient,
    collection_name: str,
    payload_fields: list[str],
) -> None:
    existing = {collection.name for collection in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )

    indexed_fields = set(client.get_collection(collection_name).payload_schema)
    for field in payload_fields:
        if field not in indexed_fields:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )


def ensure_question_collection(client: QdrantClient | None = None) -> QdrantClient:
    qdrant = client or get_qdrant()
    _ensure_collection(
        qdrant,
        settings.paper_agent_question_collection,
        ["question_id", "question_type", "difficulty", "knowledge_point_codes"],
    )
    return qdrant


def init_collections() -> None:
    client = get_qdrant()
    _ensure_collection(
        client,
        settings.qdrant_collection,
        ["document_id", "source"],
    )
    ensure_question_collection(client)
