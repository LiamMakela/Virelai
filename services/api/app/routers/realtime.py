from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.realtime import (
    realtime_event_stream,
)


router = APIRouter(
    prefix="/analytics/realtime",
    tags=["realtime"],
)


@router.get("/stream")
async def stream_realtime_events(
    request: Request,
):
    last_event_id = (
        request.headers.get(
            "last-event-id"
        )
    )

    return StreamingResponse(
        realtime_event_stream(
            request=request,
            last_event_id=last_event_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",

            # Useful later when a reverse proxy
            # such as nginx sits in front.
            "X-Accel-Buffering": "no",
        },
    )