import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import httpx


PROJECT = Path("/workspaces/ibd-live")
BACKEND = PROJECT / "backend"


def load_env():
    path = PROJECT / "webex-session.env"

    if not path.exists():
        raise RuntimeError("webex-session.env not found")

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("export "):
            continue

        key_value = line.replace("export ", "", 1)

        if "=" not in key_value:
            continue

        key, value = key_value.split("=", 1)
        os.environ[key] = value.strip().strip('"').strip("'")


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def call_output_media(bot_id, page_url, settings):
    recall_base = settings.recall_region_base_url.strip().rstrip("/")

    response = httpx.post(
        f"{recall_base}/api/v1/bot/{bot_id}/output_media/",
        headers={
            "Authorization": f"Token {settings.recall_api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json={
            "camera": {
                "kind": "webpage",
                "config": {
                    "url": page_url,
                },
            },
        },
        timeout=30,
    )

    print("Recall status:", response.status_code)

    if response.status_code >= 300:
        print(response.text)
        response.raise_for_status()


def estimate_duration_seconds(audio_path: Path) -> float:
    size = audio_path.stat().st_size
    estimated = (size * 8) / 128000
    return max(3.0, min(60.0, estimated + 2.0))


def main():
    load_env()

    session_id = os.environ["SESSION_ID"]
    bot_id = os.environ["RECALL_BOT_ID"]

    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    from app.core.config import settings

    responses = get_json(
        f"http://127.0.0.1:8000/api/sessions/{session_id}/responses"
    )

    if not responses:
        raise RuntimeError("No responses found. Run webex_wake_watcher.py first.")

    latest_audio = ""

    for item in reversed(responses):
        latest_audio = (
            item.get("audio_file_name")
            or item.get("response_record", {}).get("audio_file_name")
        )

        if latest_audio:
            break

    if not latest_audio:
        raise RuntimeError("No audio_file_name found.")

    audio_path = BACKEND / "generated_audio" / latest_audio

    if not audio_path.exists():
        raise RuntimeError(f"Audio file missing: {audio_path}")

    public_url = settings.public_base_url.strip().rstrip("/")

    play_page = (
        f"{public_url}/api/recall/output-player/{latest_audio}"
        f"?t={int(time.time())}"
    )

    idle_page = (
        f"{public_url}/api/recall/idle-player"
        f"?t={int(time.time())}"
    )

    duration = estimate_duration_seconds(audio_path)

    print("Audio:", latest_audio)
    print("Play page:", play_page)
    print("Estimated duration:", round(duration, 1), "seconds")
    print("Sending Fox speaking page to Webex...")

    call_output_media(bot_id, play_page, settings)

    print("Waiting for speech to finish, then returning to idle...")
    time.sleep(duration)

    call_output_media(bot_id, idle_page, settings)

    print("IBD Live Fox returned to idle/listening state.")


if __name__ == "__main__":
    main()
