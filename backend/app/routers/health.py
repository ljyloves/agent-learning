import logging

from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.database import async_session
from app.core.redis import get_redis
from app.core.qdrant import get_qdrant

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check():
    status = {"database": "down", "redis": "down", "qdrant": "down"}

    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
        if result.scalar_one() == 1:
            status["database"] = "up"
    except SQLAlchemyError:
        logger.exception("Database health check failed")

    try:
        async for r in get_redis():
            await r.ping()
        status["redis"] = "up"
    except Exception:
        pass

    try:
        qdrant = get_qdrant()
        qdrant.get_collections()
        status["qdrant"] = "up"
    except Exception:
        pass

    all_up = all(v == "up" for v in status.values())
    return {"service": "FlowGate", "status": "healthy" if all_up else "degraded", "checks": status}
