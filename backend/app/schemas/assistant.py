import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class LikelihoodEnum(str, Enum):
    HIGHER = "Higher"
    MODERATE = "Moderate"
    LOWER = "Lower"


class DifferentialItem(BaseModel):
    rank: int = Field(
        gt=0,
        description="Rank of the differential possibility.",
    )

    condition: str = Field(
        description="Name of the possible condition.",
    )

    likelihood: LikelihoodEnum = Field(
        description="Relative likelihood based on the transcript.",
    )

    rationale: str = Field(
        description="Educational reasoning for the possibility.",
    )


class WebSource(BaseModel):
    title: str
    url: str
    organization: str | None = None
    published_date: str | None = None


class AssistantAnswer(BaseModel):
    command_type: str = Field(
        description="Type of command processed.",
    )

    case_summary: str = Field(
        description="Brief summary of the case.",
    )

    key_findings: list[str] = Field(
        default_factory=list,
        description="Clinical findings present in the transcript.",
    )

    differential: list[DifferentialItem] = Field(
        default_factory=list,
        description="Educational differential possibilities.",
    )

    missing_information: list[str] = Field(
        default_factory=list,
        description="Important information missing from the transcript.",
    )

    answer: str = Field(
        description="Detailed answer to the question.",
    )

    audience_script: str = Field(
        description="Concise script appropriate for spoken delivery.",
    )

    limitations: str = Field(
        description="Limitations and educational disclaimer.",
    )

    sources: list[WebSource] = Field(
        default_factory=list,
        description="Web sources used in the answer.",
    )


class AssistantQuestionRequest(BaseModel):
    question: str = Field(
        min_length=2,
        max_length=2000,
    )

    speak: bool = False


class AssistantResponseRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_session_id: uuid.UUID
    command_text: str
    command_type: str
    response_text: str
    structured_result: dict | None
    audio_file_name: str | None
    created_at: datetime


class AssistantAnswerResponse(BaseModel):
    response_record: AssistantResponseRecord
    answer: AssistantAnswer
    web_search_used: bool = False
    audio_url: str | None = None
    voice: str | None = None
    disclosure: str | None = None
    voice_error: str | None = None
