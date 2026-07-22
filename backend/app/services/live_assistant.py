import json
import logging
import uuid

from sqlalchemy import func, select

from app.core.config import settings
from app.db.database import SessionLocal
from app.models import (
    AssistantResponse,
    MeetingSession,
    SessionStatus,
    TranscriptSegment,
)
from app.services.command_guard import finish_command
from app.services.speech_service import generate_speech
from app.workflows.assistant_graph import (
    run_assistant_workflow,
)


logger = logging.getLogger(__name__)


def build_case_transcript(
    session_id: uuid.UUID,
    command_sequence_number: int,
) -> str:
    """
    Build case context from transcript segments that occurred
    before the wake command.

    AI-spoken segments and previous wake commands are excluded.
    """

    with SessionLocal() as database:
        statement = (
            select(TranscriptSegment)
            .where(
                TranscriptSegment.meeting_session_id
                == session_id,
                TranscriptSegment.sequence_number
                < command_sequence_number,
                TranscriptSegment.is_ai_speaker.is_(False),
                TranscriptSegment.contains_wake_phrase.is_(False),
            )
            .order_by(
                TranscriptSegment.sequence_number.asc()
            )
        )

        segments = list(
            database.scalars(statement).all()
        )

    return "\n".join(
        f"{segment.speaker_name}: {segment.text}"
        for segment in segments
    ).strip()


def run_live_assistant_command(
    session_id: uuid.UUID,
    command_text: str,
    command_sequence_number: int,
) -> None:
    """
    Run LangGraph and OpenAI Voice after a valid wake command.

    This function is designed to run as a FastAPI background
    task.
    """

    database = SessionLocal()

    try:
        meeting_session = database.get(
            MeetingSession,
            session_id,
        )

        if meeting_session is None:
            logger.error(
                "Live assistant session was not found: %s",
                session_id,
            )
            return

        if (
            settings.deidentified_only
            and not meeting_session.deidentified
        ):
            logger.error(
                "Live assistant blocked non-de-identified "
                "session: %s",
                session_id,
            )

            meeting_session.status = (
                SessionStatus.FAILED
            )

            database.commit()
            return

        meeting_session.status = (
            SessionStatus.PROCESSING
        )

        database.commit()

        transcript = build_case_transcript(
            session_id=session_id,
            command_sequence_number=(
                command_sequence_number
            ),
        )

        if not transcript:
            raise RuntimeError(
                "No case transcript was available before "
                "the wake command."
            )

        workflow_result = run_assistant_workflow(
            session_id=str(session_id),
            question=command_text,
            transcript=transcript,
        )

        # Supports both workflow signatures:
        # AssistantAnswer
        # or tuple[AssistantAnswer, bool]
        if isinstance(workflow_result, tuple):
            answer = workflow_result[0]
            web_search_used = bool(
                workflow_result[1]
            )
        else:
            answer = workflow_result
            web_search_used = False

        structured_result = (
            answer.model_dump()
        )

        structured_result[
            "web_search_used"
        ] = web_search_used

        response_record = AssistantResponse(
            meeting_session_id=session_id,
            command_text=command_text,
            command_type=answer.command_type,
            response_text=answer.answer,
            structured_result=structured_result,
            audio_file_name=None,
        )

        database.add(response_record)
        database.flush()

        fox_external_event_id = (
            f"fox-command:{session_id}:"
            f"{command_sequence_number}"
        )

        existing_fox_segment = database.scalar(
            select(TranscriptSegment).where(
                TranscriptSegment.meeting_session_id
                == session_id,
                TranscriptSegment.external_event_id
                == fox_external_event_id,
            )
        )

        if existing_fox_segment is None:
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

            fox_segment = TranscriptSegment(
                meeting_session_id=session_id,
                sequence_number=(
                    int(max_sequence or 0) + 1
                ),
                speaker_name=settings.bot_display_name,
                text=answer.answer.strip(),
                external_event_id=(
                    fox_external_event_id
                ),
                is_ai_speaker=True,
                contains_wake_phrase=False,
            )

            database.add(fox_segment)

        meeting_session.status = (
            SessionStatus.SPEAKING
        )

        database.commit()
        database.refresh(response_record)

        logger.info(
            "Stored completed Fox response "
            "session=%s response=%s "
            "command_sequence=%s characters=%s",
            session_id,
            response_record.id,
            command_sequence_number,
            len(answer.answer.strip()),
        )

        audio_file_name, _ = generate_speech(
            answer.answer
        )

        response_record.audio_file_name = (
            audio_file_name
        )

        database.commit()

        # Audio has been generated. The next development stage
        # sends this MP3 back into Webex through Recall.ai.
        meeting_session.status = (
            SessionStatus.LISTENING
        )

        database.commit()

        logger.info(
            "Live assistant completed command for "
            "session=%s response=%s audio=%s",
            session_id,
            response_record.id,
            audio_file_name,
        )

    except Exception as error:
        database.rollback()

        logger.exception(
            "Live assistant command failed for "
            "session=%s: %s",
            session_id,
            error,
        )

        try:
            meeting_session = database.get(
                MeetingSession,
                session_id,
            )

            if meeting_session is not None:
                meeting_session.status = (
                    SessionStatus.ERROR
                    if hasattr(SessionStatus, "ERROR")
                    else SessionStatus.FAILED
                )

                database.commit()

        except Exception:
            database.rollback()

    finally:
        finish_command(session_id)
        database.close()
