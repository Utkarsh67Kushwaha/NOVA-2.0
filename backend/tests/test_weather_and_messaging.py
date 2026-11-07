"""
Unit tests for NOVA 2.0 Live Weather, WhatsApp Messaging, and Document Analysis Tools.
Verifies robust tool execution, TTL caching, phone/contact normalization,
binary file protection, offline fallbacks, intent classification,
anaphoric pronoun resolution, and dispatcher routing.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.app.services.context_manager import context_manager
from backend.app.services.dispatcher import dispatch_intent
from backend.app.services.intent_service import intent_service
from backend.app.tools.doc_analysis_tool import DocAnalysisTool
from backend.app.tools.messaging_tool import WhatsAppTool
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.weather_tool import WeatherTool


@pytest.fixture(autouse=True)
def reset_session_context():
    context_manager.clear()
    yield
    context_manager.clear()


# =====================================================================
# WeatherTool Tests
# =====================================================================

def test_weather_tool_mocked_success_and_caching():
    tool = WeatherTool(cache_ttl_seconds=300)
    fake_payload = {
        "current_condition": [
            {
                "temp_C": "28",
                "FeelsLikeC": "30",
                "weatherDesc": [{"value": "Sunny"}],
                "humidity": "45",
                "windspeedKmph": "12",
            }
        ],
        "nearest_area": [
            {"areaName": [{"value": "Delhi"}]}
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_payload

    # First call: network fetch
    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        res1 = tool.execute(city="delhi")
        assert res1.success is True
        assert "Delhi" in res1.output
        assert "28°C" in res1.output
        assert "Sunny" in res1.output
        assert res1.data["cached"] is False
        assert mock_get.call_count == 1

        # Second call: served directly from memory cache without network call
        res2 = tool.execute(city="delhi")
        assert res2.success is True
        assert res2.data["cached"] is True
        assert mock_get.call_count == 1  # No additional network call!


def test_weather_tool_multi_word_city():
    tool = WeatherTool()
    fake_payload = {
        "current_condition": [
            {
                "temp_C": "22",
                "FeelsLikeC": "22",
                "weatherDesc": [{"value": "Partly cloudy"}],
                "humidity": "60",
                "windspeedKmph": "15",
            }
        ],
        "nearest_area": [
            {"areaName": [{"value": "New York"}]}
        ],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_payload

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        res = tool.execute(city="New York")
        assert res.success is True
        assert "New York" in res.output
        called_url = mock_get.call_args[0][0]
        assert "New+York" in called_url


def test_weather_tool_offline_fallback():
    tool = WeatherTool()
    with patch("httpx.Client.get", side_effect=Exception("Network unreachable")):
        res = tool.execute(city="Mumbai")
        assert res.success is True
        assert "network issue" in res.output.lower() or "offline" in str(res.data)
        assert res.data["offline"] is True


# =====================================================================
# WhatsAppTool Tests
# =====================================================================

def test_whatsapp_tool_empty_message():
    tool = WhatsAppTool()
    res = tool.execute(message="")
    assert res.success is False
    assert "cannot be empty" in res.output


def test_whatsapp_tool_phone_normalization_10_and_11_digits():
    tool = WhatsAppTool()
    with patch("os.startfile") as mock_start:
        # 10-digit Indian number
        res1 = tool.execute(phone="9876543210", message="Hello 10")
        assert res1.success is True
        assert "phone=919876543210" in mock_start.call_args[0][0]

        # 11-digit number with leading 0
        res2 = tool.execute(phone="09876543210", message="Hello 11")
        assert res2.success is True
        assert "phone=919876543210" in mock_start.call_args[0][0]


def test_whatsapp_tool_contact_name_without_phone():
    tool = WhatsAppTool()
    with patch("os.startfile") as mock_start:
        res = tool.execute(contact_name="Rahul", message="Kal 10 baje milte hain")
        assert res.success is True
        assert "Rahul" in res.output
        called_uri = mock_start.call_args[0][0]
        assert "phone=" not in called_uri
        assert "text=" in called_uri


def test_whatsapp_tool_browser_fallback():
    tool = WhatsAppTool()
    with patch("os.startfile", side_effect=FileNotFoundError("No native client")):
        with patch("webbrowser.open") as mock_web:
            res = tool.execute(phone="9876543210", message="Web fallback test")
            assert res.success is True
            assert mock_web.called
            called_url = mock_web.call_args[0][0]
            assert "web.whatsapp.com/send?phone=919876543210" in called_url


# =====================================================================
# DocAnalysisTool Tests
# =====================================================================

def test_doc_analysis_tool_binary_file_rejection(tmp_path):
    tool = DocAnalysisTool(workspace_root=tmp_path)
    binary_file = tmp_path / "photo.png"
    binary_file.write_bytes(b"\x89PNG\r\n\x1a\nfake binary data")

    res = tool.execute(file_path="photo.png")
    assert res.success is False
    assert "binary/media file" in res.output


def test_doc_analysis_tool_missing_file(tmp_path):
    tool = DocAnalysisTool(workspace_root=tmp_path)
    res = tool.execute(file_path="nonexistent_code.py")
    assert res.success is False
    assert "nahi mili" in res.output or "not found" in res.output.lower()


def test_doc_analysis_tool_offline_heuristic_fallback(tmp_path):
    sample_py = tmp_path / "service.py"
    sample_py.write_text(
        "class AuthService:\n    def login(self):\n        pass\n    def logout(self):\n        pass\n",
        encoding="utf-8",
    )

    tool = DocAnalysisTool(workspace_root=tmp_path)
    # When Gemini is unconfigured or offline
    with patch("backend.app.services.gemini_service.gemini_service.is_configured", return_value=False):
        res = tool.execute(file_path="service.py")
        assert res.success is True
        assert "AuthService" in res.output or "login" in res.output
        assert "Offline Analysis" in res.output


def test_doc_analysis_tool_gemini_success(tmp_path):
    sample_file = tmp_path / "hello.py"
    sample_file.write_text("print('hello world')", encoding="utf-8")

    tool = DocAnalysisTool(workspace_root=tmp_path)
    with patch("backend.app.services.gemini_service.gemini_service.is_configured", return_value=True):
        with patch("backend.app.services.gemini_service.gemini_service.ask", return_value="This script prints hello world."):
            res = tool.execute(file_path="hello.py", prompt="Explain this code")
            assert res.success is True
            assert "prints hello world" in res.output
            assert res.data["file_name"] == "hello.py"


# =====================================================================
# Intent Recognition Tests
# =====================================================================

def test_weather_intent_multi_word_and_single_word():
    # Single word
    pred1 = intent_service.predict("Delhi ka mausam kaisa hai")
    assert pred1["intent"] == "WEATHER"
    assert pred1["entities"].get("city") == "delhi"

    # Multi-word city
    pred2 = intent_service.predict("New York ka mausam kaisa hai")
    assert pred2["intent"] == "WEATHER"
    assert pred2["entities"].get("city") == "new york"

    # Weather in ...
    pred3 = intent_service.predict("weather in San Francisco")
    assert pred3["intent"] == "WEATHER"
    assert pred3["entities"].get("city") == "san francisco"

    # Auto detect location
    pred4 = intent_service.predict("Aaj ka mausam kaisa hai")
    assert pred4["intent"] == "WEATHER"
    assert pred4["entities"].get("city") == ""


def test_whatsapp_intent_with_phone_and_contact():
    # With numeric phone
    pred1 = intent_service.predict("WhatsApp par 9876543210 ko message bhejo: Meeting at 5pm")
    assert pred1["intent"] == "WHATSAPP_MESSAGE"
    assert pred1["entities"].get("phone") == "9876543210"
    assert pred1["entities"].get("message") == "Meeting at 5pm"

    # With contact name
    pred2 = intent_service.predict("WhatsApp par Rahul ko message bhejo: Kal 10 baje milte hain")
    assert pred2["intent"] == "WHATSAPP_MESSAGE"
    assert pred2["entities"].get("contact_name") == "Rahul"
    assert pred2["entities"].get("message") == "Kal 10 baje milte hain"


def test_doc_analysis_intent_and_anaphora():
    pred = intent_service.predict("README.md ko explain karo")
    assert pred["intent"] == "DOCUMENT_ANALYSIS"
    assert "readme.md" in pred["entities"].get("file_path", "").lower()

    # Multi-turn anaphoric test: Turn 1 records README.md
    context_manager.record_turn(
        query="README.md search karo",
        intent="FILE_SEARCH",
        entities={"file_name": "README.md"},
        executed_tool="search_files",
    )

    # Turn 2: "isko explain karo"
    pred2 = intent_service.predict("isko explain karo")
    assert pred2["intent"] == "DOCUMENT_ANALYSIS"
    resolved = context_manager.resolve_pronoun_reference("isko explain karo", pred2["intent"], pred2["entities"])
    assert resolved.get("file_path") == "README.md"
    assert resolved.get("resolved_from_context") is True


# =====================================================================
# Dispatcher Routing Tests
# =====================================================================

def test_dispatcher_weather_routing():
    mock_registry = ToolRegistry()
    mock_weather = WeatherTool()
    mock_weather.execute = MagicMock(
        return_value=MagicMock(
            output="Taapman 25°C hai.",
            model_dump=lambda: {"result": "success"},
        )
    )
    mock_registry.register(mock_weather)

    prediction = {
        "intent": "WEATHER",
        "entities": {"city": "delhi"},
    }
    resp, tool, data = dispatch_intent(prediction, "Delhi ka mausam", registry=mock_registry)
    assert tool == "weather_tool"
    assert "25°C" in resp
    mock_weather.execute.assert_called_with(city="delhi")


def test_dispatcher_whatsapp_routing():
    mock_registry = ToolRegistry()
    mock_wa = WhatsAppTool()
    mock_wa.execute = MagicMock(
        return_value=MagicMock(
            output="Opening WhatsApp for Rahul.",
            model_dump=lambda: {"result": "success"},
        )
    )
    mock_registry.register(mock_wa)

    prediction = {
        "intent": "WHATSAPP_MESSAGE",
        "entities": {"phone": "", "contact_name": "Rahul", "message": "Hi Rahul"},
    }
    resp, tool, data = dispatch_intent(prediction, "send whatsapp", registry=mock_registry)
    assert tool == "whatsapp_tool"
    assert "Opening WhatsApp" in resp
    mock_wa.execute.assert_called_with(message="Hi Rahul", phone="", contact_name="Rahul")
