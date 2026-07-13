import uuid
from pathlib import Path
import tempfile

from app.services.media_transcription import (
    MAX_DIRECT_UPLOAD_SIZE,
    SUPPORTED_MEDIA_EXTENSIONS,
    transcribe_media,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_database
from app.models import (
    MeetingSession,
    SessionSource,
    SessionStatus,
    TranscriptSegment,
)
from app.schemas.session import (
    FullTranscriptResponse,
    SessionCreate,
    SessionResponse,
    TranscriptPasteRequest,
    TranscriptSegmentResponse,
)
from app.services.transcript_parser import parse_transcript


router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"],
)


ALLOWED_TRANSCRIPT_EXTENSIONS = {
    ".txt",
    ".srt",
    ".vtt",
}

MAX_TRANSCRIPT_FILE_SIZE = 10 * 1024 * 1024


def get_session_or_404(
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

    return meeting_session


def validate_deidentified(
    meeting_session: MeetingSession,
) -> None:
    if (
        settings.deidentified_only
        and not meeting_session.deidentified
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This prototype only accepts simulated or "
                "fully de-identified educational content."
            ),
        )


def replace_transcript_segments(
    *,
    meeting_session: MeetingSession,
    raw_text: str,
    default_speaker: str,
    database: Session,
) -> list[TranscriptSegment]:
    parsed_segments = parse_transcript(
        raw_text=raw_text,
        default_speaker=default_speaker,
    )

    if not parsed_segments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No usable transcript text was found."
            ),
        )

    database.execute(
        delete(TranscriptSegment).where(
            TranscriptSegment.meeting_session_id
            == meeting_session.id
        )
    )

    stored_segments: list[TranscriptSegment] = []

    wake_phrase = settings.wake_phrase.lower().strip()
    bot_name = settings.bot_display_name.lower().strip()

    for sequence_number, parsed in enumerate(
        parsed_segments,
        start=1,
    ):
        speaker_lower = parsed.speaker_name.lower().strip()
        text_lower = parsed.text.lower()

        segment = TranscriptSegment(
            meeting_session_id=meeting_session.id,
            sequence_number=sequence_number,
            speaker_name=parsed.speaker_name,
            text=parsed.text,
            is_ai_speaker=(
                bot_name
                and bot_name in speaker_lower
            ),
            contains_wake_phrase=(
                wake_phrase
                and wake_phrase in text_lower
            ),
        )

        database.add(segment)
        stored_segments.append(segment)

    meeting_session.status = SessionStatus.COMPLETED

    database.commit()

    for segment in stored_segments:
        database.refresh(segment)

    return stored_segments


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    request: SessionCreate,
    database: Session = Depends(get_database),
) -> SessionResponse:
    if settings.deidentified_only and not request.deidentified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This prototype only accepts sessions marked "
                "as simulated or fully de-identified."
            ),
        )

    if (
        request.source == SessionSource.LIVE_WEBEX
        and not request.webex_url
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "webex_url is required for a live Webex session."
            ),
        )

    meeting_session = MeetingSession(
        title=request.title,
        source=request.source,
        status=SessionStatus.CREATED,
        webex_url=request.webex_url,
        deidentified=request.deidentified,
    )

    database.add(meeting_session)
    database.commit()
    database.refresh(meeting_session)

    return meeting_session


@router.get(
    "",
    response_model=list[SessionResponse],
)
def list_sessions(
    database: Session = Depends(get_database),
) -> list[SessionResponse]:
    statement = (
        select(MeetingSession)
        .order_by(MeetingSession.created_at.desc())
    )

    return list(
        database.scalars(statement).all()
    )


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
)
def get_session(
    session_id: uuid.UUID,
    database: Session = Depends(get_database),
) -> MeetingSession:
    return get_session_or_404(
        session_id=session_id,
        database=database,
    )


@router.post(
    "/{session_id}/transcript/paste",
    response_model=list[TranscriptSegmentResponse],
)
def paste_transcript(
    session_id: uuid.UUID,
    request: TranscriptPasteRequest,
    database: Session = Depends(get_database),
) -> list[TranscriptSegmentResponse]:
    meeting_session = get_session_or_404(
        session_id=session_id,
        database=database,
    )

    validate_deidentified(meeting_session)

    return replace_transcript_segments(
        meeting_session=meeting_session,
        raw_text=request.transcript,
        default_speaker=request.default_speaker,
        database=database,
    )


