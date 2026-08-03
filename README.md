# Clinical IQ

Clinical IQ is a full-stack AI application for analyzing live online meetings, transcripts, recordings, and PowerPoint presentations through written questions and an AI-generated voice response.

## Architecture

**Live Meeting**
```
Meeting URL (Webex, Teams, Google Meet, etc.)
→ Recall.ai bot joins
→ meeting speech is transcribed
→ transcript webhook reaches FastAPI
→ transcript segments are stored
→ React displays live transcript updates
→ user asks questions through Ask AI
```

**Transcript**
```
Paste text or upload TXT, SRT, or VTT
→ FastAPI parses and stores transcript segments
→ Ask AI uses the transcript as context
```

**Recording**
```
Upload audio or video
→ OpenAI transcribes the recording
→ transcript segments are stored
→ Ask AI uses the transcript as context
```

**Presentation**
```
Upload PPTX (up to 200 MB)
→ FastAPI extracts slide titles, text, and tables
→ each slide is stored as a transcript segment
→ Ask AI uses the presentation as context
```

---

## Quick Setup

```bash
bash setup.sh
```

The script will:
1. Check for Python 3.11+ and Node.js
2. Create a virtual environment at `backend/.venv`
3. Install all Python and npm dependencies
4. Create `backend/.env` from `.env.example` if it doesn't exist

---

## Required Environment Variables

```bash
cd backend
cp .env.example .env
# then edit backend/.env
```

```env
APP_NAME=Clinical IQ
APP_ENV=development
DEBUG=true

# Local development (SQLite)
DATABASE_URL=sqlite:///./ibd_live.db

# For production use PostgreSQL:
# DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME

# OpenAI
OPENAI_API_KEY=REPLACE_WITH_APPROVED_OPENAI_KEY
OPENAI_TEXT_MODEL=gpt-4o-mini
OPENAI_REALTIME_MODEL=gpt-realtime-2.1-mini
OPENAI_REALTIME_VOICE=cedar
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe
OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=cedar

# Recall.ai — required only for Live Meeting
RECALL_API_KEY=REPLACE_WITH_APPROVED_RECALL_KEY
RECALL_REGION_BASE_URL=https://us-east-1.recall.ai   # match your Recall.ai account region

# Public HTTPS URL (Recall.ai webhooks require this)
# For local dev use ngrok: ngrok http 8000
PUBLIC_BASE_URL=https://REPLACE_WITH_NGROK_OR_DEPLOYED_URL

# Frontend address
FRONTEND_ORIGIN=http://localhost:5173

# Application settings
BOT_DISPLAY_NAME=Clinical IQ
DEIDENTIFIED_ONLY=true
```

---

## Manual Run Commands

### Backend

```bash
source backend/.venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
```

### Live Meeting tunnel (local dev only)

```bash
ngrok http 8000
# Copy the https URL into backend/.env as PUBLIC_BASE_URL, then restart the backend.
```

---

## Live Meeting Setup

Live Meeting requires the FastAPI backend to have a **public HTTPS address** so Recall.ai can deliver transcript webhooks. For local testing use ngrok (see above). For production, deploy the backend behind a TLS-terminating reverse proxy.

Find your Recall.ai region by logging in at https://app.recall.ai and checking your account settings, then set `RECALL_REGION_BASE_URL` accordingly (e.g. `https://us-east-1.recall.ai`).

---

## Project Validation

```bash
source backend/.venv/bin/activate
./check_project.sh

cd frontend
npm run build
```
