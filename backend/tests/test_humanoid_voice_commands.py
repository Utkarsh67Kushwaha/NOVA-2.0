"""
Comprehensive Humanoid Voice & Natural Command Integration Tests
Verifies that natural, conversational, and Alexa-grade commands in English, Hindi, and Hinglish
execute smoothly across every single NOVA 2.0 feature.
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.intent_service import intent_service
from backend.app.voice.wake_word import wake_word_detector

client = TestClient(app)


# 1. Humanoid Wake Word Variations
@pytest.mark.parametrize(
    "phrase,expected_detected,expected_clean",
    [
        ("hey nova open chrome", True, "open chrome"),
        ("ok nova find resume", True, "find resume"),
        ("hello nova play music", True, "play music"),
        ("hi nova mute audio", True, "mute audio"),
        ("bhai nova notepad kholo", True, "notepad kholo"),
        ("yaar nova volume badhao", True, "volume badhao"),
        ("suno nova battery kitni hai", True, "battery kitni hai"),
        ("arey nova screenshot le lo", True, "screenshot le lo"),
        ("oye nova gana roko", True, "gana roko"),
        ("open chrome browser please", False, "open chrome browser please"),
    ],
)
def test_humanoid_wake_words(phrase, expected_detected, expected_clean):
    detected, clean = wake_word_detector.detect_and_strip(phrase)
    assert detected is expected_detected
    assert clean == expected_clean


# 2. Humanoid App Launching Commands
@pytest.mark.parametrize(
    "cmd,expected_app",
    [
        ("notepad kholo", "notepad"),
        ("calculator open karo", "calculator"),
        ("calc kholo", "calculator"),
        ("chrome open karo", "chrome"),
        ("spotify chalao", "spotify"),
        ("vscode kholo", "vscode"),
        ("terminal open karo", "cmd"),
        ("telegram kholo", "telegram"),
        ("discord open karo", "discord"),
        ("whatsapp chalao", "whatsapp"),
        ("brave kholo", "brave"),
        ("edge open karo", "edge"),
        ("task manager kholo", "task manager"),
        ("paint open karo", "paint"),
        ("camera kholo", "camera"),
        ("settings open karo", "settings"),
        ("word open karo", "word"),
        ("excel open karo", "excel"),
        ("vlc kholo", "vlc"),
        # Colloquial with fillers
        ("bhai telegram open kar de", "telegram"),
        ("zara notepad khol do", "notepad"),
        ("ek kaam kar spotify chalao", "spotify"),
    ],
)
def test_humanoid_app_launch(cmd, expected_app):
    res = intent_service.predict(cmd)
    assert res["intent"] == "OPEN_APP", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("app_name") == expected_app


# 3. Humanoid App Close Commands
@pytest.mark.parametrize(
    "cmd,expected_app",
    [
        ("close notepad", "notepad"),
        ("notepad band karo", "notepad"),
        ("exit chrome", "chrome"),
        ("chrome band kar do", "chrome"),
        ("quit spotify", "spotify"),
        ("spotify band karo", "spotify"),
        ("close telegram", "telegram"),
        ("discord band karo", "discord"),
        ("whatsapp hatao", "whatsapp"),
        ("close task manager", "task manager"),
    ],
)
def test_humanoid_app_close(cmd, expected_app):
    res = intent_service.predict(cmd)
    assert res["intent"] == "CLOSE_APP", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("app_name") == expected_app


# 4. Humanoid Hardware Volume & Mute Controls
@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("mute", "mute"),
        ("unmute", "unmute"),
        ("mute karo", "mute"),
        ("aawaz band karo", "mute"),
        ("volume mute kar do", "mute"),
        ("aawaz badhao", "adjust_volume"),
        ("volume increase karo", "adjust_volume"),
        ("bhai aawaz badha do", "adjust_volume"),
        ("volume kam karo", "adjust_volume"),
        ("aawaz dheemi karo", "adjust_volume"),
        ("sound kam karo", "adjust_volume"),
        ("volume 50 percent karo", "set_volume"),
        ("sound 70 pe set karo", "set_volume"),
    ],
)
def test_humanoid_volume_controls(cmd, expected_action):
    res = intent_service.predict(cmd)
    assert res["intent"] == "SYSTEM_CONTROL", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


# 5. Humanoid Display Brightness Controls
@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("brightness badhao", "adjust_brightness"),
        ("screen light badhao", "adjust_brightness"),
        ("roshni badha do", "adjust_brightness"),
        ("brightness kam karo", "adjust_brightness"),
        ("screen light kam karo", "adjust_brightness"),
        ("brightness 80 percent karo", "set_brightness"),
        ("screen light 60 pe karo", "set_brightness"),
    ],
)
def test_humanoid_brightness_controls(cmd, expected_action):
    res = intent_service.predict(cmd)
    assert res["intent"] == "SYSTEM_CONTROL", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


# 6. Humanoid Power & Lock Controls
@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("lock", "lock_workstation"),
        ("pc lock karo", "lock_workstation"),
        ("lock my pc", "lock_workstation"),
        ("computer lock karo", "lock_workstation"),
        ("screen lock karo", "lock_workstation"),
        ("sleep mode", "sleep"),
        ("pc sleep karo", "sleep"),
    ],
)
def test_humanoid_power_controls(cmd, expected_action):
    res = intent_service.predict(cmd)
    assert res["intent"] == "SYSTEM_CONTROL", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


# 7. Humanoid Media Playback Controls
@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("gana roko", "pause"),
        ("pause music", "pause"),
        ("stop the song", "pause"),
        ("chup ho jao", "pause"),
        ("ruk jao", "pause"),
        ("music band karo", "pause"),
        ("play music", "resume"),
        ("resume song", "resume"),
        ("wapas bajao", "resume"),
        ("next song", "next"),
        ("agla gana", "next"),
        ("skip track", "next"),
        ("previous song", "previous"),
        ("pichla gana", "previous"),
    ],
)
def test_humanoid_media_controls(cmd, expected_action):
    res = intent_service.predict(cmd)
    assert res["intent"] == "PLAY_MUSIC", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


# 8. Humanoid Song Search & Play
@pytest.mark.parametrize(
    "cmd,expected_track",
    [
        ("play kesariya song", "kesariya"),
        ("arijit singh ka gana bajao", "arijit singh"),
        ("believer song chalao", "believer"),
    ],
)
def test_humanoid_song_play(cmd, expected_track):
    res = intent_service.predict(cmd)
    assert res["intent"] == "PLAY_MUSIC"
    assert res["entities"].get("action") == "play"
    assert expected_track in res["entities"].get("track_or_query", "").lower()


# 9. Humanoid System Info & Battery
@pytest.mark.parametrize(
    "cmd,expected_metric",
    [
        ("battery kitni hai", "battery"),
        ("battery percent batao", "battery"),
        ("charge kitna hai", "battery"),
        ("ram usage", "memory"),
        ("cpu usage", "cpu"),
        ("disk space", "disk"),
    ],
)
def test_humanoid_system_info(cmd, expected_metric):
    res = intent_service.predict(cmd)
    assert res["intent"] == "SYSTEM_INFO", f"Failed for {cmd}: got {res['intent']}"
    assert expected_metric in res["entities"].get("metric_targets", [])


# 10. Humanoid Window Management
@pytest.mark.parametrize(
    "cmd,expected_action,expected_target",
    [
        ("minimize chrome", "minimize", "chrome"),
        ("maximize notepad", "maximize", "notepad"),
        ("focus vscode", "focus", "vscode"),
        ("chrome minimize karo", "minimize", "chrome"),
    ],
)
def test_humanoid_window_management(cmd, expected_action, expected_target):
    res = intent_service.predict(cmd)
    assert res["intent"] == "WINDOW_ACTION", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action
    assert res["entities"].get("window_title") == expected_target


# 11. Humanoid Clipboard AI Tool
@pytest.mark.parametrize(
    "cmd,expected_action",
    [
        ("read clipboard", "read"),
        ("clipboard me kya hai", "read"),
        ("summarize clipboard", "summarize"),
        ("clipboard summarize karo", "summarize"),
        ("clear clipboard", "clear"),
        ("clipboard saaf karo", "clear"),
    ],
)
def test_humanoid_clipboard(cmd, expected_action):
    res = intent_service.predict(cmd)
    assert res["intent"] == "CLIPBOARD_ACTION", f"Failed for {cmd}: got {res['intent']}"
    assert res["entities"].get("action") == expected_action


# 12. Full End-to-End API Execution Check
def test_api_command_end_to_end():
    """Verify natural commands flow from API request through dispatcher to execution cleanly."""
    # 1. System info via API
    res = client.post("/api/command", json={"text": "battery status batao"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "SYSTEM_INFO"
    assert data["executed_tool"] == "system_status"
    assert data["tool_result"]["success"] is True

    # 2. Clipboard action via API
    res2 = client.post("/api/command", json={"text": "clipboard saaf karo"})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "CLIPBOARD_ACTION"
    assert data2["executed_tool"] == "clipboard_tool"

    # 3. Mute action via API
    res3 = client.post("/api/command", json={"text": "aawaz band karo"})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["intent"] == "SYSTEM_CONTROL"
    assert data3["executed_tool"] == "system_control"

    # 4. Small talk / Conversational greeting via API
    res4 = client.post("/api/command", json={"text": "kaise ho"})
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["intent"] == "AI_CHAT"
    assert "ready hoon" in data4["live_response"] or "badiya" in data4["live_response"]
