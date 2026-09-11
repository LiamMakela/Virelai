import uuid

from pydantic import BaseModel
from datetime import datetime


class PlaybackSessionRead(BaseModel):
    session_id: uuid.UUID
    video_id: uuid.UUID
    started_at: datetime

class PlaybackResponse(BaseModel):
    video_id: uuid.UUID
    playback_url: str