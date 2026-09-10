import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.playback import PlaybackResponse
from app.services import playback as playback_service


router = APIRouter(
    tags=["playback"],
)


@router.get(
    "/videos/{video_id}/playback",
    response_model=PlaybackResponse,
)
async def get_playback(
    video_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await playback_service.get_playback(
            db=db,
            video_id=video_id,
        )

    except playback_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except playback_service.VideoNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc