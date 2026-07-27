IBD Live Fox
IBD Live Fox is a full-stack AI application for analyzing live meetings, transcripts, recordings, and PowerPoint presentations through written questions and browser-based voice interaction.

Architecture
Live meeting
Meeting URL
→ Recall.ai bot joins
→ meeting speech is transcribed
→ transcript webhook reaches FastAPI
→ transcript segments are stored
→ React displays live transcript updates
→ user asks questions through Ask AI or Ask Fox

transcript
Paste text or upload TXT, SRT, or VTT
→ FastAPI parses and stores transcript segments
→ Ask AI and Ask Fox use the transcript as context

Recording
Upload audio or video
→ OpenAI transcribes the recording
→ transcript segments are stored
→ Ask AI and Ask Fox use the transcript as context

Presentation
Upload PPTX
→ FastAPI extracts slide titles, text, and tables
→ each slide is stored as a transcript segment
→ Ask AI and Ask Fox use the presentation as context


Required Environment Variables
cd backend
cp .env.example .env


APP_NAME=IBD Live Fox
APP_ENV=development
DEBUG=true

# Local development only
DATABASE_URL=sqlite:///./ibd_live.db

# For a shared or deployed environment, use PostgreSQL instead:
# DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME

# OpenAI
OPENAI_API_KEY=REPLACE_WITH_APPROVED_OPENAI_KEY
OPENAI_TEXT_MODEL=gpt-4o-mini
OPENAI_REALTIME_MODEL=gpt-realtime-2.1-mini
OPENAI_REALTIME_VOICE=cedar
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=cedar

# Recall.ai, required only for Live Meeting
RECALL_API_KEY=REPLACE_WITH_APPROVED_RECALL_KEY
RECALL_REGION_BASE_URL=https://us-west-2.recall.ai

# Local value for Transcript, Recording, and Presentation testing
PUBLIC_BASE_URL=http://127.0.0.1:8000

# Frontend address
FRONTEND_ORIGIN=http://localhost:5173

# Application settings
WAKE_PHRASE=hey fox
BOT_DISPLAY_NAME=IBD Live Fox
DEIDENTIFIED_ONLY=true

Run commands 
BACKEND

cd backend

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

cp .env.example .env

cd backend
source .venv/bin/activate

python -m compileall -q app main.py
python -c "from main import app; print('Backend OK')"

python -m uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --log-level info

  FRONTEND

  cd frontend

npm install
npm run build

npm run dev -- --host 0.0.0.0 --port 5173

Live Meeting Setup

Live Meeting requires the FastAPI backend to have a public HTTPS address so Recall.ai can deliver transcript webhooks.

For local testing, run ngrok in another terminal:


ngrok http 8000

PUBLIC_BASE_URL=https://REPLACE_WITH_NGROK_DOMAIN.ngrok-free.dev

PUBLIC_BASE_URL=https://YOUR_DEPLOYED_BACKEND_DOMAIN

Project Validation

cd /path/to/IBD-live-fox

source backend/.venv/bin/activate

./check_project.sh
git diff --check


cd frontend
npm run build