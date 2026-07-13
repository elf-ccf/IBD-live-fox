import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AssistantResponse(Base):
    __tablename__ = "assistant_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    meeting_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meeting_sessions.id"),
        nullable=False,
    )

    command_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    command_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    response_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    structured_result: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    audio_file_name: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
