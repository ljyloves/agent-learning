import asyncio
from threading import Lock

from sentence_transformers import SentenceTransformer

from app.config import settings

_model: SentenceTransformer | None = None
_lock = Lock()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                _model = SentenceTransformer(settings.embedding_model)
    return _model


async def embed(texts: list[str]) -> list[list[float]]:
    model = await asyncio.to_thread(_get_model)
    vectors = await asyncio.to_thread(
        model.encode,
        texts,
        normalize_embeddings=True,
    )
    return vectors.tolist()
