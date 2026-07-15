import json
import os
from pathlib import Path
from urllib.parse import quote

import httpx


ENV_PATH = Path("/workspaces/ibd-live/backend/.env")


def load_env_file(path):
    if not path.exists():
        raise RuntimeError(f"Missing env file: {path}")

    values = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line.replace("export ", "", 1)

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def main():
    env = load_env_file(ENV_PATH)

    meeting_url = os.environ.get("WEBEX_URL")
    wss_url = os.environ.get("DEMO_WSS_URL")

    if not meeting_url:
        raise RuntimeError("WEBEX_URL is not set.")

    recall_api_key = env.get("RECALL_API_KEY")
    recall_region_base_url = env.get("RECALL_REGION_BASE_URL", "https://us-west-2.recall.ai")

    if not recall_api_key:
        raise RuntimeError("RECALL_API_KEY missing from backend/.env")

    recall_base = recall_region_base_url.strip().rstrip("/")

    public_base_url = env.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

    if not public_base_url:
        raise RuntimeError("PUBLIC_BASE_URL missing from backend/.env")

    if not wss_url:
        if public_base_url.startswith("https://"):
            wss_url = "wss://" + public_base_url[len("https://") :]
        elif public_base_url.startswith("http://"):
            wss_url = "ws://" + public_base_url[len("http://") :]
        else:
            raise RuntimeError(
                "Could not derive websocket URL. Set DEMO_WSS_URL explicitly."
            )

    wss_url = f"{wss_url.rstrip('/')}/api/webex-realtime/ws"

    output_page = (
        f"{public_base_url}/api/webex-realtime/agent"
        f"?wss={quote(wss_url, safe='')}"
    )

    payload = {
        "meeting_url": meeting_url,
        "bot_name": "IBD Live Fox",
        "output_media": {
            "camera": {
                "kind": "webpage",
                "config": {
                    "url": output_page,
                },
            },
        },
    }

    print("Creating Recall voice-agent demo bot...")
    print("Meeting:", meeting_url)
    print("Output page:", output_page)
    print("Recall base:", recall_base)

    response = httpx.post(
        f"{recall_base}/api/v1/bot/",
        headers={
            "Authorization": f"Token {recall_api_key.strip()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )

    print("Recall status:", response.status_code)

    try:
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print(response.text)

    response.raise_for_status()


if __name__ == "__main__":
    main()
