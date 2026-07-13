from pydantic import BaseModel, Field


class SpeechRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=4000,
        description="Text that OpenAI will convert into speech.",
    )


class SpeechResponse(BaseModel):
    audio_file_name: str
    audio_url: str
    voice: str
    disclosure: str
