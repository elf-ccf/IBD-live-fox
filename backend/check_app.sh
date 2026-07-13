#!/usr/bin/env bash

set -e

echo "Checking Python syntax..."
python -m compileall -q app main.py

echo "Checking FastAPI..."
python -c "from main import app"

echo "Checking LangGraph..."
python -c "from app.workflows.assistant_graph import run_assistant_workflow"

echo "Checking OpenAI Voice..."
python -c "from app.services.speech_service import generate_speech"

echo "Checking Recall.ai..."
python -c "from app.api.recall import router"

echo
echo "All application checks passed."
