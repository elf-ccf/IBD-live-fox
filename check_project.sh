#!/usr/bin/env bash

set -e

PROJECT="/workspaces/ibd-live/ibd-live-ai"

echo
echo "=== Checking backend ==="

cd "$PROJECT/backend"

if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: Backend virtual environment not found."
    exit 1
fi

source .venv/bin/activate

python -m compileall -q app main.py
python -c "from main import app; print('FastAPI loaded')"
python -c "from app.workflows.assistant_graph import run_assistant_workflow; print('LangGraph loaded')"
python -c "from app.services.speech_service import generate_speech; print('OpenAI Voice loaded')"

if [ -f "app/api/recall.py" ]; then
    python -c "from app.api.recall import router; print('Recall.ai API loaded')"
fi

echo "Backend passed."

echo
echo "=== Checking frontend ==="

cd "$PROJECT/frontend"

if [ ! -f "package.json" ]; then
    echo "ERROR: frontend/package.json was not found."
    exit 1
fi

npm install
npm run build

echo
echo "Frontend passed."
echo "All project checks passed."
