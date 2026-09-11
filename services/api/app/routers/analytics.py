import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsTimelinePoint,
    VideoAnalyticsSummary,
)
from app.services import analytics as analytics_service


router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
)


@router.get(
    "/videos/{video_id}/summary",
    response_model=VideoAnalyticsSummary,
)
async def get_video_summary(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await analytics_service.get_video_analytics(
            db=db,
            video_id=video_id,
        )

    except analytics_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/videos/{video_id}/timeline",
    response_model=list[
        AnalyticsTimelinePoint
    ],
)
async def get_video_timeline(
    video_id: uuid.UUID,

    bucket: str = Query(
        default="minute",
        pattern="^(minute|hour|day)$",
    ),

    db: AsyncSession = Depends(get_db),
):
    try:
        return await analytics_service.get_video_timeline(
            db=db,
            video_id=video_id,
            bucket=bucket,
        )

    except analytics_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc