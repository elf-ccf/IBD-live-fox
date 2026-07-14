#!/usr/bin/env bash

set -e

PROJECT="/workspaces/ibd-live/ibd-live-ai"
BACKEND="$PROJECT/backend"

echo
echo "=== IBD Live Fox Webex live-transcript setup ==="
echo

cd "$BACKEND"

if [ ! -f ".venv/bin/activate" ]; then
  echo "ERROR: backend .venv not found."
  exit 1
fi

source .venv/bin/activate

echo "1. Checking backend..."
python -m compileall -q app main.py
python -c "from main import app; print('FastAPI loaded')"
python -c "from app.api.recall import router; print('Recall API loaded')"
echo "Backend OK."
echo

echo "2. Installing ngrok if needed..."
if ! command -v ngrok >/dev/null 2>&1; then
  curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
    | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null

  echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" \
    | sudo tee /etc/apt/sources.list.d/ngrok.list >/dev/null

  sudo apt update
  sudo apt install -y ngrok
fi

ngrok version
echo

echo "3. Configuring ngrok token..."
if [ -z "${NGROK_AUTHTOKEN:-}" ]; then
  read -rsp "Paste ngrok authtoken: " NGROK_AUTHTOKEN
  echo
fi

if [ -z "$NGROK_AUTHTOKEN" ]; then
  echo "ERROR: ngrok auth token is required."
  exit 1
fi

ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null
echo "ngrok token configured."
echo

echo "4. Getting Webex meeting URL..."
if [ -z "${WEBEX_URL:-}" ]; then
  read -rp "Paste safe Webex meeting URL: " WEBEX_URL
fi

if [ -z "$WEBEX_URL" ]; then
  echo "ERROR: WEBEX_URL is required."
  exit 1
fi

echo
echo "5. Starting backend on port 8000..."
pkill -f "uvicorn main:app" >/dev/null 2>&1 || true
sleep 2

nohup uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/ibd-live-uvicorn.log 2>&1 &

sleep 5

curl -s http://127.0.0.1:8000/api/health \
  | python -m json.tool

echo
echo "6. Starting ngrok tunnel..."
pkill -f "ngrok http 8000" >/dev/null 2>&1 || true
sleep 2

nohup ngrok http 8000 \
  > /tmp/ibd-live-ngrok.log 2>&1 &

sleep 7

PUBLIC_URL=$(
python - <<'PY'
import json
import time
import urllib.request

for _ in range(20):
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:4040/api/tunnels",
            timeout=2,
        ) as response:
            data = json.load(response)

        for tunnel in data.get("tunnels", []):
            url = tunnel.get("public_url", "")
            if url.startswith("https://"):
                print(url)
                raise SystemExit(0)

    except Exception:
        time.sleep(1)

raise SystemExit("Could not read ngrok public HTTPS URL.")
PY
)

echo "ngrok public URL: $PUBLIC_URL"
echo

echo "7. Updating backend .env PUBLIC_BASE_URL and wake phrase..."
python - <<PY
from pathlib import Path

path = Path(".env")
if not path.exists():
    raise RuntimeError(".env not found")

updates = {
    "PUBLIC_BASE_URL": "$PUBLIC_URL",
    "WAKE_PHRASE": "hey fox",
    "BOT_DISPLAY_NAME": "IBD Live Fox",
}

lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
out = []

for line in lines:
    if "=" not in line or line.strip().startswith("#"):
        out.append(line)
        continue

    key, value = line.split("=", 1)

    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text("\\n".join(out) + "\\n", encoding="utf-8")
print("Updated .env")
PY

echo
echo "8. Restarting backend with new PUBLIC_BASE_URL..."
pkill -f "uvicorn main:app" >/dev/null 2>&1 || true
sleep 2

nohup uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  > /tmp/ibd-live-uvicorn.log 2>&1 &

sleep 5

echo "Local health:"
curl -s http://127.0.0.1:8000/api/health \
  | python -m json.tool

echo
echo "Public ngrok health:"
curl -i "$PUBLIC_URL/api/health" | head -n 20

echo
echo "9. Creating fresh Recall.ai Webex bot..."
BOT_RESPONSE=$(
  curl -s -X POST \
    http://127.0.0.1:8000/api/recall/webex \
    -H 'Content-Type: application/json' \
    -d "{
      \"meeting_url\": \"$WEBEX_URL\",
      \"title\": \"Safe Webex Hey Fox Live Test\",
      \"deidentified\": true
    }"
)

echo "$BOT_RESPONSE" | python -m json.tool

SESSION_ID=$(
  echo "$BOT_RESPONSE" |
  python -c 'import json,sys; print(json.load(sys.stdin)["session_id"])'
)

RECALL_BOT_ID=$(
  echo "$BOT_RESPONSE" |
  python -c 'import json,sys; print(json.load(sys.stdin)["recall_bot_id"])'
)

cat > "$PROJECT/webex-session.env" <<ENV
export SESSION_ID="$SESSION_ID"
export RECALL_BOT_ID="$RECALL_BOT_ID"
export PUBLIC_URL="$PUBLIC_URL"
export WEBEX_URL="$WEBEX_URL"
ENV

echo
echo "Saved session variables to:"
echo "$PROJECT/webex-session.env"
echo

echo "=== NEXT STEPS ==="
echo
echo "1. Admit IBD Live Fox in Webex."
echo
echo "2. Watch backend logs:"
echo "   tail -f /tmp/ibd-live-uvicorn.log"
echo
echo "3. In Webex, say:"
echo "   This is a simulated educational case about Crohn disease."
echo
echo "4. Then say:"
echo "   Hey Fox, can you summarize what we are discussing?"
echo
echo "5. In a new terminal, load IDs:"
echo "   cd $PROJECT"
echo "   source webex-session.env"
echo
echo "6. Check transcript:"
echo "   curl -s \"http://127.0.0.1:8000/api/sessions/\$SESSION_ID/transcript\" | python -m json.tool"
echo
echo "7. Check AI responses:"
echo "   curl -s \"http://127.0.0.1:8000/api/sessions/\$SESSION_ID/responses\" | python -m json.tool"
echo
echo "Setup complete."
