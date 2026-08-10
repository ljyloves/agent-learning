import re
import uuid
from typing import TypedDict

from qdrant_client.http import models as qmodels

from app.config import settings
from app.core.qdrant import get_qdrant
from app.services.embedding import embed


class Chunk(TypedDict):
    id: str
    text: str
    document_id: str
    source: str
    chunk_index: int


class SearchResult(TypedDict):
    text: str
    source: str
    score: float


# --- Chunking ---

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            sentences = re.split(r"(?<=[。！？.!?])\s*", para)
            current = ""
            for s in sentences:
                if len(current) + len(s) <= chunk_size:
                    current += s
                else:
                    if current:
                        chunks.append(current.strip())
                    current = s
            if current.strip():
                chunks.append(current.strip())
    return chunks


# --- Index ---

async def index_document(text: str, source: str, document_id: str | None = None) -> str:
    doc_id = document_id or str(uuid.uuid4())
    chunks = split_text(text)
    if not chunks:
        return doc_id

    vectors = await embed(chunks)
    client = get_qdrant()
    points = [
        qmodels.PointStruct(
            id=str(uuid.uuid4()),
            vector=vectors[i],
            payload={
                "document_id": doc_id,
                "source": source,
                "chunk_index": i,
                "text": chunks[i],
            },
        )
        for i in range(len(chunks))
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    return doc_id


# --- Search ---

async def search(query: str, top_k: int = 5) -> list[SearchResult]:
    qv = await embed([query])
    client = get_qdrant()
    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=qv[0],
        limit=top_k,
        with_payload=True,
    ).points
    return [
        SearchResult(
            text=r.payload.get("text", ""),
            source=r.payload.get("source", "unknown"),
            score=r.score,
        )
        for r in results
    ]


# --- RAG Q&A ---

async def rag_query(question: str, top_k: int = 5) -> dict:
    results = await search(question, top_k=top_k)
    if not results:
        return {"answer": "未找到相关文档，无法回答该问题。", "sources": []}

    context = "\n\n---\n\n".join(f"[来源: {r['source']}]\n{r['text']}" for r in results)
    from app.services.llm import chat

    answer = await chat([
        {"role": "system", "content": (
            "你是一个企业知识库助手。根据以下文档内容回答问题。"
            "如果文档内容不足以回答，请明确说明。回答时引用相关来源。"
        )},
        {"role": "user", "content": f"文档内容：\n\n{context}\n\n问题：{question}"},
    ])
    return {
        "answer": answer,
        "sources": [{"source": r["source"], "score": round(r["score"], 3), "text": r["text"][:200]} for r in results],
    }
