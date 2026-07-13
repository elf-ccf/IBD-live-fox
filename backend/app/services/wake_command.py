import re

from app.core.config import settings


def normalize_spaces(value: str) -> str:
    return " ".join(value.split()).strip()


def contains_wake_phrase(text: str) -> bool:
    wake_phrase = normalize_spaces(
        settings.wake_phrase
    ).lower()

    if not wake_phrase:
        return False

    normalized_text = normalize_spaces(
        text
    ).lower()

    return wake_phrase in normalized_text


def extract_wake_command(
    text: str,
) -> str | None:
    """
    Extract the spoken command appearing after the configured
    wake phrase.

    Example:

    Input:
    "Hey AI, summarize the case."

    Output:
    "summarize the case."
    """

    wake_phrase = normalize_spaces(
        settings.wake_phrase
    )

    if not wake_phrase:
        return None

    pattern = re.compile(
        re.escape(wake_phrase),
        flags=re.IGNORECASE,
    )

    match = pattern.search(text)

    if match is None:
        return None

    command = text[match.end():]

    command = command.lstrip(
        " ,.:;!?-–—"
    )

    command = normalize_spaces(command)

    if not command:
        return None

    return command


def speaker_is_ai(
    speaker_name: str,
) -> bool:
    normalized_speaker = normalize_spaces(
        speaker_name
    ).lower()

    normalized_bot_name = normalize_spaces(
        settings.bot_display_name
    ).lower()

    if not normalized_bot_name:
        return False

    return normalized_bot_name in normalized_speaker
