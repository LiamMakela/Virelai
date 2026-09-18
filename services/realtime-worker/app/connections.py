import os

from redis import Redis


def redis_connection() -> Redis:
    redis_url = os.environ.get(
        "REDIS_URL"
    )

    if redis_url:
        return Redis.from_url(
            redis_url,
            decode_responses=True,
        )

    use_tls = (
        os.environ.get(
            "REDIS_TLS",
            "true",
        ).lower()
        in {
            "1",
            "true",
            "yes",
        }
    )

    return Redis(
        host=os.environ["REDIS_HOST"],
        port=int(
            os.environ.get(
                "REDIS_PORT",
                "6379",
            )
        ),
        username=os.environ.get(
            "REDIS_USERNAME",
            "default",
        ),
        password=os.environ[
            "REDIS_PASSWORD"
        ],
        ssl=use_tls,
        decode_responses=True,
    )