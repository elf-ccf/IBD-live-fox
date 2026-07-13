import uuid
from pathlib import Path

from app.core.config import settings
from app.services.openai_client import get_openai_client


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[2]
)

GENERATED_AUDIO_DIRECTORY = (
    BACKEND_DIRECTORY / "generated_audio"
)

GENERATED_AUDIO_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


MAX_SPEECH_CHARACTERS = 4000


def generate_speech(
    text: str,
) -> tuple[str, Path]:
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError(
            "Speech text cannot be empty."
        )

    if len(cleaned_text) > MAX_SPEECH_CHARACTERS:
        raise ValueError(
            "Speech text exceeds the "
            "4000-character limit."
        )

    client = get_openai_client()

    file_name = f"{uuid.uuid4()}.mp3"

    output_path = (
        GENERATED_AUDIO_DIRECTORY / file_name
    )

    try:
        with (
            client.audio.speech
            .with_streaming_response
            .create(
                model=settings.openai_tts_model,
                voice=settings.openai_tts_voice,
                input=cleaned_text,
                instructions=(
                    "Speak clearly and professionally for "
                    "a live medical education audience. "
                    "Use a calm, neutral, measured tone. "
                    "Pronounce medical terminology "
                    "carefully. Do not sound overly "
                    "dramatic."
                ),
                response_format="mp3",
            )
        ) as response:
            response.stream_to_file(
                output_path
            )

        if not output_path.exists():
            raise RuntimeError(
                "OpenAI did not create an audio file."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "OpenAI created an empty audio file."
            )

        return file_name, output_path

    except Exception:
        if output_path.exists():
            output_path.unlink()

        raise


def get_audio_path(
    file_name: str,
) -> Path:
    safe_file_name = Path(file_name).name

    if safe_file_name != file_name:
        raise ValueError(
            "Invalid audio filename."
        )

    if not safe_file_name.lower().endswith(".mp3"):
        raise ValueError(
            "Only MP3 audio files are supported."
        )

    return (
        GENERATED_AUDIO_DIRECTORY
        / safe_file_name
    )
