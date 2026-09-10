import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload import Upload


async def create_upload(
    db: AsyncSession,
    *,
    video_id: uuid.UUID,
    object_key: str,
    multipart_upload_id: str,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    part_size_bytes: int,
    part_count: int,
) -> Upload:
    upload = Upload(
        video_id=video_id,
        object_key=object_key,
        multipart_upload_id=multipart_upload_id,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        part_size_bytes=part_size_bytes,
        part_count=part_count,
    )

    db.add(upload)

    await db.flush()

    return upload


async def get_upload(
    db: AsyncSession,
    upload_id: uuid.UUID,
) -> Upload | None:
    return await db.get(
        Upload,
        upload_id,
    )