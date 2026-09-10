import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.video import VideoCreate, VideoRead
from app.services import videos as video_service


router = APIRouter(
    tags=["videos"],
)


@router.post(
    "/users/{owner_id}/videos",
    response_model=VideoRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_video(
    owner_id: uuid.UUID,
    data: VideoCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await video_service.create_video(
            db=db,
            owner_id=owner_id,
            data=data,
        )

    except video_service.OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/videos/{video_id}",
    response_model=VideoRead,
)
async def get_video(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await video_service.get_video(
            db=db,
            video_id=video_id,
        )

    except video_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/users/{owner_id}/videos",
    response_model=list[VideoRead],
)
async def list_videos(
    owner_id: uuid.UUID,
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await video_service.list_videos(
            db=db,
            owner_id=owner_id,
            limit=limit,
            offset=offset,
        )

    except video_service.OwnerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc