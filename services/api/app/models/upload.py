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
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UploadStatus(enum.Enum):
    INITIATED = "initiated"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class Upload(Base):
    __tablename__ = "uploads"

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

    object_key: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    multipart_upload_id: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(127),
        nullable=False,
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    part_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    part_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[UploadStatus] = mapped_column(
        Enum(
            UploadStatus,
            name="upload_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        default=UploadStatus.INITIATED,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_uploads_video_status",
            "video_id",
            "status",
        ),
    )