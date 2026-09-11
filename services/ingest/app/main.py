import json
import os
import uuid
from datetime import datetime
from typing import Literal

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
    delivery_errors: list[str] = []

    def delivery_callback(error, message):
        if error is not None:
            delivery_errors.append(
                str(error)
            )

    for event in batch.events:
        producer.produce(
            topic=KAFKA_TOPIC,
            key=str(event.session_id),
            value=json.dumps(
                event.model_dump(
                    mode="json"
                )
            ).encode("utf-8"),
            on_delivery=delivery_callback,
        )

        producer.poll(0)

    remaining = producer.flush(
        timeout=5,
    )

    if delivery_errors or remaining:
        raise HTTPException(
            status_code=503,
            detail="Unable to publish telemetry",
        )

    return {
        "accepted": len(batch.events),
    }