from redis.asyncio import Redis

from app.core.config import settings


if settings.redis_host:
    redis_client = Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        ssl=settings.redis_tls,
        decode_responses=True,
    )
else:
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


async def close_redis() -> None:
    await redis_client.aclose()