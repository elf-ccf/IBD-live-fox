#!/usr/bin/env bash

set -euo pipefail

PROJECT="/workspaces/ibd-live"
BACKEND="$PROJECT/backend"
FRONTEND="$PROJECT/frontend"
ENV_FILE="$BACKEND/.env"
SESSION_ENV="$PROJECT/webex-session.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: Missing backend .env at $ENV_FILE"
  exit 1
fi

echo "=== 1) Backend compile ==="
cd "$BACKEND"
source .venv/bin/activate
python -m compileall -q app main.py
python -c "from main import app; print('Backend imports OK')"

echo
echo "=== 2) Frontend build ==="
cd "$FRONTEND"
npm run build

echo
echo "=== 3) Top-level project check ==="
cd "$PROJECT"
./check_project.sh

echo
echo "=== 4) Detect ngrok URL ==="
PUBLIC_URL="$(python - <<'PY'
import json
import urllib.request

with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as r:
    data = json.load(r)

for t in data.get('tunnels', []):
    url = t.get('public_url', '')
    if url.startswith('https://'):
        print(url)
        break
else:
    raise SystemExit('No HTTPS ngrok tunnel found. Start ngrok: ngrok http 8000')
PY
)"

echo "Using PUBLIC_BASE_URL=$PUBLIC_URL"

echo
echo "=== 5) Update backend/.env ==="
python - <<PY
from pathlib import Path

path = Path(r"$ENV_FILE")
updates = {
    'PUBLIC_BASE_URL': r"$PUBLIC_URL",
    'WAKE_PHRASE': 'hey fox',
    'BOT_DISPLAY_NAME': 'IBD Live Fox',
}

lines = path.read_text(encoding='utf-8').splitlines()
out = []
seen = set()

for line in lines:
    if '=' not in line or line.strip().startswith('#'):
        out.append(line)
        continue
    key, _ = line.split('=', 1)
    if key in updates:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")

path.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('Updated PUBLIC_BASE_URL, WAKE_PHRASE, BOT_DISPLAY_NAME')
PY

echo
echo "=== 6) Restart backend ==="
cd "$BACKEND"
pkill -f "uvicorn main:app" >/dev/null 2>&1 || true
nohup uvicorn main:app --host 0.0.0.0 --port 8000 >/tmp/ibd-live-uvicorn.log 2>&1 &
sleep 5
curl -s http://127.0.0.1:8000/api/health | python -m json.tool

echo
echo "=== 7) Create fresh Webex bot ==="
cd "$PROJECT"
if [[ -z "${WEBEX_URL:-}" ]]; then
  echo "Set WEBEX_URL before running, for example:"
  echo "  export WEBEX_URL='https://...webex.com/meet/... '"
  exit 1
fi

BOT_RESPONSE="$(curl -s -X POST http://127.0.0.1:8000/api/recall/webex \
  -H 'Content-Type: application/json' \
  -d "{\"meeting_url\": \"$WEBEX_URL\", \"title\": \"IBD Live Fox Full Test\", \"deidentified\": true}")"

echo "$BOT_RESPONSE" | python -m json.tool

SESSION_ID="$(echo "$BOT_RESPONSE" | python -c 'import json,sys; print(json.load(sys.stdin)["session_id"])')"
RECALL_BOT_ID="$(echo "$BOT_RESPONSE" | python -c 'import json,sys; print(json.load(sys.stdin)["recall_bot_id"])')"

cat > "$SESSION_ENV" <<ENV
export SESSION_ID="$SESSION_ID"
export RECALL_BOT_ID="$RECALL_BOT_ID"
export PUBLIC_URL="$PUBLIC_URL"
export WEBEX_URL="$WEBEX_URL"
ENV

echo "Wrote $SESSION_ENV"

echo
echo "=== 8) Post manual transcript.data test ==="
EVENT_ID="manual-full-test-$(date +%s)"
PAYLOAD="$(cat <<JSON
{
  "event": "transcript.data",
  "data": {
    "speaker": "Manual Test",
    "text": "Hey Fox, summarize what we are discussing in one sentence.",
    "id": "$EVENT_ID"
  }
}
JSON
)"

curl -s -X POST "http://127.0.0.1:8000/api/recall/events/$SESSION_ID" \
  -H 'Content-Type: application/json' \
  -d "$PAYLOAD" | python -m json.tool

echo
echo "=== 9) Trigger watcher fallback directly once ==="
curl -s -X POST "http://127.0.0.1:8000/api/sessions/$SESSION_ID/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"summarize what we are discussing in one sentence","speak":true}' | python -m json.tool

echo
echo "=== 10) Confirm response + audio file ==="
LATEST_AUDIO="$(curl -s "http://127.0.0.1:8000/api/sessions/$SESSION_ID/responses" | python -c 'import json,sys; d=json.load(sys.stdin); f=""; 
for item in reversed(d):
    f=item.get("audio_file_name") or item.get("response_record",{}).get("audio_file_name")
    if f:
        break
print(f)')"

if [[ -z "$LATEST_AUDIO" ]]; then
  echo "ERROR: No audio file found in responses"
  exit 1
fi

echo "Latest audio: $LATEST_AUDIO"

echo
echo "=== 11) Confirm audio endpoint content type ==="
AUDIO_HEADERS="$(curl -s -i "http://127.0.0.1:8000/api/audio/$LATEST_AUDIO" | head -n 30)"
echo "$AUDIO_HEADERS"
if ! echo "$AUDIO_HEADERS" | grep -qi "content-type: audio/mpeg"; then
  echo "ERROR: Audio endpoint not returning audio/mpeg"
  exit 1
fi

echo
echo "=== 12) Confirm output player has real <audio src=> tag ==="
PLAYER_HTML="$(curl -s "$PUBLIC_URL/api/recall/output-player/$LATEST_AUDIO?t=$(date +%s)")"
if ! echo "$PLAYER_HTML" | grep -q "<audio"; then
  echo "ERROR: Output player missing <audio tag"
  exit 1
fi
if ! echo "$PLAYER_HTML" | grep -q "src=\"$PUBLIC_URL/api/audio/$LATEST_AUDIO\""; then
  echo "ERROR: Output player missing expected audio src"
  exit 1
fi

echo "Output player HTML check passed"

echo
echo "=== 13) Call Recall Output Media ==="
python speak_latest_to_webex.py

echo
echo "=== DONE ==="
echo "Next steps:"
echo "1) Admit IBD Live Fox in Webex if pending"
echo "2) Speak in Webex: Hey Fox, summarize what we are discussing in one sentence"
echo "3) If output media page renders but no speech, run: python speak_latest_direct_audio_to_webex.py"
echo "4) Watch backend logs: tail -f /tmp/ibd-live-uvicorn.log"
