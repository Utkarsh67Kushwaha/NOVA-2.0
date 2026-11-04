import numpy as np
import pytest
from starlette.testclient import TestClient

from backend.app.main import app
from backend.app.voice.tts import tts_service
from backend.app.voice.vad import VoiceActivityDetector
from backend.app.voice.voice_manager import voice_manager
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
        ("hey noah take screenshot", True, "take screenshot"),
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
    """Verify GET /api/voice/status returns valid state including hands-free."""
    response = client.get("/api/voice/status")
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "is_muted" in data
    assert "volume_level" in data
    assert "hands_free_active" in data


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


def test_hands_free_endpoints(client):
    """Verify Hands-Free wake-word start, toggle, stop and events endpoints."""
    # Start
    res_start = client.post("/api/voice/hands-free/start")
    assert res_start.status_code == 200
    assert res_start.json()["hands_free_active"] is True
    assert voice_manager.is_hands_free is True

    # Check status
    res_status = client.get("/api/voice/status")
    assert res_status.json()["hands_free_active"] is True

    # Events endpoint
    res_events = client.get("/api/voice/events")
    assert res_events.status_code == 200
    assert "events" in res_events.json()

    # Toggle to stop
    res_toggle = client.post("/api/voice/hands-free/toggle")
    assert res_toggle.status_code == 200
    assert res_toggle.json()["hands_free_active"] is False

    # Stop explicitly
    res_stop = client.post("/api/voice/hands-free/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["hands_free_active"] is False



def test_media_controller_operations():
    """Verify hardware media key and audio inspection routines."""
    from backend.app.voice.media_controller import media_controller

    # Test state management
    media_controller._paused_for_voice = True
    assert media_controller.is_paused_for_voice is True
    media_controller.clear_paused_state()
    assert media_controller.is_paused_for_voice is False

    # Test key emission returns boolean
    assert isinstance(media_controller.toggle_playback(), bool)
    assert isinstance(media_controller.pause(), bool)
    assert isinstance(media_controller.resume(), bool)


def test_media_control_safe_tool(client):
    """Verify media_control tool can be executed through API."""
    response = client.post(
        "/api/tools/execute",
        json={"tool_name": "media_control", "args": {"action": "pause"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"]["success"] is True
    assert "paused" in data["result"]["output"].lower()
