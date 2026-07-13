import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class RecallBotCreateRequest(BaseModel):
    meeting_url: HttpUrl

    title: str = Field(
        default="Live Webex session",
        min_length=1,
        max_length=200,
    )

    deidentified: bool = True


class RecallBotCreateResponse(BaseModel):
    session_id: uuid.UUID
    recall_bot_id: str
    status: str
    meeting_url: str
    bot_name: str
    webhook_url: str


class RecallEventResponse(BaseModel):
    accepted: bool
    event_type: str
    session_id: uuid.UUID
    transcript_segment_id: uuid.UUID | None = None
    duplicate: bool = False


class RecallBotStatusResponse(BaseModel):
    session_id: uuid.UUID
    recall_bot_id: str | None
    session_status: str
    transcript_segment_count: int
    last_transcript_at: datetime | None
