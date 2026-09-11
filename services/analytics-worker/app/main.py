import logging
import os
import uuid
from datetime import datetime

import psycopg

from confluent_kafka import Consumer
from pydantic import BaseModel


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
    "virelai.analytics"
)


DATABASE_URL = os.environ[
    "DATABASE_URL"
]

KAFKA_BOOTSTRAP_SERVERS = os.environ[
    "KAFKA_BOOTSTRAP_SERVERS"
]

KAFKA_TOPIC = os.environ.get(
    "KAFKA_TOPIC_PLAYBACK_EVENTS",
    "playback.events.v1",
)


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


def persist_event(
    event: PlaybackEvent,
) -> None:
    with psycopg.connect(
        DATABASE_URL
    ) as connection:
        with connection.cursor() as cursor:

            cursor.execute(
                """
                INSERT INTO playback_events (
                    id,
                    session_id,
                    video_id,
                    sequence_number,
                    event_time,
                    event_type,
                    playback_position_ms,
                    buffer_duration_ms,
                    bitrate_kbps,
                    quality_height,
                    error_code,
                    event_metadata
                )
                VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (
                    session_id,
                    sequence_number
                )
                DO NOTHING
                """,
                (
                    event.event_id,
                    event.session_id,
                    event.video_id,
                    event.sequence_number,
                    event.event_time,
                    event.event_type,
                    event.playback_position_ms,
                    event.buffer_duration_ms,
                    event.bitrate_kbps,
                    event.quality_height,
                    event.error_code,
                    event.metadata,
                ),
            )

            if (
                event.event_type
                == "playback_ended"
            ):
                cursor.execute(
                    """
                    UPDATE playback_sessions
                    SET ended_at = %s
                    WHERE id = %s
                    """,
                    (
                        event.event_time,
                        event.session_id,
                    ),
                )

        connection.commit()


def main():
    consumer = Consumer(
        {
            "bootstrap.servers": (
                KAFKA_BOOTSTRAP_SERVERS
            ),

            "group.id": (
                "virelai-analytics-persist"
            ),

            "enable.auto.commit": False,

            "auto.offset.reset": "earliest",
        }
    )

    consumer.subscribe(
        [KAFKA_TOPIC]
    )

    logger.info(
        "analytics worker started topic=%s",
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

                persist_event(
                    event
                )

                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

                logger.info(
                    "persisted event "
                    "session=%s seq=%s type=%s",
                    event.session_id,
                    event.sequence_number,
                    event.event_type,
                )

            except Exception:
                logger.exception(
                    "failed to process playback event"
                )

                # Later:
                # retries + DLQ.
                #
                # For now avoid poison-message loops.
                consumer.commit(
                    message=message,
                    asynchronous=False,
                )

    finally:
        consumer.close()


if __name__ == "__main__":
    main()