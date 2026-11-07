"""
Unit tests for NOVA 2.0 Live Weather, WhatsApp Messaging, and Document Analysis Tools.
Verifies tool execution, offline fallbacks, path sandboxing, intent classification,
anaphoric pronoun resolution, and dispatcher routing.
"""

from unittest.mock import MagicMock, patch
import pytest

from backend.app.services.context_manager import context_manager
from backend.app.services.dispatcher import dispatch_intent
from backend.app.services.intent_service import intent_service
from backend.app.tools.registry import ToolRegistry
from backend.app.tools.doc_analysis_tool import DocAnalysisTool
from backend.app.tools.messaging_tool import WhatsAppTool
from backend.app.tools.weather_tool import WeatherTool


@pytest.fixture(autouse=True)
def reset_session_context():
    context_manager.clear()
    yield
    context_manager.clear()


# =====================================================================
# WeatherTool Tests
# =====================================================================

def test_weather_tool_mocked_success():
    tool = WeatherTool()
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

    with patch("httpx.Client.get", return_value=mock_resp):
        res = tool.execute(city="delhi")
        assert res.success is True
        assert "Delhi" in res.output
        assert "28°C" in res.output
        assert res.data["temp_c"] == "28"
        assert res.verification.verified is True


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


def test_whatsapp_tool_native_startfile():
    tool = WhatsAppTool()
    with patch("os.startfile") as mock_start:
        res = tool.execute(phone="9876543210", message="Hello from test")
        assert res.success is True
        assert mock_start.called
        called_uri = mock_start.call_args[0][0]
        assert "whatsapp://send?phone=919876543210" in called_uri
        assert "Hello%20from%20test" in called_uri


def test_whatsapp_tool_browser_fallback():
    tool = WhatsAppTool()
    with patch("os.startfile", side_effect=FileNotFoundError("No native app")):
        with patch("webbrowser.open") as mock_web:
            res = tool.execute(phone="9876543210", message="Test web fallback")
            assert res.success is True
            assert mock_web.called
            called_url = mock_web.call_args[0][0]
            assert "web.whatsapp.com/send?phone=919876543210" in called_url


# =====================================================================
# DocAnalysisTool Tests
# =====================================================================

def test_doc_analysis_tool_missing_file(tmp_path):
    tool = DocAnalysisTool(workspace_root=tmp_path)
    res = tool.execute(file_path="nonexistent_file.py")
    assert res.success is False
    assert "not found" in res.output.lower()


def test_doc_analysis_tool_success(tmp_path):
    sample_file = tmp_path / "hello.py"
    sample_file.write_text("print('hello world')", encoding="utf-8")

    tool = DocAnalysisTool(workspace_root=tmp_path)
    with patch("backend.app.services.gemini_service.gemini_service.ask", return_value="This script prints hello world."):
        res = tool.execute(file_path="hello.py", prompt="Explain this code")
        assert res.success is True
        assert "prints hello world" in res.output
        assert res.data["file_name"] == "hello.py"


# =====================================================================
# Intent Recognition Tests
# =====================================================================

def test_weather_intent_classification():
    pred = intent_service.predict("Delhi ka mausam kaisa hai")
    assert pred["intent"] == "WEATHER"
    assert pred["entities"].get("city") == "delhi"

    pred2 = intent_service.predict("Aaj ka temperature check karo")
    assert pred2["intent"] == "WEATHER"


def test_whatsapp_intent_classification():
    pred = intent_service.predict("WhatsApp par 9876543210 ko message bhejo: Meeting at 5pm")
    assert pred["intent"] == "WHATSAPP_MESSAGE"
    assert "9876543210" in pred["entities"].get("phone", "")
    assert "Meeting at 5pm" in pred["entities"].get("message", "")


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
            output="Opening WhatsApp to 919876543210.",
            model_dump=lambda: {"result": "success"},
        )
    )
    mock_registry.register(mock_wa)

    prediction = {
        "intent": "WHATSAPP_MESSAGE",
        "entities": {"phone": "9876543210", "message": "Hi NOVA"},
    }
    resp, tool, data = dispatch_intent(prediction, "send whatsapp", registry=mock_registry)
    assert tool == "whatsapp_tool"
    assert "Opening WhatsApp" in resp
    mock_wa.execute.assert_called_with(phone="9876543210", message="Hi NOVA")
