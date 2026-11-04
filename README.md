# NOVA: Desktop AI Assistant

A modular, privacy-focused desktop AI assistant built on Electron + React (TypeScript) and a Python FastAPI backend.

## Architecture

- **Desktop Shell:** Electron + React (TypeScript) + Tailwind CSS
- **Core Backend:** Python FastAPI + WebSockets + Uvicorn
- **Machine Learning & Voice (Upcoming Phases):** Custom Intent Classifier, openWakeWord, Faster-Whisper, Piper TTS

## Development Setup

### 1. Backend (Python 3.13)
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r backend/requirements.txt

# Run backend tests
python -m pytest backend/tests

# Run backend development server
python -m backend.app.main
```

### 2. Desktop Frontend (Electron + Vite + React)
```powershell
cd frontend
npm install
npm run dev
```
