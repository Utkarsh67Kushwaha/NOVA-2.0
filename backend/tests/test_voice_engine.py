import numpy as np
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.voice.tts import tts_service
from backend.app.voice.vad import VoiceActivityDetector
from backend.app.voice.wake_word import wake_word_detector


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_vad_silence_detection():
    """Verify VAD correctly ignores pure silence."""
    vad = VoiceActivityDetector(energy_threshold=0.015)
    silence = np.zeros(1024, dtype=np.float32)
    assert vad.is_speech_frame(silence) is False
    res = vad.process_chunk(silence)
    assert res is None


def test_vad_speech_detection():
    """Verify VAD triggers on human voice frequency simulation."""
    vad = VoiceActivityDetector(energy_threshold=0.015)
    # 400Hz sine wave (voice fundamental frequency) with moderate amplitude
    t = np.linspace(0, 1024 / 16000, 1024, endpoint=False)
    simulated_voice = 0.1 * np.sin(2 * np.pi * 400 * t).astype(np.float32)
    assert vad.is_speech_frame(simulated_voice) is True


@pytest.mark.parametrize(
    "phrase,expected_detected,expected_clean",
    [
        ("hey nova open chrome", True, "open chrome"),
        ("nova battery kitne percent hai", True, "battery kitne percent hai"),
        ("hello nova play music", True, "play music"),
        ("ok nova find resume in downloads", True, "find resume in downloads"),
        ("open chrome browser please", False, "open chrome browser please"),
        ("play arijit singh songs", False, "play arijit singh songs"),
    ],
)
def test_wake_word_patterns(phrase, expected_detected, expected_clean):
    """Verify wake phrase detection and remainder extraction."""
    detected, clean = wake_word_detector.detect_and_strip(phrase)
    assert detected is expected_detected
    assert clean == expected_clean


def test_tts_service_non_blocking():
    """Verify TTS initiates and stops cleanly without blocking."""
    tts_service.speak("NOVA voice test", blocking=False)
    tts_service.stop()
    assert tts_service.is_speaking is False


def test_voice_status_endpoint(client):
    """Verify GET /api/voice/status returns valid state."""
    response = client.get("/api/voice/status")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "is_muted" in data
    assert "volume_level" in data


def test_voice_interrupt_endpoint(client):
    """Verify POST /api/voice/interrupt stops speech."""
    response = client.post("/api/voice/interrupt")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "interrupted"


def test_voice_toggle_mute_endpoint(client):
    """Verify POST /api/voice/toggle-mute changes mute state."""
    response = client.post("/api/voice/toggle-mute")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "is_muted" in data

    # Toggle back
    response2 = client.post("/api/voice/toggle-mute")
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["is_muted"] != data["is_muted"]
