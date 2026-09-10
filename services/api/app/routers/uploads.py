import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.upload import (
    UploadCompleteRequest,
    UploadCreate,
    UploadInitiateResponse,
)
from app.services import uploads as upload_service


router = APIRouter(
    tags=["uploads"],
)


@router.post(
    "/videos/{video_id}/uploads",
    response_model=UploadInitiateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_upload(
    video_id: uuid.UUID,
    data: UploadCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await upload_service.initiate_upload(
            db=db,
            video_id=video_id,
            data=data,
        )

    except upload_service.VideoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        upload_service.InvalidVideoStateError,
        upload_service.InvalidUploadError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post(
    "/uploads/{upload_id}/complete",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def complete_upload(
    upload_id: uuid.UUID,
    data: UploadCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        await upload_service.complete_upload(
            db=db,
            upload_id=upload_id,
            completed_parts=data.parts,
        )

    except (
        upload_service.UploadNotFoundError,
        upload_service.VideoNotFoundError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except (
        upload_service.InvalidUploadStateError,
        upload_service.InvalidUploadError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )