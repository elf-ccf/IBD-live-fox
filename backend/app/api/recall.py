import json
import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_database
from app.models import (
    MeetingSession,
    SessionSource,
    SessionStatus,
    TranscriptSegment,
)
from app.schemas.recall import (
    RecallBotCreateRequest,
    RecallBotCreateResponse,
    RecallBotStatusResponse,
    RecallEventResponse,
)
from app.services.command_guard import (
    finish_command,
    try_start_command,
)
from app.services.live_assistant import (
    run_live_assistant_command,
)
from app.services.recall_service import (
    RecallServiceError,
    build_recall_webhook_url,
    create_recall_bot,
    extract_recall_status,
    extract_transcript_data,
    get_event_type,
    get_recall_bot_id,
    map_recall_status,
    verify_recall_webhook,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/recall",
    tags=["Recall.ai"],
)


def get_live_session_or_404(
    session_id: uuid.UUID,
    database: Session,
) -> MeetingSession:
    meeting_session = database.get(
        MeetingSession,
        session_id,
    )

    if meeting_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session was not found.",
        )

    if (
        meeting_session.source
        != SessionSource.LIVE_WEBEX
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The session is not a live Webex session."
            ),
        )

    return meeting_session


@router.post(
    "/webex",
    response_model=RecallBotCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_webex_bot(
    request: RecallBotCreateRequest,
    database: Session = Depends(get_database),
) -> RecallBotCreateResponse:
    if (
        settings.deidentified_only
        and not request.deidentified
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This prototype only accepts simulated "
                "or fully de-identified sessions."
            ),
        )

    if not settings.recall_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RECALL_API_KEY is not configured.",
        )

    if not settings.public_base_url:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PUBLIC_BASE_URL is not configured.",
        )

    meeting_session = MeetingSession(
        title=request.title,
        source=SessionSource.LIVE_WEBEX,
        status=SessionStatus.JOINING,
        webex_url=str(request.meeting_url),
        deidentified=request.deidentified,
    )

    database.add(meeting_session)
    database.commit()
    database.refresh(meeting_session)

    try:
        recall_response = await create_recall_bot(
            meeting_url=str(request.meeting_url),
            session_id=meeting_session.id,
        )

        recall_bot_id = get_recall_bot_id(
            recall_response
        )

        webhook_url = build_recall_webhook_url(
            meeting_session.id
        )

        meeting_session.recall_bot_id = (
            recall_bot_id
        )

        meeting_session.status = (
            SessionStatus.JOINING
        )

        database.commit()
        database.refresh(meeting_session)

        return RecallBotCreateResponse(
            session_id=meeting_session.id,
            recall_bot_id=recall_bot_id,
            status=meeting_session.status.value,
            meeting_url=str(request.meeting_url),
            bot_name=settings.bot_display_name,
            webhook_url=webhook_url,
        )

    except RecallServiceError as error:
        meeting_session.status = (
            SessionStatus.FAILED
        )

        database.commit()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error


