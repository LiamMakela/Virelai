import logging
import os
import uuid
from datetime import datetime

import psycopg

from confluent_kafka import (
    Consumer,
    TopicPartition,
)
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ValidationError


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


BATCH_SIZE = 500
BATCH_TIMEOUT_SECONDS = 1.0


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


INSERT_EVENT_SQL = """
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
    event_metadata,

    startup_time_ms,
    watch_delta_ms,

    seek_from_ms,
    seek_to_ms
)
VALUES (
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s
)
ON CONFLICT (
    session_id,
    sequence_number
)
DO NOTHING
"""


UPDATE_SESSION_END_SQL = """
UPDATE playback_sessions
SET ended_at = %s
WHERE id = %s
"""


def event_row(
    event: PlaybackEvent,
):
    return (
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

        (
            Jsonb(event.metadata)
            if event.metadata
            is not None
            else None
        ),

        event.startup_time_ms,
        event.watch_delta_ms,

        event.seek_from_ms,
        event.seek_to_ms,
    )


def persist_events(
    events: list[PlaybackEvent],
) -> None:
    if not events:
        return

    rows = [
        event_row(event)
        for event in events
    ]

    ended_sessions = [
        (
            event.event_time,
            event.session_id,
        )
        for event in events
        if event.event_type
        == "playback_ended"
    ]

    #
    # One PostgreSQL connection
    # + one transaction
    # for the entire Kafka batch.
    #
    with psycopg.connect(
        DATABASE_URL
    ) as connection:

        with connection.cursor() as cursor:

            cursor.executemany(
                INSERT_EVENT_SQL,
                rows,
            )

            if ended_sessions:
                cursor.executemany(
                    UPDATE_SESSION_END_SQL,
                    ended_sessions,
                )

        connection.commit()


def offsets_for_messages(
    messages,
) -> list[TopicPartition]:
    #
    # A consume() call can contain messages
    # from several Kafka partitions.
    #
    # We need to commit the highest processed
    # offset + 1 for EACH partition.
    #
    offsets: dict[
        tuple[str, int],
        int,
    ] = {}

    for message in messages:
        if message.error():
            continue

        key = (
            message.topic(),
            message.partition(),
        )

        next_offset = (
            message.offset() + 1
        )

        previous = offsets.get(
            key
        )

        if (
            previous is None
            or next_offset > previous
        ):
            offsets[key] = (
                next_offset
            )

    return [
        TopicPartition(
            topic,
            partition,
            offset,
        )
        for (
            topic,
            partition,
        ), offset in offsets.items()
    ]


def main():
    consumer = Consumer(
        {
            "bootstrap.servers":
                KAFKA_BOOTSTRAP_SERVERS,

            "group.id":
                "virelai-analytics-persist",

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
        "analytics worker started "
        "topic=%s batch_size=%s",
        KAFKA_TOPIC,
        BATCH_SIZE,
    )

    try:
        while True:
            messages = consumer.consume(
                num_messages=BATCH_SIZE,
                timeout=(
                    BATCH_TIMEOUT_SECONDS
                ),
            )

            if not messages:
                continue

            valid_events: list[
                PlaybackEvent
            ] = []

            processable_messages = []

            for message in messages:

                if message.error():
                    logger.error(
                        "Kafka error: %s",
                        message.error(),
                    )

                    continue

                processable_messages.append(
                    message
                )

                try:
                    event = (
                        PlaybackEvent
                        .model_validate_json(
                            message.value()
                        )
                    )

                    valid_events.append(
                        event
                    )

                except ValidationError:
                    #
                    # Poison message:
                    # log it and allow its
                    # Kafka offset to advance.
                    #
                    logger.exception(
                        "invalid playback event "
                        "partition=%s offset=%s",
                        message.partition(),
                        message.offset(),
                    )

            if not processable_messages:
                continue

            try:
                #
                # FIRST:
                # persist the whole valid batch.
                #
                persist_events(
                    valid_events
                )

                #
                # THEN:
                # commit Kafka offsets.
                #
                # If PostgreSQL fails, this never
                # runs and Kafka retains the batch.
                #
                offsets = (
                    offsets_for_messages(
                        processable_messages
                    )
                )

                committed = consumer.commit(
                    offsets=offsets,
                    asynchronous=False,
                )

                for partition in (
                    committed or []
                ):
                    if (
                        partition.error
                        is not None
                    ):
                        raise RuntimeError(
                            "Kafka offset commit "
                            "failed for "
                            f"{partition.topic}"
                            f"[{partition.partition}]: "
                            f"{partition.error}"
                        )

                logger.info(
                    "persisted batch "
                    "received=%s valid=%s "
                    "partitions=%s",
                    len(
                        processable_messages
                    ),
                    len(
                        valid_events
                    ),
                    len(offsets),
                )

            except Exception:
                logger.exception(
                    "batch persistence failed; "
                    "exiting without committing "
                    "Kafka offsets"
                )

                #
                # Exit intentionally.
                #
                # Docker restart policy brings the
                # worker back and Kafka resumes from
                # the last successfully committed
                # offsets.
                #
                raise

    finally:
        consumer.close()


if __name__ == "__main__":
    main()