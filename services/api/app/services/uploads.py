import asyncio
import math
import uuid

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import UploadStatus
from app.models.video import Video, VideoStatus
from app.repositories import uploads as upload_repository
from app.schemas.upload import (
    CompletedPart,
    UploadCreate,
    UploadInitiateResponse,
    UploadPartURL,
)
from app.storage import s3
from app.core.config import settings
from app.events import kafka




PART_SIZE_BYTES = 10 * 1024 * 1024
MAX_PARTS = 10_000

ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
}


class VideoNotFoundError(Exception):
    pass


class InvalidVideoStateError(Exception):
    pass


class UploadNotFoundError(Exception):
    pass


class InvalidUploadStateError(Exception):
    pass


class InvalidUploadError(Exception):
    pass


async def initiate_upload(
    db: AsyncSession,
    video_id: uuid.UUID,
    data: UploadCreate,
) -> UploadInitiateResponse:
    video = await db.get(
        Video,
        video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    if video.status != VideoStatus.DRAFT:
        raise InvalidVideoStateError(
            f"Video must be in draft state, not {video.status.value}"
        )

    extension = Path(data.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise InvalidUploadError(
            "Unsupported video file extension"
        )

    part_count = math.ceil(
        data.size_bytes / PART_SIZE_BYTES
    )

    if part_count > MAX_PARTS:
        raise InvalidUploadError(
            "File is too large for the configured multipart upload size"
        )

    # We never put the user-supplied filename into the storage path.
    object_key = (
        f"users/{video.owner_id}/"
        f"videos/{video.id}/"
        f"source{extension}"
    )

    multipart_upload_id = await asyncio.to_thread(
        s3.create_multipart_upload,
        object_key,
        data.content_type,
    )

    try:
        upload = await upload_repository.create_upload(
            db,
            video_id=video.id,
            object_key=object_key,
            multipart_upload_id=multipart_upload_id,
            original_filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            part_size_bytes=PART_SIZE_BYTES,
            part_count=part_count,
        )

        video.status = VideoStatus.UPLOADING

        await db.commit()

        await db.refresh(upload)

    except Exception:
        await db.rollback()

        await asyncio.to_thread(
            s3.abort_multipart_upload,
            object_key,
            multipart_upload_id,
        )

        raise

    part_urls = [
        UploadPartURL(
            part_number=part_number,
            url=s3.generate_upload_part_url(
                object_key=object_key,
                multipart_upload_id=multipart_upload_id,
                part_number=part_number,
            ),
        )
        for part_number in range(
            1,
            part_count + 1,
        )
    ]

    return UploadInitiateResponse(
        upload_id=upload.id,
        object_key=upload.object_key,
        part_size_bytes=upload.part_size_bytes,
        part_count=upload.part_count,
        parts=part_urls,
    )


async def complete_upload(
    db: AsyncSession,
    upload_id: uuid.UUID,
    completed_parts: list[CompletedPart],
) -> None:
    upload = await upload_repository.get_upload(
        db,
        upload_id,
    )

    if upload is None:
        raise UploadNotFoundError(
            f"Upload {upload_id} does not exist"
        )

    if upload.status != UploadStatus.INITIATED:
        raise InvalidUploadStateError(
            f"Upload is already {upload.status.value}"
        )

    video = await db.get(
        Video,
        upload.video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {upload.video_id} does not exist"
        )

    expected_parts = set(
        range(
            1,
            upload.part_count + 1,
        )
    )

    supplied_parts = {
        part.part_number
        for part in completed_parts
    }

    if supplied_parts != expected_parts:
        raise InvalidUploadError(
            "Completed parts do not match expected upload parts"
        )

    if len(completed_parts) != upload.part_count:
        raise InvalidUploadError(
            "Duplicate part numbers are not allowed"
        )

    s3_parts = [
        {
            "PartNumber": part.part_number,
            "ETag": part.etag,
        }
        for part in sorted(
            completed_parts,
            key=lambda item: item.part_number,
        )
    ]

    await asyncio.to_thread(
        s3.complete_multipart_upload,
        upload.object_key,
        upload.multipart_upload_id,
        s3_parts,
    )

    actual_size = await asyncio.to_thread(
        s3.get_object_size,
        upload.object_key,
    )

    if actual_size != upload.size_bytes:
        raise InvalidUploadError(
            f"Uploaded object size mismatch: "
            f"expected {upload.size_bytes}, got {actual_size}"
        )

    upload.status = UploadStatus.COMPLETED
    upload.completed_at = datetime.now(timezone.utc)

    video.status = VideoStatus.UPLOADED

    await db.commit()

    await asyncio.to_thread(
        kafka.publish_video_uploaded,
        video_id=video.id,
        bucket=settings.s3_bucket_originals,
        object_key=upload.object_key,
    )