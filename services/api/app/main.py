from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from app.core.metrics import (
    observe_http_request,
)

from app.db.session import get_db
from app.routers.videos import router as videos_router
from app.routers.uploads import router as uploads_router
from app.routers.playback import router as playback_router
from app.routers.analytics import router as analytics_router
from app.routers.realtime import router as realtime_router

app = FastAPI(
    title="Virelai API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.middleware("http")(
    observe_http_request
)

app.include_router(videos_router)
app.include_router(uploads_router)
app.include_router(playback_router)
app.include_router(analytics_router)
app.include_router(realtime_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
    }


@app.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db),
):
    await db.execute(text("SELECT 1"))

    return {
        "status": "ready",
        "database": "ok",
    }

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