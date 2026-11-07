# NOVA 2.0 — System Architecture & Agent Guide

> **Context Optimization**: This file is engineered to give Claude and AI agents complete working knowledge of NOVA 2.0 in ~1,200 tokens.

---

## 1. High-Level Summary
NOVA 2.0 is an ultra-fast, privacy-first desktop AI assistant on Windows. It combines an Electron + React (TypeScript) shell with a local Python FastAPI backend, Faster-Whisper voice transcription, an ML intent engine with Alexa-grade direct rules, Windows hardware & window controls, native Win32 clipboard assistance, and a persistent background TTS worker.

---

## 2. Tech Stack & Key Libraries
- **Backend**: Python 3.13, FastAPI, Uvicorn, Faster-Whisper (greedy decoding, 6 threads), WebRTC-VAD + SoundDevice, pyttsx3 (threaded SAPI5 worker), scikit-learn (TF-IDF + MultinomialNB), PyAutoGUI, ctypes (Windows User32 & Kernel32 APIs).
- **Frontend**: Electron 34, React 18, Vite 6 (`strictPort: 5173`), TypeScript 5.7, Tailwind CSS 3.4, Lucide React icons.
- **Environment**: Windows 11, PowerShell, local `.venv` in root.

---

## 3. Directory Layout & Key Modules
```text
NOVA 2.0/
├── CLAUDE.md                     # Agent briefing & architectural guide (this file)
├── copy_context.ps1              # 1-click PowerShell context copier directly to clipboard
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint, lifespan startup/shutdown, pre-warm
│   │   ├── api/routes.py         # HTTP endpoints: /api/command, /api/voice/*, /api/tools/*
│   │   ├── services/
│   │   │   ├── dispatcher.py     # Centralized DRY action execution layer (routes + voice)
│   │   │   ├── intent_service.py # ML classifier (8 intents) + Rule 0/0.1/0.2/0.5/Media fast-paths
│   │   │   └── gemini_service.py # Conversational AI fallback + offline time/date/jokes handler
│   │   ├── tools/                # Safe tools: LaunchApp, CloseApp, Clipboard, ManageWindow, etc.
│   │   ├── system/               # HardwareController: volume, non-blocking brightness cache (<1ms)
│   │   ├── voice/
│   │   │   ├── vad.py            # Energy + WebRTC VAD (silence_timeout_sec = 0.45s)
│   │   │   ├── stt.py            # Faster-Whisper base (beam_size=1, cpu_threads=6, greedy)
│   │   │   ├── tts.py            # Non-blocking pyttsx3 persistent COM worker + interrupt event
│   │   │   ├── wake_word.py      # Regex wake-word stripper ("hey nova", "bhai nova", "suno")
│   │   │   └── voice_manager.py  # Audio pipeline orchestrator (VAD -> STT -> Dispatcher -> TTS)
│   │   ├── reminders/
│   │   │   ├── time_parser.py    # Natural language time parsing ("in 10 minutes", "at 5pm")
│   │   │   └── scheduler.py      # Background reminder scheduler + Windows notifications
│   │   └── notes/
│   │       ├── note_model.py     # Persistent NoteItem & NoteCreate schemas
│   │       └── note_manager.py   # Thread-safe persistent JSON notes & Notepad exporter
│   ├── data/                     # ML training data, persistent reminders.json & notes.json
│   ├── models/                   # Serialized intent_classifier.pkl & evaluation report
│   └── tests/                    # 204 pytest tests (100% passing)
├── frontend/
│   ├── electron/main.ts          # Electron window manager, IPC handlers, dev server watcher
│   ├── src/
│   │   ├── App.tsx               # Primary dashboard: live mic, tool feed, voice visualizer
│   │   └── services/api.ts       # Frontend HTTP client communicating with backend:8000
│   └── package.json              # Scripts: dev (concurrent Vite + Electron), dev:renderer
└── scripts/
    ├── start_desktop.ps1         # Cleans port 8000, starts backend + Electron window
    └── dump_claude_context.py    # Python CLI exporter for prompt tokens
```

