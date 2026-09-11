import json
import logging
import os
import time
import uuid
from datetime import datetime

from confluent_kafka import Consumer
from pydantic import BaseModel, ValidationError
from redis import Redis


logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s "
        "%(levelname)s "
        "%(name)s "
        "%(message)s"
    ),
)

logger = logging.getLogger(
    "virelai.realtime"
)


KAFKA_BOOTSTRAP_SERVERS = os.environ[
    "KAFKA_BOOTSTRAP_SERVERS"
]

KAFKA_TOPIC = os.environ.get(
    "KAFKA_TOPIC_PLAYBACK_EVENTS",
    "playback.events.v1",
)

REDIS_URL = os.environ.get(
    "REDIS_URL",
    "redis://redis:6379/0",
)


redis_client = Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


ACTIVE_SESSION_TTL_SECONDS = 30
EVENT_RETENTION_SECONDS = 120
LIVE_STREAM_MAX_LENGTH = 500


class PlaybackEvent(BaseModel):
    event_id: uuid.UUID

    session_id: uuid.UUID
    video_id: uuid.UUID

    sequence_number: int

    event_time: datetime
    event_type: str

    playback_position_ms: int | None = None
    buffer_duration_ms: int | None = None

    bitrate_kbps: int | None = None
    quality_height: int | None = None

    error_code: str | None = None
    metadata: dict | None = None

    startup_time_ms: int | None = None
    watch_delta_ms: int | None = None

    seek_from_ms: int | None = None
    seek_to_ms: int | None = None


def event_stream_fields(
    event: PlaybackEvent,
) -> dict[str, str]:
    fields = {
        "event_id": str(event.event_id),
        "session_id": str(event.session_id),
        "video_id": str(event.video_id),
        "sequence_number": str(
            event.sequence_number
        ),
        "event_time": (
            event.event_time.isoformat()
        ),
        "event_type": event.event_type,
    }

    if event.playback_position_ms is not None:
        fields["playback_position_ms"] = str(
            event.playback_position_ms
        )

    if event.buffer_duration_ms is not None:
        fields["buffer_duration_ms"] = str(
            event.buffer_duration_ms
        )

    if event.quality_height is not None:
        fields["quality_height"] = str(
            event.quality_height
        )

    if event.bitrate_kbps is not None:
        fields["bitrate_kbps"] = str(
            event.bitrate_kbps
        )

    if event.error_code is not None:
        fields["error_code"] = (
            event.error_code
        )

    if event.metadata is not None:
        fields["metadata"] = json.dumps(
            event.metadata
        )

    if event.startup_time_ms is not None:
        fields["startup_time_ms"] = str(
            event.startup_time_ms
        )

    if event.watch_delta_ms is not None:
        fields["watch_delta_ms"] = str(
            event.watch_delta_ms
        )

    if event.seek_from_ms is not None:
        fields["seek_from_ms"] = str(
            event.seek_from_ms
        )

    if event.seek_to_ms is not None:
        fields["seek_to_ms"] = str(
            event.seek_to_ms
        )

    return fields


