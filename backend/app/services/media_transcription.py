from pathlib import Path

from app.core.config import settings
from app.services.openai_client import get_openai_client


SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpga",
    ".m4a",
    ".wav",
    ".webm",
}

MAX_DIRECT_UPLOAD_SIZE = 25 * 1024 * 1024


def validate_media_file(
    file_path: Path,
) -> None:
    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_MEDIA_EXTENSIONS:
        allowed_formats = ", ".join(
            sorted(SUPPORTED_MEDIA_EXTENSIONS)
        )

        raise ValueError(
            "Unsupported media format. "
            f"Allowed formats: {allowed_formats}"
        )

    if not file_path.exists():
        raise FileNotFoundError(
            f"Media file was not found: {file_path}"
        )

    file_size = file_path.stat().st_size

    if file_size == 0:
        raise ValueError(
            "The uploaded media file is empty."
        )

    if file_size > MAX_DIRECT_UPLOAD_SIZE:
        raise ValueError(
            "The media file exceeds the 25 MB direct "
            "transcription limit. Large-file chunking "
            "will be added in the next stage."
        )


def transcribe_media(
    file_path: Path,
) -> str:
    validate_media_file(file_path)

    client = get_openai_client()

    with file_path.open("rb") as media_file:
        transcription = (
            client.audio.transcriptions.create(
                model=settings.openai_transcription_model,
                file=media_file,
                response_format="text",
            )
        )

    if isinstance(transcription, str):
        transcript_text = transcription
    else:
        transcript_text = getattr(
            transcription,
            "text",
            "",
        )

    transcript_text = transcript_text.strip()

    if not transcript_text:
        raise RuntimeError(
            "OpenAI returned an empty transcript."
        )

    return transcript_text
