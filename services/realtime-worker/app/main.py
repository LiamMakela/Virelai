import json
import logging
import os
import time
import uuid
from datetime import datetime

from confluent_kafka import (
    Consumer,
    TopicPartition,
)
from pydantic import (
    BaseModel,
    ValidationError,
)
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


def event_stream_fields(
    event: PlaybackEvent,
) -> dict[str, str]:
    fields = {
        "event_id":
            str(event.event_id),

        "session_id":
            str(event.session_id),

        "video_id":
            str(event.video_id),

        "sequence_number":
            str(event.sequence_number),

        "event_time":
            event.event_time.isoformat(),

        "event_type":
            event.event_type,
    }


    optional_integer_fields = {
        "playback_position_ms":
            event.playback_position_ms,

        "buffer_duration_ms":
            event.buffer_duration_ms,

        "quality_height":
            event.quality_height,

        "bitrate_kbps":
            event.bitrate_kbps,

        "startup_time_ms":
            event.startup_time_ms,

        "watch_delta_ms":
            event.watch_delta_ms,

        "seek_from_ms":
            event.seek_from_ms,

        "seek_to_ms":
            event.seek_to_ms,
    }


    for (
        field_name,
        value,
    ) in optional_integer_fields.items():

        if value is not None:
            fields[field_name] = (
                str(value)
            )


    if event.error_code is not None:
        fields["error_code"] = (
            event.error_code
        )


    if event.metadata is not None:
        fields["metadata"] = (
            json.dumps(
                event.metadata
            )
        )


    return fields


def process_events(
    events: list[PlaybackEvent],
) -> None:
    if not events:
        return


    now = time.time()

    cutoff = (
        now
        - EVENT_RETENTION_SECONDS
    )


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


    touched_video_ids: set[
        str
    ] = set()


    #
    # One Redis pipeline for the entire
    # Kafka batch.
    #
    pipe = redis_client.pipeline(
        transaction=False
    )


    for event in events:
        event_id = str(
            event.event_id
        )

        session_id = str(
            event.session_id
        )

        video_id = str(
            event.video_id
        )

        touched_video_ids.add(
            video_id
        )


        event_timestamp = (
            event.event_time.timestamp()
        )


        video_events_key = (
            f"video:{video_id}:"
            "realtime:events"
        )

        video_buffers_key = (
            f"video:{video_id}:"
            "realtime:buffers"
        )

        video_errors_key = (
            f"video:{video_id}:"
            "realtime:errors"
        )

        video_active_key = (
            f"video:{video_id}:"
            "active_sessions"
        )


        #
        # All realtime events.
        #
        pipe.zadd(
            platform_events_key,
            {
                event_id:
                    event_timestamp,
            },
        )

        pipe.zadd(
            video_events_key,
            {
                event_id:
                    event_timestamp,
            },
        )


        #
        # Buffering projection.
        #
        if (
            event.event_type
            == "buffer_ended"
        ):
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


        #
        # Error projection.
        #
        if (
            event.event_type
            == "playback_error"
        ):
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


        #
        # Active-viewer projection.
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

            if (
                metadata.get("fatal")
                is True
            ):
                pipe.zrem(
                    platform_active_key,
                    session_id,
                )

                pipe.zrem(
                    video_active_key,
                    session_id,
                )


        #
        # Rolling live event stream used by
        # the SSE operations dashboard.
        #
        pipe.xadd(
            "realtime:event_stream",

            event_stream_fields(
                event
            ),

            maxlen=(
                LIVE_STREAM_MAX_LENGTH
            ),

            approximate=True,
        )


    #
    # Trim platform-level structures ONCE
    # per Kafka batch instead of once for
    # every single event.
    #
    pipe.zremrangebyscore(
        platform_events_key,
        "-inf",
        cutoff,
    )

    pipe.zremrangebyscore(
        platform_buffers_key,
        "-inf",
        cutoff,
    )

    pipe.zremrangebyscore(
        platform_errors_key,
        "-inf",
        cutoff,
    )


    #
    # Trim each touched video's structures
    # once per batch.
    #
    for video_id in touched_video_ids:

        prefix = (
            f"video:{video_id}"
        )

        pipe.zremrangebyscore(
            f"{prefix}:realtime:events",
            "-inf",
            cutoff,
        )

        pipe.zremrangebyscore(
            f"{prefix}:realtime:buffers",
            "-inf",
            cutoff,
        )

        pipe.zremrangebyscore(
            f"{prefix}:realtime:errors",
            "-inf",
            cutoff,
        )


    #
    # ONE Redis network round trip for
    # the batch.
    #
    pipe.execute()


def offsets_for_messages(
    messages,
) -> list[TopicPartition]:
    """
    Commit the highest successfully processed
    offset + 1 for every Kafka partition
    represented in the batch.
    """

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
        ), offset
        in offsets.items()
    ]


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
        "topic=%s batch_size=%s",
        KAFKA_TOPIC,
        BATCH_SIZE,
    )


    try:
        while True:

            #
            # Pull as many as 500 Kafka
            # messages at once.
            #
            messages = (
                consumer.consume(
                    num_messages=(
                        BATCH_SIZE
                    ),
                    timeout=(
                        BATCH_TIMEOUT_SECONDS
                    ),
                )
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
                    # Bad payloads will not become
                    # valid if retried forever.
                    #
                    logger.exception(
                        "invalid playback event "
                        "partition=%s "
                        "offset=%s",
                        message.partition(),
                        message.offset(),
                    )


            if not processable_messages:
                continue


            try:
                #
                # FIRST:
                # update Redis for the entire batch.
                #
                process_events(
                    valid_events
                )


                #
                # THEN:
                # advance Kafka.
                #
                offsets = (
                    offsets_for_messages(
                        processable_messages
                    )
                )


                committed = (
                    consumer.commit(
                        offsets=offsets,
                        asynchronous=False,
                    )
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
                            f"[{partition.partition}]"
                            ": "
                            f"{partition.error}"
                        )


                logger.info(
                    "updated realtime batch "
                    "received=%s "
                    "valid=%s "
                    "partitions=%s",
                    len(
                        processable_messages
                    ),
                    len(
                        valid_events
                    ),
                    len(
                        offsets
                    ),
                )


            except Exception:
                logger.exception(
                    "realtime batch failed; "
                    "Kafka offsets were not "
                    "committed"
                )

                #
                # Let Docker restart the worker.
                #
                # Redis sorted-set updates are
                # idempotent because event/session
                # IDs are members.
                #
                # The rolling SSE stream may see a
                # duplicate after an extremely
                # unlucky crash/replay, which is
                # acceptable for this ephemeral
                # operations feed.
                #
                raise


    finally:
        consumer.close()

        redis_client.close()


if __name__ == "__main__":
    main()