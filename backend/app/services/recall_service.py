import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx

from app.core.config import settings
from app.models.meeting import SessionStatus


logger = logging.getLogger(__name__)


class RecallServiceError(RuntimeError):
    pass


def normalized_public_base_url() -> str:
    value = settings.public_base_url.strip().rstrip("/")

    if not value:
        raise RecallServiceError(
            "PUBLIC_BASE_URL is not configured."
        )

    if not value.startswith("https://"):
        raise RecallServiceError(
            "PUBLIC_BASE_URL must use public HTTPS."
        )

    return value


def normalized_recall_base_url() -> str:
    value = (
        settings.recall_region_base_url
        .strip()
        .rstrip("/")
    )

    if not value.startswith("https://"):
        raise RecallServiceError(
            "RECALL_REGION_BASE_URL must use HTTPS."
        )

    return value


def build_recall_webhook_url(
    session_id: UUID,
) -> str:
    public_base_url = (
        normalized_public_base_url()
    )

    return (
        f"{public_base_url}"
        f"/api/recall/events/{session_id}"
    )


async def create_recall_bot(
    meeting_url: str,
    session_id: UUID,
) -> dict[str, Any]:
    if not settings.recall_api_key:
        raise RecallServiceError(
            "RECALL_API_KEY is not configured."
        )

    recall_base_url = (
        normalized_recall_base_url()
    )

    webhook_url = build_recall_webhook_url(
        session_id
    )

    payload = {
        "meeting_url": meeting_url,
        "bot_name": settings.bot_display_name,
        "recording_config": {
            "transcript": {
                "provider": {
                    "recallai_streaming": {}
                },
            },
            "realtime_endpoints": [
                {
                    "type": "webhook",
                    "url": webhook_url,
                    "events": [
                        "transcript.data",
                    ],
                }
            ],
        },
    }

 
    headers = {
        "Authorization": (
            f"Token {settings.recall_api_key.strip()}"
        ),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0)
        ) as client:
            response = await client.post(
                f"{recall_base_url}/api/v1/bot/",
                headers=headers,
                json=payload,
            )

    except httpx.HTTPError as error:
        raise RecallServiceError(
            f"Unable to contact Recall.ai: {error}"
        ) from error

    if response.status_code >= 300:
        safe_message = response.text[:1000]

        logger.error(
            "Recall.ai create-bot failure: "
            "status=%s response=%s",
            response.status_code,
            safe_message,
        )

        raise RecallServiceError(
            "Recall.ai rejected the bot request "
            f"with HTTP {response.status_code}."
        )

    try:
        result = response.json()
    except ValueError as error:
        raise RecallServiceError(
            "Recall.ai returned invalid JSON."
        ) from error

    return result


def get_recall_bot_id(
    response_data: dict[str, Any],
) -> str:
    bot_id = (
        response_data.get("id")
        or response_data.get("bot_id")
    )

    if not bot_id:
        raise RecallServiceError(
            "Recall.ai did not return a bot ID."
        )

    return str(bot_id)


def get_event_type(
    payload: dict[str, Any],
) -> str:
    event_type = (
        payload.get("event")
        or payload.get("type")
        or ""
    )

    return str(event_type).strip()


def nested_data(
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = payload.get("data", payload)

    if not isinstance(data, dict):
        return {}

    inner_data = data.get("data")

    if isinstance(inner_data, dict):
        return inner_data

    return data


def extract_external_event_id(
    payload: dict[str, Any],
) -> str | None:
    data = nested_data(payload)

    possible_id = (
        data.get("id")
        or data.get("segment_id")
        or data.get("transcript_id")
        or payload.get("id")
    )

    if possible_id is None:
        return None

    return str(possible_id)[:300]


def extract_transcript_data(
    payload: dict[str, Any],
) -> tuple[str, str, str | None]:
    data = nested_data(payload)

    participant = data.get("participant")

    if not isinstance(participant, dict):
        participant = {}

    speaker_value = (
        data.get("speaker")
        or data.get("speaker_name")
        or participant.get("name")
        or "Unknown speaker"
    )

    if isinstance(speaker_value, dict):
        speaker_value = (
            speaker_value.get("name")
            or speaker_value.get("display_name")
            or "Unknown speaker"
        )

    speaker_name = (
        str(speaker_value).strip()
        or "Unknown speaker"
    )

    raw_words = data.get("words")

    if isinstance(raw_words, list):
        word_values: list[str] = []

        for item in raw_words:
            if isinstance(item, dict):
                value = (
                    item.get("text")
                    or item.get("word")
                    or ""
                )
            else:
                value = str(item)

            value = str(value).strip()

            if value:
                word_values.append(value)

        transcript_text = " ".join(
            word_values
        ).strip()

    else:
        raw_text = (
            data.get("text")
            or data.get("transcript")
            or data.get("words")
            or ""
        )

        transcript_text = str(
            raw_text
        ).strip()

    external_event_id = (
        extract_external_event_id(payload)
    )

    return (
        speaker_name,
        transcript_text,
        external_event_id,
    )


def extract_recall_status(
    payload: dict[str, Any],
) -> str:
    data = nested_data(payload)

    status_value = data.get("status", "")

    if isinstance(status_value, dict):
        status_value = (
            status_value.get("code")
            or status_value.get("status")
            or status_value.get("state")
            or ""
        )

    return str(status_value).strip().lower()


def map_recall_status(
    recall_status: str,
) -> SessionStatus:
    value = recall_status.lower().strip()

    joining_statuses = {
        "ready",
        "joining_call",
        "in_waiting_room",
        "waiting_room",
        "joining",
    }

    listening_statuses = {
        "in_call_not_recording",
        "in_call_recording",
        "recording_permission_allowed",
        "recording",
        "in_call",
    }

    completed_statuses = {
        "done",
        "call_ended",
        "recording_done",
        "completed",
    }

    failed_statuses = {
        "fatal",
        "failed",
        "error",
        "call_not_found",
        "bot_rejected",
    }

    if value in joining_statuses:
        return SessionStatus.JOINING

    if value in listening_statuses:
        return SessionStatus.LISTENING

    if value in completed_statuses:
        return SessionStatus.COMPLETED

    if value in failed_statuses:
        return SessionStatus.FAILED

    return SessionStatus.CREATED


_webhook_warning_logged = False


def verify_recall_webhook(
    request_body: bytes,
    headers: Mapping[str, str],
) -> bool:
    global _webhook_warning_logged

    if not settings.recall_webhook_secret:
        if not _webhook_warning_logged:
            logger.warning(
                "Recall.ai webhook verification "
                "is disabled in development."
            )

            _webhook_warning_logged = True

        return True

    raise RecallServiceError(
        "RECALL_WEBHOOK_SECRET is configured, "
        "but webhook-signature verification has "
        "not yet been configured from verified "
        "Recall.ai signature documentation."
    )