---

## 4. Essential Commands
Run all commands from repository root: `c:\Users\utkar\OneDrive\Desktop\NOVA 2.0`

| Action | PowerShell Command |
| :--- | :--- |
| **Copy Claude Context** | `.\copy_context.ps1` *(instantly puts ~1,200 tokens on clipboard)* |
| **Run Full Desktop App** | `powershell -ExecutionPolicy Bypass -File .\scripts\start_desktop.ps1` |
| **Run Backend Only** | `.\.venv\Scripts\python.exe -m backend.app.main` *(port 8000)* |
| **Run Frontend Web Only** | `npm --prefix frontend run dev:renderer` *(browser on :5173)* |
| **Run Pytest Suite** | `.\.venv\Scripts\python.exe -m pytest backend/tests` *(245 tests)* |
| **Build Frontend** | `npm --prefix frontend run build` |
| **Free Port 8000** | `Get-NetTCPConnection -LocalPort 8000 -EA 0 \| % { Stop-Process -Id $_.OwningProcess -Force }` |

---

## 5. Intent System & Fast-Path Rules
The intent engine in `backend/app/services/intent_service.py` operates in priority order:
1. **Rule 0 (Direct Single-Word Apps)**: `"calc"`, `"notepad"`, `"chrome"`, `"spotify"`, `"vscode"`, `"code"`, `"terminal"`, `"camera"`, `"paint"`, `"settings"` $\rightarrow$ `OPEN_APP`.
2. **Rule 0.1 (Direct Mute/Unmute)**: `"mute"`, `"unmute"` $\rightarrow$ `SYSTEM_CONTROL`.
3. **Rule 0.2 (System Diagnostics & Info)**: `"battery"`, `"time"`, `"date"`, `"weather"` $\rightarrow$ `SYSTEM_INFO` / `AI_CHAT`.
4. **Rule 0.25 (Voice Math & Instant Calculator)**: `"calculate 20% of 1500"`, `"500 divided by 12"`, `"15 into 40"`, `"18% GST on 5000"` $\rightarrow$ `CALCULATE` (safe AST evaluation).
5. **Rule 0.26 (Live Multimodal Screen Vision)**: `"what's on my screen"`, `"screen par kya hai"`, `"look at my screen"`, `"screen dekh kar batao"`, `"explain active window"` $\rightarrow$ `SCREEN_VISION` (multimodal Gemini 2.5 Flash + offline Win32 fallback).
6. **Rule 0.27 (Windows System Maintenance & Quick Folders)**: `"empty recycle bin"`, `"recycle bin saaf karo"`, `"downloads folder kholo"`, `"open documents"`, `"top processes batao"`, `"internet check karo"`, `"all drives status"` $\rightarrow$ `SYSTEM_MAINTENANCE` (empty recycle bin via Win32 `SHEmptyRecycleBinW`, folder explorer launcher, socket ping, process RSS diagnostics).
7. **Rule 0.28 (Hands-Free Voice Keyboard & Desktop Shortcuts)**: `"new tab kholo"`, `"close tab"`, `"copy karo"`, `"paste karo"`, `"select all"`, `"save karo"`, `"undo karo"`, `"refresh karo"`, `"full screen"`, `"zoom in/out"`, `"show desktop"`, `"switch window"` $\rightarrow$ `KEYBOARD_ACTION` (native Win32 `keybd_event` hotkey dispatch).
8. **Rule 0.29 (Deep Multi-Engine Search)**: `"search youtube for <q>"`, `"search github for <q>"`, `"search wikipedia for <q>"`, `"search amazon for <q>"`, `"search stackoverflow for <q>"` $\rightarrow$ `BROWSER_ACTION` (targeted engine URL dispatch).
9. **Rule 0.5 (Apps with Verbs)**: `"{verb} {app}"` / `"{app} {verb}"` $\rightarrow$ `OPEN_APP`.
5. **Rule 0.51 (App Close/Kill)**: `"close {app}"`, `"{app} band karo"`, `"exit {app}"` $\rightarrow$ `CLOSE_APP`.
6. **Rule 0.52 (Window Management)**: `"minimize {app}"`, `"maximize {app}"`, `"focus {app}"` $\rightarrow$ `WINDOW_ACTION`.
7. **Rule 0.53 (Clipboard AI)**: `"read clipboard"`, `"clipboard me kya hai"`, `"summarize clipboard"`, `"clear clipboard"` $\rightarrow$ `CLIPBOARD_ACTION`.
8. **Rule 0.54 (Smart Voice Notes & Scratchpad)**: `"note likho <text>"`, `"take a note <text>"`, `"show my notes"`, `"read latest note"`, `"clear notes"`, `"notes notepad me kholo"` $\rightarrow$ `NOTE_ACTION`.
9. **Rule 0.55 (Document & Code AI)**: `"is document ki summary bana do"`, `"review this code for bugs"` $\rightarrow$ `DOCUMENT_ANALYSIS` / `CODE_ANALYSIS` (routes to Gemini AI Brain).
10. **Rule 0.6 (Screenshot)**: `"screenshot"`, `"sc"`, `"sc le lo"`, `"screen capture"`, `"desktop photo"` $\rightarrow$ `OPEN_APP` (app_name: "screenshot").
11. **Rule Hardware & Media Transport**:
   - Pause/Stop: `"chup"`, `"chup ho"`, `"ruk jao"`, `"pause"`, `"stop"`, `"band karo"`.
   - Play/Resume: `"bhai gaana chala de"`, `"gaana bajao"`, `"play"`, `"resume"` (resumes playback or searches & plays).
   - Track Navigation: `"next"`, `"skip"`, `"previous"`, `"prev"`.
   - Volume & Brightness: `"volume 50%"`, `"awaz badhao"`, `"light kam karo"`.
   - Power & Security: `"lock"`, `"pc lock karo"`, `"sleep"`.
