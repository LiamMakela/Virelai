import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.video import Video
from app.repositories import videos as video_repository
from app.schemas.video import VideoCreate


class OwnerNotFoundError(Exception):
    pass


class VideoNotFoundError(Exception):
    pass


async def create_video(
    db: AsyncSession,
    owner_id: uuid.UUID,
    data: VideoCreate,
) -> Video:
    owner = await db.get(User, owner_id)

    if owner is None:
        raise OwnerNotFoundError(
            f"User {owner_id} does not exist"
        )

    async with db.begin_nested():
        video = await video_repository.create_video(
            db=db,
            owner_id=owner_id,
            data=data,
        )

    await db.commit()
    await db.refresh(video)

    return video


async def get_video(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> Video:
    video = await video_repository.get_video_by_id(
        db=db,
        video_id=video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    return video


async def list_videos(
    db: AsyncSession,
    owner_id: uuid.UUID,
    limit: int,
    offset: int,
) -> Sequence[Video]:
    owner = await db.get(User, owner_id)

    if owner is None:
        raise OwnerNotFoundError(
            f"User {owner_id} does not exist"
        )

    return await video_repository.list_videos_by_owner(
        db=db,
        owner_id=owner_id,
        limit=limit,
        offset=offset,
    )