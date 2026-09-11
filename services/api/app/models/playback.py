import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PlaybackSession(Base):
    __tablename__ = "playback_sessions"

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

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_playback_sessions_video_started",
            "video_id",
            "started_at",
        ),
    )


class PlaybackEvent(Base):
    __tablename__ = "playback_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "playback_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "videos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    playback_position_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    buffer_duration_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    bitrate_kbps: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    quality_height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    event_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    startup_time_ms: Mapped[int | None] = mapped_column(
    BigInteger,
    nullable=True,
    )

    watch_delta_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    seek_from_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    seek_to_ms: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
            name="uq_playback_event_session_sequence",
        ),
        Index(
            "ix_playback_events_video_time",
            "video_id",
            "event_time",
        ),
        Index(
            "ix_playback_events_type_time",
            "event_type",
            "event_time",
        ),
    )