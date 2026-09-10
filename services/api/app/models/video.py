import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.rendition import Rendition


class VideoStatus(enum.Enum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    PUBLISHED = "published"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[VideoStatus] = mapped_column(
        Enum(
            VideoStatus,
            name="video_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=VideoStatus.DRAFT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    owner: Mapped["User"] = relationship(
        back_populates="videos",
    )

    renditions: Mapped[list["Rendition"]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "ix_videos_owner_created_at",
            "owner_id",
            "created_at",
        ),
        Index(
            "ix_videos_status_published_at",
            "status",
            "published_at",
        ),
    )

    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    source_width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    source_codec: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    thumbnail_key: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    master_playlist_key: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )


from app.models.user import User  # noqa: E402