import json
import os
import threading
import time
import uuid

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from confluent_kafka import Producer
from fastapi import (
    FastAPI,
    HTTPException,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import (
    BaseModel,
    Field,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------


KAFKA_BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:19092",
)

KAFKA_TOPIC = os.environ.get(
    "KAFKA_TOPIC_PLAYBACK_EVENTS",
    "playback.events.v1",
)


# ---------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------


EVENTS_ACCEPTED = Counter(
    "virelai_ingest_events_accepted_total",
    "Playback telemetry events accepted",
)


BATCHES_ACCEPTED = Counter(
    "virelai_ingest_batches_accepted_total",
    "Telemetry batches accepted",
)


KAFKA_PUBLISH_FAILURES = Counter(
    "virelai_ingest_kafka_publish_failures_total",
    "Kafka telemetry publishing failures",
)


BATCH_SIZE = Histogram(
    "virelai_ingest_batch_size",
    "Number of telemetry events per batch",
    buckets=(
        1,
        2,
        5,
        10,
        20,
        50,
        100,
    ),
)


#
# This now measures how long it takes to enqueue
# the batch into the local Kafka producer, NOT
# broker acknowledgement latency.
#
KAFKA_ENQUEUE_DURATION = Histogram(
    "virelai_ingest_kafka_enqueue_duration_seconds",
    "Time required to enqueue a telemetry batch into the Kafka producer",
    buckets=(
        0.0001,
        0.0005,
        0.001,
        0.0025,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
    ),
)


KAFKA_QUEUE_DEPTH = Gauge(
    "virelai_ingest_kafka_queue_depth",
    "Messages waiting in the local Kafka producer queue",
)


# ---------------------------------------------------------
# Kafka producer
# ---------------------------------------------------------


producer = Producer(
    {
        "bootstrap.servers":
            KAFKA_BOOTSTRAP_SERVERS,

        "client.id":
            "virelai-ingest",

        #
        # Wait for acknowledgement from all
        # in-sync replicas.
        #
        "acks":
            "all",

        #
        # Prevent duplicate writes caused by
        # internal producer retries.
        #
        "enable.idempotence":
            True,

        #
        # Allow librdkafka a tiny amount of time
        # to combine messages into larger batches.
        #
        "linger.ms":
            5,

        #
        # Maximum messages librdkafka may place
        # in one producer batch.
        #
        "batch.num.messages":
            10000,
    }
)


producer_stop_event = (
    threading.Event()
)


def delivery_callback(
    error,
    message,
) -> None:
    """
    Called by producer.poll() when Kafka has either
    successfully delivered a message or permanently
    failed to deliver it.

    This runs asynchronously from the HTTP request.
    """

    if error is not None:
        KAFKA_PUBLISH_FAILURES.inc()

        print(
            "Kafka delivery failed "
            f"topic={message.topic()} "
            f"error={error}"
        )


def poll_kafka_producer() -> None:
    """
    Dedicated Kafka event-loop thread.

    Delivery callbacks are served by poll().
    HTTP handlers therefore never need to call
    flush() and block FastAPI's event loop.
    """

    while not producer_stop_event.is_set():

        #
        # Blocks THIS background thread for at most
        # 100 ms. It does not block FastAPI.
        #
        producer.poll(
            0.1
        )

        KAFKA_QUEUE_DEPTH.set(
            len(producer)
        )


# ---------------------------------------------------------
# FastAPI lifecycle
# ---------------------------------------------------------


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    producer_stop_event.clear()

    producer_thread = threading.Thread(
        target=poll_kafka_producer,
        name=(
            "virelai-kafka-producer-poller"
        ),
        daemon=True,
    )

    producer_thread.start()

    print(
        "Kafka producer poller started"
    )

    try:
        yield

    finally:
        print(
            "Stopping Kafka producer poller"
        )

        producer_stop_event.set()

        producer_thread.join(
            timeout=2,
        )

        #
        # Shutdown is the correct place to flush.
        #
        # Give queued messages a chance to reach
        # Kafka before the process exits.
        #
        remaining = producer.flush(
            timeout=10,
        )

        KAFKA_QUEUE_DEPTH.set(
            remaining
        )

        if remaining:
            print(
                f"WARNING: {remaining} Kafka "
                "messages remained queued "
                "during shutdown"
            )
        else:
            print(
                "Kafka producer flushed successfully"
            )


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------


app = FastAPI(
    title=(
        "Virelai Telemetry Ingestion"
    ),
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_methods=[
        "POST",
        "GET",
    ],
    allow_headers=[
        "*",
    ],
)


# ---------------------------------------------------------
# Event schemas
# ---------------------------------------------------------


PlaybackEventType = Literal[
    "play_requested",
    "playback_started",
    "pause",
    "resume",
    "buffer_started",
    "buffer_ended",
    "quality_changed",
    "heartbeat",
    "seek",
    "playback_ended",
    "playback_error",
]


class PlaybackEvent(
    BaseModel
):
    event_id: uuid.UUID

    session_id: uuid.UUID
    video_id: uuid.UUID

    sequence_number: int = Field(
        ge=1,
    )

    event_time: datetime

    event_type: (
        PlaybackEventType
    )

    playback_position_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    buffer_duration_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    bitrate_kbps: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    quality_height: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    startup_time_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    watch_delta_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    seek_from_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    seek_to_ms: (
        int | None
    ) = Field(
        default=None,
        ge=0,
    )

    error_code: (
        str | None
    ) = None

    metadata: (
        dict | None
    ) = None


class EventBatch(
    BaseModel
):
    events: list[
        PlaybackEvent
    ] = Field(
        min_length=1,
        max_length=100,
    )


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------


@app.get(
    "/health"
)
async def health():
    return {
        "status": "ok",
        "kafka_queue_depth":
            len(producer),
    }


# ---------------------------------------------------------
# Telemetry ingestion
# ---------------------------------------------------------


@app.post(
    "/events/batch",
    status_code=(
        status.HTTP_202_ACCEPTED
    ),
)
async def ingest_events(
    batch: EventBatch,
):
    started = (
        time.perf_counter()
    )

    event_count = len(
        batch.events
    )

    BATCH_SIZE.observe(
        event_count
    )


    #
    # Convert validated Pydantic events into
    # confluent-kafka produce_batch dictionaries.
    #
    messages = [
        {
            "key": str(
                event.session_id
            ),

            "value": json.dumps(
                event.model_dump(
                    mode="json"
                )
            ).encode(
                "utf-8"
            ),
        }
        for event in batch.events
    ]


    try:
        #
        # ASYNCHRONOUS:
        #
        # This queues the messages into librdkafka.
        # It does NOT wait for broker acknowledgement.
        #
        queued = (
            producer.produce_batch(
                KAFKA_TOPIC,
                messages,
                on_delivery=(
                    delivery_callback
                ),
            )
        )


        #
        # Normally all messages should enter the
        # local producer queue.
        #
        # A partial enqueue means the producer is
        # saturated and the caller should retry.
        #
        if queued != event_count:
            failed = (
                event_count
                - queued
            )

            KAFKA_PUBLISH_FAILURES.inc(
                failed
            )

            KAFKA_QUEUE_DEPTH.set(
                len(producer)
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                detail=(
                    "Kafka producer queue "
                    "could not accept all events"
                ),
                headers={
                    "Retry-After": "1",
                },
            )


        EVENTS_ACCEPTED.inc(
            queued
        )

        BATCHES_ACCEPTED.inc()


        KAFKA_QUEUE_DEPTH.set(
            len(producer)
        )


        return {
            "accepted": queued,
        }


    except BufferError as exc:
        #
        # librdkafka's local producer queue is full.
        #
        KAFKA_PUBLISH_FAILURES.inc()

        KAFKA_QUEUE_DEPTH.set(
            len(producer)
        )

        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Kafka producer queue is full"
            ),
            headers={
                "Retry-After": "1",
            },
        ) from exc


    finally:
        KAFKA_ENQUEUE_DURATION.observe(
            time.perf_counter()
            - started
        )


# ---------------------------------------------------------
# Prometheus
# ---------------------------------------------------------


@app.get(
    "/metrics",
    include_in_schema=False,
)
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=(
            CONTENT_TYPE_LATEST
        ),
    )