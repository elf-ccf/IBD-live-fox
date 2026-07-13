import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.meeting import SessionSource, SessionStatus


class SessionCreate(BaseModel):
    title: str = Field(
        default="Untitled session",
        min_length=1,
        max_length=200,
    )

    source: SessionSource

    deidentified: bool = True

    webex_url: str | None = None


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: SessionSource
    status: SessionStatus
    webex_url: str | None
    recall_bot_id: str | None
    original_file_name: str | None
    deidentified: bool
    created_at: datetime
    updated_at: datetime

class TranscriptPasteRequest(BaseModel):
    transcript: str = Field(
        min_length=1,
        description="Transcript text to store.",
    )

    default_speaker: str = Field(
        default="Unknown speaker",
        min_length=1,
        max_length=200,
    )


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_session_id: uuid.UUID
    sequence_number: int
    speaker_name: str
    text: str
    external_event_id: str | None
    is_ai_speaker: bool
    contains_wake_phrase: bool
    created_at: datetime


class FullTranscriptResponse(BaseModel):
    session_id: uuid.UUID
    title: str
    source: SessionSource
    segment_count: int
    transcript: str
    segments: list[TranscriptSegmentResponse]