12. **ML Vectorizer & Naive Bayes**: Used for all remaining complex desktop tasks.
13. **Clarification Barrier Removed**: `needs_clarification` is forced `False` so commands execute without stalling.

---

## 6. Voice Engine & Latency Optimization Pipeline
- **Wake Word Detection**: Regex `\b(?:hey\s+|ok\s+|hello\s+|hi\s+|arey\s+|oye\s+|suno\s+)?(?:nova|noah|noba|knower)\b` strips wake words.
- **VAD**: `vad.py` uses `silence_timeout_sec = 0.45` and `energy_threshold = 0.0009`. When user stops talking, capture ends in 450ms.
- **Audio Trimming**: Only the trimmed speech slice (`final_speech_audio`) is passed to STT, never raw multi-second room silence.
- **STT (Faster-Whisper)**: Greedy decoding (`beam_size=1`, `best_of=1`, `cpu_threads=6`, `temperature=0.0`) runs inference in ~1.1s. Pre-warmed at server boot.
- **TTS (pyttsx3)**: Runs on dedicated `NOVA-TTS-Worker` background thread. `tts.speak(..., blocking=False)` ensures API HTTP responses return in `< 5ms`. Real-time interrupt via `_stop_event`.
- **API Latency**: All endpoints (`/health`, `/api/status`, `/api/command`) operate at sub-5ms latency thanks to async non-blocking hardware caching.

---

## 7. Critical Architectural Constraints for AI Agents
1. **Never block the API thread on TTS**: Always pass `blocking=False` in `tts.speak()`.
2. **Never add artificial confirmation/clarification dialogs** for common user intents.
3. **Preserve VAD silence timeout at ~0.45s**: Increasing this re-introduces latency.
4. **Windows Pathing**: Always handle Windows backslashes with raw strings `r"..."` or `Path()`.
5. **Always preserve 245/245 pytest tests**: Run `.\.venv\Scripts\python.exe -m pytest backend/tests` after any backend change.
6. **Port Integrity**: Frontend is locked to port `5173` (`strictPort: true` in `vite.config.ts`), and backend is locked to `8000`. Do not change these ports.
