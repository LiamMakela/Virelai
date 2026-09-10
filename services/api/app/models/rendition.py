import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.models.video import Video


class Rendition(Base):
    __tablename__ = "renditions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "videos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    video_bitrate_kbps: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    audio_bitrate_kbps: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    video_codec: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    audio_codec: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    playlist_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    video: Mapped["Video"] = relationship(
        back_populates="renditions",
    )

    __table_args__ = (
        UniqueConstraint(
            "video_id",
            "height",
            name="uq_renditions_video_height",
        ),
        Index(
            "ix_renditions_video_id",
            "video_id",
        ),
    )