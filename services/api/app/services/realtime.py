import asyncio
import json
import time
from collections.abc import AsyncGenerator

from fastapi import Request

from app.core.redis import redis_client
from app.services.analytics import (
    get_platform_realtime_metrics,
)


STREAM_KEY = "realtime:event_stream"
STREAM_BLOCK_MS = 5000
METRICS_INTERVAL_SECONDS = 5


INTEGER_FIELDS = {
    "sequence_number",
    "playback_position_ms",
    "buffer_duration_ms",
    "quality_height",
    "bitrate_kbps",
}


def _normalize_event(
    fields: dict[str, str],
) -> dict:
    event: dict = dict(fields)

    for field in INTEGER_FIELDS:
        value = event.get(field)

        if value is not None:
            try:
                event[field] = int(value)
            except ValueError:
                pass

    metadata = event.get("metadata")

    if metadata is not None:
        try:
            event["metadata"] = json.loads(
                metadata
            )
        except json.JSONDecodeError:
            pass

    return event


def _format_sse(
    *,
    event_type: str,
    data: dict,
    event_id: str | None = None,
) -> str:
    lines: list[str] = []

    if event_id is not None:
        lines.append(
            f"id: {event_id}"
        )

    lines.append(
        f"event: {event_type}"
    )

    payload = json.dumps(
        data,
        separators=(",", ":"),
    )

    lines.append(
        f"data: {payload}"
    )

    return "\n".join(lines) + "\n\n"


async def _initial_stream_id(
    last_event_id: str | None,
) -> str:
    #
    # EventSource automatically sends Last-Event-ID
    # after reconnecting.
    #
    # If this is a brand-new connection, start after
    # the latest existing Redis event so we only show
    # events that occur from this point forward.
    #
    if last_event_id:
        return last_event_id

    latest = await redis_client.xrevrange(
        STREAM_KEY,
        max="+",
        min="-",
        count=1,
    )

    if latest:
        return latest[0][0]

    return "0-0"


async def realtime_event_stream(
    request: Request,
    last_event_id: str | None,
) -> AsyncGenerator[str, None]:
    stream_id = await _initial_stream_id(
        last_event_id
    )

    last_metrics_sent = 0.0

    #
    # Send a metrics snapshot immediately.
    #
    metrics = (
        await get_platform_realtime_metrics()
    )

    yield _format_sse(
        event_type="metrics",
        data=metrics.model_dump(
            mode="json"
        ),
    )

    last_metrics_sent = time.monotonic()

    try:
        while True:
            if await request.is_disconnected():
                break

            #
            # XREAD blocks for up to five seconds.
            #
            # It returns immediately if a newer
            # stream entry appears.
            #
            result = await redis_client.xread(
                {
                    STREAM_KEY: stream_id,
                },
                count=25,
                block=STREAM_BLOCK_MS,
            )

            if await request.is_disconnected():
                break

            if result:
                for _, entries in result:
                    for (
                        entry_id,
                        fields,
                    ) in entries:
                        stream_id = entry_id

                        event = (
                            _normalize_event(
                                fields
                            )
                        )

                        yield _format_sse(
                            event_type=(
                                "playback_event"
                            ),
                            event_id=entry_id,
                            data=event,
                        )

            else:
                #
                # SSE comments are ignored by the
                # browser but keep idle connections
                # alive through intermediaries.
                #
                yield ": keep-alive\n\n"

            now = time.monotonic()

            if (
                now - last_metrics_sent
                >= METRICS_INTERVAL_SECONDS
            ):
                metrics = (
                    await
                    get_platform_realtime_metrics()
                )

                yield _format_sse(
                    event_type="metrics",
                    data=metrics.model_dump(
                        mode="json"
                    ),
                )

                last_metrics_sent = now

    except asyncio.CancelledError:
        #
        # Normal when the browser closes the page
        # or EventSource disconnects.
        #
        raise