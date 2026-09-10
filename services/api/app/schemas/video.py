import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.video import VideoStatus


class VideoCreate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
        max_length=5000,
    )


class VideoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID

    title: str
    description: str | None = None

    status: VideoStatus

    duration_ms: int | None = None
    source_width: int | None = None
    source_height: int | None = None
    source_codec: str | None = None

    thumbnail_key: str | None = None
    master_playlist_key: str | None = None

    created_at: datetime
    updated_at: datetime
    published_at: datetime | None = None