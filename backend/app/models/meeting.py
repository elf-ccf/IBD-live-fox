import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class SessionSource(str, enum.Enum):
    LIVE_WEBEX = "live_webex"
    TRANSCRIPT_UPLOAD = "transcript_upload"
    MEDIA_UPLOAD = "media_upload"


class SessionStatus(str, enum.Enum):
    CREATED = "created"
    JOINING = "joining"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    FAILED = "failed"


class MeetingSession(Base):
    __tablename__ = "meeting_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        default="Untitled session",
        nullable=False,
    )

    source: Mapped[SessionSource] = mapped_column(
        Enum(
            SessionSource,
            name="session_source",
        ),
        nullable=False,
    )

    status: Mapped[SessionStatus] = mapped_column(
        Enum(
            SessionStatus,
            name="session_status",
        ),
        default=SessionStatus.CREATED,
        nullable=False,
    )

    webex_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    recall_bot_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    original_file_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )
    deidentified: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
