import base64
import json
import os
import sys
from pathlib import Path

import httpx


PROJECT = Path("/workspaces/ibd-live")
BACKEND = PROJECT / "backend"


def load_env_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"{path} not found")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line.startswith("export "):
            continue

        key_value = line.replace("export ", "", 1)

        if "=" not in key_value:
            continue

        key, value = key_value.split("=", 1)
        os.environ[key] = value.strip().strip('"').strip("'")


def load_latest_audio_file_name(session_id: str) -> str:
    response = httpx.get(
        f"http://127.0.0.1:8000/api/sessions/{session_id}/responses",
        timeout=30,
    )
    response.raise_for_status()
    responses = response.json()

    if not responses:
        raise RuntimeError(
            "No AI responses found yet. Trigger a command first."
        )

    for item in reversed(responses):
        file_name = (
            item.get("audio_file_name")
            or item.get("response_record", {}).get("audio_file_name")
        )
        if file_name:
            return file_name

    raise RuntimeError("No audio_file_name found in latest responses.")


def main() -> None:
    load_env_file(PROJECT / "webex-session.env")

    session_id = os.environ["SESSION_ID"]
    bot_id = os.environ["RECALL_BOT_ID"]

    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    from app.core.config import settings

    file_name = load_latest_audio_file_name(session_id)
    audio_path = BACKEND / "generated_audio" / file_name

    if not audio_path.exists():
        raise RuntimeError(f"Audio file not found: {audio_path}")

    b64_data = base64.b64encode(audio_path.read_bytes()).decode("utf-8")

    recall_base = settings.recall_region_base_url.strip().rstrip("/")
    output_audio_url = f"{recall_base}/api/v1/bot/{bot_id}/output_audio/"

    payload = {
        "kind": "mp3",
        "b64_data": b64_data,
    }

    headers = {
        "Authorization": f"Token {settings.recall_api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    print("Session:", session_id)
    print("Bot:", bot_id)
    print("Audio:", file_name)
    print("Recall Output Audio URL:", output_audio_url)
    print("Calling Recall Output Audio...")

    response = httpx.post(
        output_audio_url,
        headers=headers,
        json=payload,
        timeout=60,
    )

    print("Recall status:", response.status_code)

    if response.status_code >= 300:
        body_text = response.text
        print(body_text)

        if "automatic_audio_output" in body_text.lower():
            print()
            print(
                "Recall bot config requirement: enable automatic_audio_output "
                "when creating the bot (recording_config.automatic_audio_output=true)."
            )

        response.raise_for_status()

    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        pass

    print("IBD Live Fox direct audio fallback sent.")


if __name__ == "__main__":
    main()