@router.post(
    "/events/{session_id}",
    response_model=RecallEventResponse,
)
async def receive_recall_event(
    session_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    database: Session = Depends(get_database),
) -> RecallEventResponse:
    request_body = await request.body()

    try:
        verify_recall_webhook(
            request_body=request_body,
            headers=request.headers,
        )

    except RecallServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    try:
        payload = json.loads(
            request_body.decode("utf-8")
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Recall.ai JSON payload.",
        ) from error

    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Recall.ai payload must be an object.",
        )

    meeting_session = get_live_session_or_404(
        session_id=session_id,
        database=database,
    )

    event_type = get_event_type(payload)

    if event_type == "bot.status_change":
        recall_status = extract_recall_status(
            payload
        )

        mapped_status = map_recall_status(
            recall_status
        )

        if mapped_status != SessionStatus.CREATED:
            meeting_session.status = mapped_status

        database.commit()

        return RecallEventResponse(
            accepted=True,
            event_type=event_type,
            session_id=session_id,
        )

    if event_type != "transcript.data":
        return RecallEventResponse(
            accepted=True,
            event_type=event_type or "unknown",
            session_id=session_id,
        )

    (
        speaker_name,
        transcript_text,
        external_event_id,
    ) = extract_transcript_data(payload)

    if not transcript_text:
        return RecallEventResponse(
            accepted=True,
            event_type=event_type,
            session_id=session_id,
        )

    if external_event_id:
        duplicate_statement = (
            select(TranscriptSegment)
            .where(
                TranscriptSegment.external_event_id
                == external_event_id
            )
        )

        duplicate = database.scalar(
            duplicate_statement
        )

        if duplicate is not None:
            return RecallEventResponse(
                accepted=True,
                event_type=event_type,
                session_id=session_id,
                transcript_segment_id=duplicate.id,
                duplicate=True,
            )

    max_sequence = database.scalar(
        select(
            func.max(
                TranscriptSegment.sequence_number
            )
        ).where(
            TranscriptSegment.meeting_session_id
            == session_id
        )
    )

    next_sequence = (
        int(max_sequence or 0) + 1
    )

    normalized_speaker = (
        speaker_name.lower().strip()
    )

    normalized_bot_name = (
        settings.bot_display_name
        .lower()
        .strip()
    )

    normalized_text = (
        transcript_text.lower()
    )

    wake_phrase = (
        settings.wake_phrase
        .lower()
        .strip()
    )

    transcript_segment = TranscriptSegment(
        meeting_session_id=session_id,
        sequence_number=next_sequence,
        speaker_name=speaker_name,
        text=transcript_text,
        external_event_id=external_event_id,
        is_ai_speaker=(
            bool(normalized_bot_name)
            and normalized_bot_name
            in normalized_speaker
        ),
        contains_wake_phrase=(
            bool(wake_phrase)
            and wake_phrase
            in normalized_text
        ),
    )

    database.add(transcript_segment)

    meeting_session.status = (
        SessionStatus.LISTENING
    )

    database.commit()
    database.refresh(transcript_segment)

    # Wake-phrase processing
    should_trigger = (
        transcript_segment.contains_wake_phrase
        and not transcript_segment.is_ai_speaker
    )

    if should_trigger:
        normalized_text = transcript_text.lower()
        wake_phrase = settings.wake_phrase.lower().strip()
        wake_index = normalized_text.find(wake_phrase)
        command_text = ""
        if wake_index >= 0:
            after_wake = transcript_text[
                wake_index + len(wake_phrase):
            ].strip().lstrip(",. ").strip()
            command_text = after_wake

        if command_text:
            command_started = try_start_command(session_id)

            if command_started:
                try:
                    meeting_session.status = (
                        SessionStatus.PROCESSING
                    )
                    database.commit()

                    background_tasks.add_task(
                        run_live_assistant_command,
                        session_id=session_id,
                        command_text=command_text,
                        command_sequence_number=(
                            transcript_segment.sequence_number
                        ),
                    )

                    logger.info(
                        "Wake command accepted for "
                        "session=%s command=%r",
                        session_id,
                        command_text,
                    )

                except Exception as exc:
                    finish_command(session_id)
                    logger.exception(
                        "Failed to schedule background task "
                        "for session=%s: %s",
                        session_id,
                        exc,
                    )
            else:
                logger.info(
                    "Assistant already busy for session=%s; "
                    "ignoring wake command: %r",
                    session_id,
                    command_text,
                )

    return RecallEventResponse(
        accepted=True,
        event_type=event_type,
        session_id=session_id,
        transcript_segment_id=(
            transcript_segment.id
        ),
    )


@router.get(
    "/sessions/{session_id}/status",
    response_model=RecallBotStatusResponse,
)
def get_recall_session_status(
    session_id: uuid.UUID,
    database: Session = Depends(get_database),
) -> RecallBotStatusResponse:
    meeting_session = get_live_session_or_404(
        session_id=session_id,
        database=database,
    )

    transcript_count = database.scalar(
        select(
            func.count(TranscriptSegment.id)
        ).where(
            TranscriptSegment.meeting_session_id
            == session_id
        )
    )

    last_transcript_at = database.scalar(
        select(
            func.max(TranscriptSegment.created_at)
        ).where(
            TranscriptSegment.meeting_session_id
            == session_id
        )
    )

    return RecallBotStatusResponse(
        session_id=meeting_session.id,
        recall_bot_id=(
            meeting_session.recall_bot_id
        ),
        session_status=(
            meeting_session.status.value
        ),
        transcript_segment_count=int(
            transcript_count or 0
        ),
        last_transcript_at=last_transcript_at,
    )