@router.post(
    "/{session_id}/transcript/upload",
    response_model=list[TranscriptSegmentResponse],
)
async def upload_transcript(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    default_speaker: str = Form("Unknown speaker"),
    database: Session = Depends(get_database),
) -> list[TranscriptSegmentResponse]:
    meeting_session = get_session_or_404(
        session_id=session_id,
        database=database,
    )

    validate_deidentified(meeting_session)

    file_name = file.filename or "transcript.txt"

    extension = Path(file_name).suffix.lower()

    if extension not in ALLOWED_TRANSCRIPT_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported transcript format. "
                "Use TXT, SRT, or VTT."
            ),
        )

    file_content = await file.read()

    if len(file_content) > MAX_TRANSCRIPT_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                "Transcript file exceeds the 10 MB limit."
            ),
        )

    try:
        raw_text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Transcript must use UTF-8 text encoding."
            ),
        ) from error

    return replace_transcript_segments(
        meeting_session=meeting_session,
        raw_text=raw_text,
        default_speaker=default_speaker,
        database=database,
    )


@router.get(
    "/{session_id}/transcript",
    response_model=FullTranscriptResponse,
)
def get_full_transcript(
    session_id: uuid.UUID,
    database: Session = Depends(get_database),
) -> FullTranscriptResponse:
    meeting_session = get_session_or_404(
        session_id=session_id,
        database=database,
    )

    statement = (
        select(TranscriptSegment)
        .where(
            TranscriptSegment.meeting_session_id
            == meeting_session.id
        )
        .order_by(TranscriptSegment.sequence_number.asc())
    )

    segments = list(
        database.scalars(statement).all()
    )

    full_text = "\n".join(
        (
            f"{segment.speaker_name}: "
            f"{segment.text}"
        )
        for segment in segments
    )

    return FullTranscriptResponse(
        session_id=meeting_session.id,
        title=meeting_session.title,
        source=meeting_session.source,
        segment_count=len(segments),
        transcript=full_text,
        segments=segments,
    )


@router.post(
    "/{session_id}/media/upload",
    response_model=FullTranscriptResponse,
)
async def upload_media(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    database: Session = Depends(get_database),
) -> FullTranscriptResponse:
    meeting_session = get_session_or_404(
        session_id=session_id,
        database=database,
    )

    validate_deidentified(meeting_session)

    if meeting_session.source != SessionSource.MEDIA_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This session was not created with "
                "source=media_upload."
            ),
        )

    original_file_name = (
        file.filename or "meeting-recording"
    )

    extension = (
        Path(original_file_name)
        .suffix
        .lower()
    )

    if extension not in SUPPORTED_MEDIA_EXTENSIONS:
        allowed_formats = ", ".join(
            sorted(SUPPORTED_MEDIA_EXTENSIONS)
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported media format. "
                f"Allowed formats: {allowed_formats}"
            ),
        )

    meeting_session.status = SessionStatus.PROCESSING
    meeting_session.original_file_name = (
        original_file_name
    )

    database.commit()

    temporary_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(
                temporary_file.name
            )

            total_size = 0

            while chunk := await file.read(
                1024 * 1024
            ):
                total_size += len(chunk)

                if total_size > MAX_DIRECT_UPLOAD_SIZE:
                    raise HTTPException(
                        status_code=(
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                        ),
                        detail=(
                            "The media file exceeds the "
                            "25 MB direct-upload limit."
                        ),
                    )

                temporary_file.write(chunk)

        transcript_text = transcribe_media(
            temporary_path,
        )

        stored_segments = replace_transcript_segments(
            meeting_session=meeting_session,
            raw_text=transcript_text,
            default_speaker="Meeting audio",
            database=database,
        )

        full_text = "\n".join(
            (
                f"{segment.speaker_name}: "
                f"{segment.text}"
            )
            for segment in stored_segments
        )

        return FullTranscriptResponse(
            session_id=meeting_session.id,
            title=meeting_session.title,
            source=meeting_session.source,
            segment_count=len(stored_segments),
            transcript=full_text,
            segments=stored_segments,
        )

    except HTTPException:
        meeting_session.status = SessionStatus.FAILED
        database.commit()

        raise

    except Exception as error:
        meeting_session.status = SessionStatus.FAILED
        database.commit()

        print(
            "Media transcription error:",
            repr(error),
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Media transcription failed. "
                "Check the backend terminal for details."
            ),
        ) from error

    finally:
        await file.close()

        if (
            temporary_path is not None
            and temporary_path.exists()
        ):
            temporary_path.unlink()
@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_session(
    session_id: uuid.UUID,
    database: Session = Depends(get_database),
) -> None:
    meeting_session = get_session_or_404(
        session_id=session_id,
        database=database,
    )

    database.delete(meeting_session)
    database.commit()
