import json
import os
import uuid
from datetime import datetime
from typing import Literal
import time

from fastapi.responses import Response

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)

from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


KAFKA_BOOTSTRAP_SERVERS = os.environ.get(
    "KAFKA_BOOTSTRAP_SERVERS",
    "kafka:19092",
)

KAFKA_TOPIC = os.environ.get(
    "KAFKA_TOPIC_PLAYBACK_EVENTS",
    "playback.events.v1",
)

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


KAFKA_PUBLISH_DURATION = Histogram(
    "virelai_ingest_kafka_publish_duration_seconds",
    "Time required to publish a telemetry batch to Kafka",
    buckets=(
        0.001,
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1,
        2,
        5,
    ),
)

producer = Producer(
    {
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "client.id": "virelai-ingest",
        "acks": "all",
    }
)


app = FastAPI(
    title="Virelai Telemetry Ingestion",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


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


class PlaybackEvent(BaseModel):
    event_id: uuid.UUID

    session_id: uuid.UUID
    video_id: uuid.UUID

    sequence_number: int = Field(
        ge=1,
    )

    event_time: datetime
    event_type: PlaybackEventType

    playback_position_ms: int | None = Field(
        default=None,
        ge=0,
    )

    buffer_duration_ms: int | None = Field(
        default=None,
        ge=0,
    )

    bitrate_kbps: int | None = Field(
        default=None,
        ge=0,
    )

    quality_height: int | None = Field(
        default=None,
        ge=0,
    )

    startup_time_ms: int | None = Field(
    default=None,
    ge=0,
    )

    watch_delta_ms: int | None = Field(
        default=None,
        ge=0,
    )

    seek_from_ms: int | None = Field(
        default=None,
        ge=0,
    )

    seek_to_ms: int | None = Field(
        default=None,
        ge=0,
    )

    error_code: str | None = None
    metadata: dict | None = None


class EventBatch(BaseModel):
    events: list[PlaybackEvent] = Field(
        min_length=1,
        max_length=100,
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }


@app.post(
    "/events/batch",
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_events(
    batch: EventBatch,
):
    started = time.perf_counter()

    event_count = len(
        batch.events
    )

    BATCH_SIZE.observe(
        event_count
    )

    delivery_errors: list[str] = []

    def delivery_callback(
        error,
        message,
    ):
        if error is not None:
            delivery_errors.append(
                str(error)
            )

    try:
        for event in batch.events:
            producer.produce(
                topic=KAFKA_TOPIC,
                key=str(
                    event.session_id
                ),
                value=json.dumps(
                    event.model_dump(
                        mode="json"
                    )
                ).encode(
                    "utf-8"
                ),
                on_delivery=(
                    delivery_callback
                ),
            )

            producer.poll(0)

        remaining = producer.flush(
            timeout=5,
        )

        if (
            delivery_errors
            or remaining
        ):
            KAFKA_PUBLISH_FAILURES.inc()

            raise HTTPException(
                status_code=503,
                detail=(
                    "Unable to publish telemetry"
                ),
            )

        EVENTS_ACCEPTED.inc(
            event_count
        )

        BATCHES_ACCEPTED.inc()

        return {
            "accepted": event_count,
        }

    finally:
        KAFKA_PUBLISH_DURATION.observe(
            time.perf_counter()
            - started
        )

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