def process_event(
    event: PlaybackEvent,
) -> None:
    event_id = str(event.event_id)
    session_id = str(event.session_id)
    video_id = str(event.video_id)

    event_timestamp = (
        event.event_time.timestamp()
    )

    now = time.time()

    platform_events_key = (
        "realtime:events"
    )

    platform_buffers_key = (
        "realtime:buffers"
    )

    platform_errors_key = (
        "realtime:errors"
    )

    platform_active_key = (
        "realtime:active_sessions"
    )

    video_events_key = (
        f"video:{video_id}:realtime:events"
    )

    video_buffers_key = (
        f"video:{video_id}:realtime:buffers"
    )

    video_errors_key = (
        f"video:{video_id}:realtime:errors"
    )

    video_active_key = (
        f"video:{video_id}:active_sessions"
    )

    pipe = redis_client.pipeline(
        transaction=False
    )

    #
    # Every event goes into a timestamp-scored
    # sorted set.
    #
    # Using event_id as the member makes retries
    # naturally idempotent for these counters.
    #
    pipe.zadd(
        platform_events_key,
        {
            event_id: event_timestamp,
        },
    )

    pipe.zadd(
        video_events_key,
        {
            event_id: event_timestamp,
        },
    )

    #
    # Trim old realtime events so Redis remains
    # bounded.
    #
    cutoff = (
        now
        - EVENT_RETENTION_SECONDS
    )

    pipe.zremrangebyscore(
        platform_events_key,
        "-inf",
        cutoff,
    )

    pipe.zremrangebyscore(
        video_events_key,
        "-inf",
        cutoff,
    )

    if event.event_type == "buffer_ended":
        pipe.zadd(
            platform_buffers_key,
            {
                event_id:
                    event_timestamp,
            },
        )

        pipe.zadd(
            video_buffers_key,
            {
                event_id:
                    event_timestamp,
            },
        )

        pipe.zremrangebyscore(
            platform_buffers_key,
            "-inf",
            cutoff,
        )

        pipe.zremrangebyscore(
            video_buffers_key,
            "-inf",
            cutoff,
        )

    if event.event_type == "playback_error":
        pipe.zadd(
            platform_errors_key,
            {
                event_id:
                    event_timestamp,
            },
        )

        pipe.zadd(
            video_errors_key,
            {
                event_id:
                    event_timestamp,
            },
        )

        pipe.zremrangebyscore(
            platform_errors_key,
            "-inf",
            cutoff,
        )

        pipe.zremrangebyscore(
            video_errors_key,
            "-inf",
            cutoff,
        )

    #
    # Active viewer projection.
    #
    # A score represents the most recent known
    # activity timestamp for that session.
    #
    if event.event_type in {
        "playback_started",
        "resume",
        "heartbeat",
        "buffer_started",
        "buffer_ended",
    }:
        pipe.zadd(
            platform_active_key,
            {
                session_id:
                    event_timestamp,
            },
        )

        pipe.zadd(
            video_active_key,
            {
                session_id:
                    event_timestamp,
            },
        )

    elif event.event_type in {
        "pause",
        "playback_ended",
    }:
        pipe.zrem(
            platform_active_key,
            session_id,
        )

        pipe.zrem(
            video_active_key,
            session_id,
        )

    elif (
        event.event_type
        == "playback_error"
    ):
        metadata = (
            event.metadata or {}
        )

        if metadata.get("fatal") is True:
            pipe.zrem(
                platform_active_key,
                session_id,
            )

            pipe.zrem(
                video_active_key,
                session_id,
            )

    #
    # Keep a small rolling Redis Stream for the
    # eventual SSE operations dashboard.
    #
    pipe.xadd(
        "realtime:event_stream",
        event_stream_fields(event),
        maxlen=LIVE_STREAM_MAX_LENGTH,
        approximate=True,
    )

    pipe.execute()


def main() -> None:
    redis_client.ping()

    consumer = Consumer(
        {
            "bootstrap.servers":
                KAFKA_BOOTSTRAP_SERVERS,

            "group.id":
                "virelai-realtime",

            "enable.auto.commit":
                False,

            "auto.offset.reset":
                "earliest",
        }
    )

    consumer.subscribe(
        [
            KAFKA_TOPIC,
        ]
    )

    logger.info(
        "realtime worker started "
        "topic=%s",
        KAFKA_TOPIC,
    )

    try:
        while True:
            message = consumer.poll(
                timeout=1.0
            )

            if message is None:
                continue

            if message.error():
                logger.error(
                    "Kafka error: %s",
                    message.error(),
                )

                continue

            try:
                event = (
                    PlaybackEvent
                    .model_validate_json(
                        message.value()
                    )
                )

                process_event(
                    event
                )

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

                logger.info(
                    "updated realtime state "
                    "session=%s seq=%s type=%s",
                    event.session_id,
                    event.sequence_number,
                    event.event_type,
                )

            except ValidationError:
                logger.exception(
                    "invalid playback event"
                )

                # Poison events cannot become valid
                # by retrying forever.
                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

            except Exception:
                logger.exception(
                    "realtime update failed"
                )

                #
                # Do NOT commit.
                #
                # Redis sorted-set updates are largely
                # idempotent because event_id/session_id
                # is the member, so this message can
                # safely retry.
                #

    finally:
        consumer.close()
        redis_client.close()


if __name__ == "__main__":
    main()