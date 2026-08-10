from redis.asyncio import Redis

from app.config import settings


async def get_redis() -> Redis:
    client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        db=0,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()
