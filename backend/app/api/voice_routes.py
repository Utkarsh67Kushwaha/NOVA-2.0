from typing import Any, Dict, List
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.app.voice.tts import tts_service
from backend.app.voice.voice_manager import voice_manager

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    """Text-to-speech request schema."""

    text: str = Field(..., min_length=1, description="Text to synthesize to speech")


@router.get("/status")
async def get_voice_status() -> Dict[str, Any]:
    """Returns real-time voice subsystem state, hands-free mode, and mic volume."""
    return voice_manager.get_status()


@router.post("/listen-once")
async def listen_once() -> Dict[str, Any]:
    """Records user voice from microphone, runs VAD, STT, intent classification, and speaks response."""
    return voice_manager.record_and_process_once(max_duration_sec=6.0)


@router.post("/hands-free/start")
async def start_hands_free() -> Dict[str, Any]:
    """Starts continuous background 'Hey NOVA' wake-word listening loop."""
    active = voice_manager.start_hands_free()
    return {"status": "ok", "hands_free_active": active}


@router.post("/hands-free/stop")
async def stop_hands_free() -> Dict[str, Any]:
    """Stops continuous background 'Hey NOVA' wake-word listening loop."""
    active = voice_manager.stop_hands_free()
    return {"status": "ok", "hands_free_active": active}


@router.post("/hands-free/toggle")
async def toggle_hands_free() -> Dict[str, Any]:
    """Toggles continuous background 'Hey NOVA' wake-word listening loop."""
    active = voice_manager.toggle_hands_free()
    return {"status": "ok", "hands_free_active": active}


@router.get("/events")
async def get_voice_events() -> Dict[str, Any]:
    """Returns recent voice detection events and the latest trigger."""
    return {
        "status": "ok",
        "latest": voice_manager.last_event,
        "events": voice_manager.event_history[-20:],
    }


@router.post("/speak")
async def synthesize_speech(request: SpeakRequest) -> Dict[str, Any]:
    """Speaks provided text via local TTS (pyttsx3 / Windows SAPI5)."""
    tts_service.speak(request.text, blocking=False)
    return {"status": "speaking", "text": request.text}


@router.post("/interrupt")
async def interrupt_speech() -> Dict[str, Any]:
    """Immediately stops ongoing voice synthesis (interruption support)."""
    voice_manager.interrupt()
    return {"status": "interrupted"}


@router.post("/toggle-mute")
async def toggle_mute() -> Dict[str, Any]:
    """Toggles microphone mute state."""
    is_muted = voice_manager.toggle_mute()
    return {"status": "ok", "is_muted": is_muted}
