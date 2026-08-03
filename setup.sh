#!/usr/bin/env bash
set -euo pipefail

# Clinical IQ — one-shot setup script
# Usage: bash setup.sh

PYTHON_MIN="3.11"
VENV_DIR="backend/.venv"

# ── helpers ──────────────────────────────────────────────────────────────────

print_step() { echo -e "\n\033[1;34m▶ $*\033[0m"; }
print_ok()   { echo -e "  \033[1;32m✔ $*\033[0m"; }
print_err()  { echo -e "  \033[1;31m✖ $*\033[0m" >&2; }

require_command() {
  if ! command -v "$1" &>/dev/null; then
    print_err "Required command not found: $1"
    echo "    $2"
    exit 1
  fi
}

# ── 1. Check system dependencies ─────────────────────────────────────────────

print_step "Checking system dependencies"

# Find a Python >= 3.11
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 11 ]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  print_err "Python $PYTHON_MIN+ is required but was not found."
  echo "    Install it from https://www.python.org/downloads/ or via your package manager."
  exit 1
fi

print_ok "Python: $($PYTHON --version)"

require_command node "Install Node.js from https://nodejs.org/"
require_command npm  "Install Node.js from https://nodejs.org/"
print_ok "Node: $(node --version)  npm: $(npm --version)"

# ── 2. Backend virtual environment & packages ─────────────────────────────────

print_step "Setting up Python virtual environment at $VENV_DIR"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON" -m venv "$VENV_DIR"
  print_ok "Virtual environment created"
else
  print_ok "Virtual environment already exists"
fi

# Activate (Unix venv uses bin/, Windows venv uses Scripts/)
if [ -f "$VENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  ACTIVATE_HINT="source $VENV_DIR/bin/activate"
elif [ -f "$VENV_DIR/Scripts/activate" ]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/Scripts/activate"
  ACTIVATE_HINT="source $VENV_DIR/Scripts/activate"
else
  print_err "Virtual environment activation script not found."
  exit 1
fi

print_step "Installing Python dependencies"
python -m pip install --upgrade pip --quiet
python -m pip install -r backend/requirements.txt --quiet
print_ok "Python packages installed"

# ── 3. Create backend .env if missing ────────────────────────────────────────

print_step "Backend environment file"

if [ ! -f "backend/.env" ]; then
  cp backend/.env.example backend/.env
  print_ok "Created backend/.env from .env.example"
  echo ""
  echo "  ⚠  Open backend/.env and fill in at minimum:"
  echo "       OPENAI_API_KEY"
  echo "       RECALL_API_KEY"
  echo "       RECALL_REGION_BASE_URL  (e.g. https://us-east-1.recall.ai)"
  echo "       PUBLIC_BASE_URL         (public HTTPS URL; use ngrok for local dev)"
else
  print_ok "backend/.env already exists — skipping"
fi

# ── 4. Frontend packages ──────────────────────────────────────────────────────

print_step "Installing frontend npm packages"
(cd frontend && npm install --silent)
print_ok "Frontend packages installed"

# ── 5. Done ───────────────────────────────────────────────────────────────────

echo ""
echo -e "\033[1;32m✔ Setup complete!\033[0m"
echo ""
echo "  To start the app, open two terminals:"
echo ""
echo "  Terminal 1 — backend:"
echo "    ${ACTIVATE_HINT:-source $VENV_DIR/bin/activate}"
echo "    cd backend"
echo "    uvicorn main:app --reload --port 8000"
echo ""
echo "  Terminal 2 — frontend:"
echo "    cd frontend"
echo "    npm run dev"
echo ""
echo "  Then open http://localhost:5173"
echo ""
echo "  For Recall.ai / live meeting support you also need a public HTTPS tunnel:"
echo "    ngrok http 8000"
echo "  Copy the URL into backend/.env as PUBLIC_BASE_URL and restart the backend."
echo ""
