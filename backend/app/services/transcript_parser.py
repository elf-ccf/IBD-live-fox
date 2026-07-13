import re
from dataclasses import dataclass


TIMESTAMP_PATTERN = re.compile(
    r"^\s*"
    r"(?:\d{1,2}:)?\d{1,2}:\d{2}"
    r"[\.,]\d{3}"
    r"\s*-->\s*"
    r"(?:\d{1,2}:)?\d{1,2}:\d{2}"
    r"[\.,]\d{3}"
    r".*$"
)

SPEAKER_PATTERN = re.compile(
    r"^\s*"
    r"(?P<speaker>[A-Za-z][A-Za-z0-9 .,'’()_-]{1,80})"
    r":\s*"
    r"(?P<text>.+)"
    r"$"
)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass
class ParsedSegment:
    speaker_name: str
    text: str


def clean_caption_line(line: str) -> str:
    cleaned = HTML_TAG_PATTERN.sub("", line)

    cleaned = cleaned.replace("&nbsp;", " ")
    cleaned = cleaned.replace("&amp;", "&")
    cleaned = cleaned.replace("&lt;", "<")
    cleaned = cleaned.replace("&gt;", ">")

    return " ".join(cleaned.split()).strip()


def should_ignore_line(line: str) -> bool:
    stripped = line.strip()

    if not stripped:
        return True

    if stripped.upper() == "WEBVTT":
        return True

    if stripped.isdigit():
        return True

    if TIMESTAMP_PATTERN.match(stripped):
        return True

    if stripped.startswith("NOTE "):
        return True

    return False


def parse_transcript(
    raw_text: str,
    default_speaker: str = "Unknown speaker",
) -> list[ParsedSegment]:
    if not raw_text.strip():
        return []

    segments: list[ParsedSegment] = []

    current_speaker = default_speaker
    text_buffer: list[str] = []

    def flush_buffer() -> None:
        nonlocal text_buffer

        combined_text = " ".join(text_buffer).strip()

        if combined_text:
            segments.append(
                ParsedSegment(
                    speaker_name=current_speaker,
                    text=combined_text,
                )
            )

        text_buffer = []

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()

        if should_ignore_line(line):
            flush_buffer()
            continue

        cleaned_line = clean_caption_line(line)

        if not cleaned_line:
            continue

        speaker_match = SPEAKER_PATTERN.match(cleaned_line)

        if speaker_match:
            flush_buffer()

            current_speaker = (
                speaker_match.group("speaker").strip()
            )

            spoken_text = (
                speaker_match.group("text").strip()
            )

            if spoken_text:
                text_buffer.append(spoken_text)

            continue

        text_buffer.append(cleaned_line)

    flush_buffer()

    if not segments:
        cleaned_text = clean_caption_line(raw_text)

        if cleaned_text:
            segments.append(
                ParsedSegment(
                    speaker_name=default_speaker,
                    text=cleaned_text,
                )
            )

    return segments
