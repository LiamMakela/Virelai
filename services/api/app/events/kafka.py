import json
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer

from app.core.config import settings


producer = Producer(
    {
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "client.id": "virelai-api",
        "acks": "all",
    }
)


def publish_video_uploaded(
    *,
    video_id: uuid.UUID,
    bucket: str,
    object_key: str,
) -> None:
    event = {
        "event_id": str(uuid.uuid4()),
        "event_version": 1,
        "event_type": "video.uploaded",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "video_id": str(video_id),
        "source": {
            "bucket": bucket,
            "key": object_key,
        },
    }

    errors: list[str] = []

    def delivery_callback(err, msg):
        if err is not None:
            errors.append(str(err))

    producer.produce(
        topic=settings.kafka_topic_video_uploaded,
        key=str(video_id),
        value=json.dumps(event).encode("utf-8"),
        on_delivery=delivery_callback,
    )

    remaining = producer.flush(timeout=10)

    if errors:
        raise RuntimeError(
            f"Kafka delivery failed: {errors[0]}"
        )

    if remaining != 0:
        raise RuntimeError(
            f"{remaining} Kafka message(s) were not delivered"
        )