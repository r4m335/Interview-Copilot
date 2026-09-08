# Interview Copilot

Real-time programming interview assistant.

Chrome extension captures tab audio → Python backend (Gemini Live ASR / faster-whisper fallback) → LLM generates answers → mobile web client displays on phone.

## Architecture

```
Google Meet / Teams / Zoom (browser tab)
        ↓ tab audio
Chrome Extension (AudioWorklet + VAD)
        ↓ WebSocket (binary PCM 16kHz mono)
FastAPI Backend
        ↓ Gemini 3.5 Transcribe Live (Primary ASR)
        ↓ faster-whisper (Fallback ASR)
        ↓ question detection & heuristic scoring
        ↓ LLM (Ollama → OpenRouter → Groq)
        ↓ WebSocket (JSON)
Phone Browser (/session/<id>)
```

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
# or: pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Extension

```bash
cd extension
npm install
npm run build
# Load dist/ as unpacked extension in chrome://extensions
```

### Mobile

```bash
cd mobile
npm install
npm run dev
```

### Environment

Copy `.env.example` to `.env` and fill in your API keys.

## Development

Run backend on `0.0.0.0:8000` so your phone can reach it over LAN:

```
Laptop: http://192.168.x.x:8000
Phone:  http://192.168.x.x:8000/session/<id>
```

## Project Structure

```
interview-copilot/
├── extension/     # Chrome/Edge Manifest V3 extension
├── backend/       # FastAPI + faster-whisper + LLM
├── mobile/        # React mobile web client
└── .env           # API keys (not committed)
```
