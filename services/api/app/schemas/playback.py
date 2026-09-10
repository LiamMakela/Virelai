import uuid

from pydantic import BaseModel


class PlaybackResponse(BaseModel):
    video_id: uuid.UUID
    playback_url: str