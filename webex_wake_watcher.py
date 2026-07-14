import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE_URL = "http://127.0.0.1:8000"
WAKE_PHRASES = [
    "hey fox",
    "hi fox",
    "okay fox",
    "ok fox",
    "hey box",
    "hey folks",
    "fox",
]

STATE_FILE = Path(".webex-wake-processed.json")


def load_env_file(path="webex-session.env"):
    env_path = Path(path)

    if not env_path.exists():
        raise RuntimeError(
            "webex-session.env not found. Run the Webex setup script first."
        )

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line.startswith("export "):
            continue

        key_value = line.replace("export ", "", 1)

        if "=" not in key_value:
            continue

        key, value = key_value.split("=", 1)
        os.environ[key] = value.strip().strip('"').strip("'")


def request_json(method, url, payload=None):
    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        re.sub(r"[^\w\s]", " ", text.lower()),
    ).strip()


def extract_command(text):
    original = text.strip()
    lowered = clean_text(original)

    for phrase in WAKE_PHRASES:
        phrase_clean = clean_text(phrase)
        index = lowered.find(phrase_clean)

        if index < 0:
            continue

        words_original = original.split()
        words_clean = lowered.split()
        wake_words = phrase_clean.split()

        for word_index in range(0, len(words_clean) - len(wake_words) + 1):
            chunk = " ".join(
                words_clean[word_index:word_index + len(wake_words)]
            )

            if chunk == phrase_clean:
                command = " ".join(
                    words_original[word_index + len(wake_words):]
                ).strip()

                command = re.sub(
                    r"^[\s,.:;!?—-]+",
                    "",
                    command,
                ).strip()

                return command or "Summarize what we are discussing."

    return None


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


def main():
    load_env_file()

    session_id = os.environ.get("SESSION_ID")

    if not session_id:
        raise RuntimeError("SESSION_ID is missing.")

    processed = load_processed()

    print("Webex wake watcher running.")
    print(f"Session: {session_id}")
    print("Listening for: Hey Fox")
    print()

    while True:
        try:
            transcript = request_json(
                "GET",
                f"{BASE_URL}/api/sessions/{session_id}/transcript",
            )

            segments = transcript.get("segments", [])

            for segment in segments:
                segment_id = segment.get("id")
                text = segment.get("text", "")

                if not segment_id or segment_id in processed:
                    continue

                command = extract_command(text)

                if not command:
                    continue

                print(f"Wake phrase detected: {text}")
                print(f"Command: {command}")

                response = request_json(
                    "POST",
                    f"{BASE_URL}/api/sessions/{session_id}/ask",
                    {
                        "question": command,
                        "speak": True,
                    },
                )

                audio_url = response.get("audio_url")

                print("AI response created.")
                print(f"Audio URL: {audio_url}")
                print()

                processed.add(segment_id)
                save_processed(processed)

        except urllib.error.HTTPError as error:
            print(f"HTTP error: {error.code}")
            try:
                print(error.read().decode("utf-8"))
            except Exception:
                pass

        except KeyboardInterrupt:
            print()
            print("Wake watcher stopped.")
            break

        except Exception as error:
            print(f"Watcher warning: {error}")

        time.sleep(3)


if __name__ == "__main__":
    main()
