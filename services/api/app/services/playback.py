import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.video import Video, VideoStatus
from app.schemas.playback import PlaybackResponse
from app.storage.s3 import generate_media_download_url
from app.storage.s3 import media_public_url


class VideoNotFoundError(Exception):
    pass


class VideoNotReadyError(Exception):
    pass


async def get_playback(
    db: AsyncSession,
    video_id: uuid.UUID,
) -> PlaybackResponse:
    video = await db.get(
        Video,
        video_id,
    )

    if video is None:
        raise VideoNotFoundError(
            f"Video {video_id} does not exist"
        )

    if video.status not in {
        VideoStatus.READY,
        VideoStatus.PUBLISHED,
    }:
        raise VideoNotReadyError(
            f"Video is not ready for playback; current state is {video.status.value}"
        )

    if not video.master_playlist_key:
        raise VideoNotReadyError(
            "Video does not have a master HLS playlist"
        )

    playback_url = media_public_url(
        video.master_playlist_key
    )

    return PlaybackResponse(
        video_id=video.id,
        playback_url=playback_url,
    )