import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video import Video
from app.schemas.video import VideoCreate


async def create_video(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: VideoCreate,
) -> Video:
    video = Video(
        owner_id=owner_id,
        title=data.title,
        description=data.description,
    )

    db.add(video)

    await db.flush()

    return video


async def get_video_by_id(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> Video | None:
    result = await db.execute(
        select(Video).where(Video.id == video_id)
    )

    return result.scalar_one_or_none()


async def list_videos_by_owner(
    db: AsyncSession,
    owner_id: uuid.UUID,
    limit: int,
    offset: int,
) -> Sequence[Video]:
    result = await db.execute(
        select(Video)
        .where(Video.owner_id == owner_id)
        .order_by(Video.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    return result.scalars().all()