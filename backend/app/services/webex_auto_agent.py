import asyncio
import base64
import json
import re
from pathlib import Path

import httpx

from app.core.config import settings


BASE_URL = "http://127.0.0.1:8000"
STATE_FILE = Path("/tmp/ibd-live-webex-auto-processed.json")
AUDIO_DIR = Path(__file__).resolve().parents[2] / "generated_audio"

WAKE_PHRASES = [
    "hey fox",
    "hey folks",
    "hey box",
    "hey fax",
    "hi fox",
    "ok fox",
    "okay fox",
    "fox",
]


def load_processed():
    if not STATE_FILE.exists():
        return set()

    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_processed(processed):
    STATE_FILE.write_text(
        json.dumps(sorted(processed), indent=2),
        encoding="utf-8",
    )


def clean_text(value):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^\w\s]", " ", str(value).lower()),
    ).strip()


def extract_command(text):
    original = str(text or "").strip()

    if not original:
        return None

    cleaned_words = clean_text(original).split()
    original_words = original.split()

    for phrase in WAKE_PHRASES:
        phrase_words = clean_text(phrase).split()

        for index in range(0, len(cleaned_words) - len(phrase_words) + 1):
            if cleaned_words[index:index + len(phrase_words)] == phrase_words:
                command = " ".join(
                    original_words[index + len(phrase_words):]
                ).strip()

                command = re.sub(
                    r"^[\s,.:;!?-]+",
                    "",
                    command,
                ).strip()

                return command or "Summarize what we are discussing."

    return None


async def get_json(client, path):
    response = await client.get(path)
    response.raise_for_status()
    return response.json()


async def post_json(client, path, payload):
    response = await client.post(path, json=payload)
    response.raise_for_status()
    return response.json()


def get_session_id(session):
    return (
        session.get("id")
        or session.get("session_id")
        or session.get("meeting_session_id")
    )


def get_bot_id(session):
    return (
        session.get("recall_bot_id")
        or session.get("bot_id")
        or session.get("recall_id")
    )


def is_webex_session(session):
    source = str(session.get("source", "")).lower()
    return source == "live_webex"


async def list_live_webex_sessions(client):
    sessions_payload = await get_json(client, "/api/sessions")

    if isinstance(sessions_payload, dict):
        sessions = (
            sessions_payload.get("sessions")
            or sessions_payload.get("items")
            or sessions_payload.get("data")
            or []
        )
    else:
        sessions = sessions_payload

    candidates = []

    if isinstance(sessions, list):
        for session in sessions:
            if not isinstance(session, dict):
                continue

            if not is_webex_session(session):
                continue

            session_id = get_session_id(session)
            bot_id = get_bot_id(session)

            if session_id:
                candidates.append(
                    {
                        "session_id": session_id,
                        "recall_bot_id": bot_id,
                    }
                )

    return candidates


async def find_bot_id_from_session(client, session_id, known_bot_id):
    if known_bot_id:
        return known_bot_id

    try:
        session = await get_json(client, f"/api/sessions/{session_id}")
    except Exception:
        return None

    if isinstance(session, dict):
        return get_bot_id(session)

    return None


def audio_file_from_response(response):
    audio_url = response.get("audio_url")

    if audio_url:
        return str(audio_url).rstrip("/").split("/")[-1]

    return (
        response.get("audio_file_name")
        or response.get("response_record", {}).get("audio_file_name")
    )


async def send_audio_to_webex(bot_id, audio_file_name):
    if not bot_id:
        print("[webex-auto] No Recall bot id available; cannot speak into Webex.")
        return False

    audio_path = AUDIO_DIR / audio_file_name

    if not audio_path.exists():
        print("[webex-auto] Audio file missing:", audio_path)
        return False

    audio_bytes = audio_path.read_bytes()
    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    recall_base = settings.recall_region_base_url.strip().rstrip("/")
    url = f"{recall_base}/api/v1/bot/{bot_id}/output_audio/"

    headers = {
        "Authorization": f"Token {settings.recall_api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    payload = {
        "kind": "mp3",
        "b64_data": b64_audio,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            url,
            headers=headers,
            json=payload,
        )

    print("[webex-auto] output_audio status:", response.status_code)

    if response.status_code >= 300:
        print("[webex-auto] output_audio response:", response.text[:800])
        return False

    print("[webex-auto] Sent direct output_audio.")
    return True


async def handle_segment(session_id, bot_id, segment_id, text, processed):
    command = extract_command(text)

    if not command:
        return

    processed.add(segment_id)
    save_processed(processed)

    print("[webex-auto] Wake phrase detected:", text)
    print("[webex-auto] Command:", command)

    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=180,
    ) as client:
        response = await post_json(
            client,
            f"/api/sessions/{session_id}/ask",
            {
                "question": command,
                "speak": True,
            },
        )

    audio_file = audio_file_from_response(response)

    if not audio_file:
        print("[webex-auto] No audio returned.")
        return

    print("[webex-auto] Audio created:", audio_file)

    await send_audio_to_webex(bot_id, audio_file)


async def webex_auto_agent_loop():
    await asyncio.sleep(6)

    print("[webex-auto] Agent loop started.")

    processed = load_processed()

    while True:
        try:
            async with httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=30,
            ) as client:
                sessions = await list_live_webex_sessions(client)

                for session in sessions:
                    session_id = session["session_id"]
                    known_bot_id = session.get("recall_bot_id")

                    bot_id = await find_bot_id_from_session(
                        client,
                        session_id,
                        known_bot_id,
                    )

                    transcript = await get_json(
                        client,
                        f"/api/sessions/{session_id}/transcript",
                    )

                    for segment in transcript.get("segments", []):
                        segment_id = segment.get("id")
                        text = segment.get("text", "")

                        if not segment_id or segment_id in processed:
                            continue

                        command = extract_command(text)

                        if not command:
                            continue

                        await handle_segment(
                            session_id,
                            bot_id,
                            segment_id,
                            text,
                            processed,
                        )

        except Exception as error:
            print("[webex-auto] warning:", error)

        await asyncio.sleep(3)
