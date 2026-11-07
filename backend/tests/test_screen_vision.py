"""
Unit & Integration Tests for NOVA 2.0 Live Screen Vision & Multimodal Desktop Intelligence
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.intent_service import intent_service
from backend.app.services.gemini_service import gemini_service
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry

client = TestClient(app)


class TestScreenVisionTool(unittest.TestCase):
    """Tests for ScreenVisionTool and Gemini Multimodal Vision Service."""

    def test_screen_vision_tool_execution(self):
        """Verifies ScreenVisionTool executes, inspects system state, and returns a verified result."""
        tool = default_registry.get_tool("screen_vision")
        self.assertIsNotNone(tool)

        res = tool.execute(prompt="What is on my screen?")
        self.assertTrue(res.success)
        self.assertTrue(res.verification.verified)
        self.assertIn("active_window", res.data)
        self.assertIn("running_apps", res.data)
        self.assertIsInstance(res.output, str)
        self.assertGreater(len(res.output), 5)

    def test_offline_screen_intelligence_fallback(self):
        """Verifies offline screen brain gives an articulate response without crashing."""
        out = gemini_service._offline_screen_brain(
            window_context="Visual Studio Code - NOVA 2.0",
            running_apps=["chrome.exe", "spotify.exe"],
            prompt="What is on my screen?",
        )
        self.assertIn("Visual Studio Code", out)
        self.assertIn("Chrome", out)

    @patch("httpx.Client.post")
    def test_gemini_multimodal_vision_online(self, mock_post):
        """Verifies that when configured with an API key, Gemini Multimodal Vision API is invoked."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "Aapke screen par Visual Studio Code khula hua hai jisme Python script active hai."}
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        # Temporarily enable configured API key
        orig_key = gemini_service.api_key
        gemini_service.api_key = "test_valid_dummy_gemini_key_12345"

        try:
            sample_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 600
            result = gemini_service.analyze_screen(
                image_bytes=sample_bytes,
                prompt="Screen explain karo",
                window_context="VS Code",
            )
            self.assertIn("Visual Studio Code", result)
            self.assertTrue(mock_post.called)
        finally:
            gemini_service.api_key = orig_key


class TestScreenVisionIntents(unittest.TestCase):
    """Tests intent classification for varied screen vision voice queries."""

    VISION_QUERIES = [
        "what's on my screen",
        "whats on my screen",
        "what is on my screen",
        "screen par kya hai",
        "screen pe kya hai",
        "screen par kya chal raha hai",
        "look at my screen",
        "screen dekho",
        "screen dekh kar batao",
        "summarize screen",
        "explain screen",
        "screen explain karo",
        "explain active window",
        "what am i looking at",
        "display par kya hai",
        "read my screen",
    ]

    def test_screen_vision_intent_recognition(self):
        for q in self.VISION_QUERIES:
            pred = intent_service.predict(q)
            self.assertEqual(
                pred["intent"],
                "SCREEN_VISION",
                f"Query '{q}' failed to classify as SCREEN_VISION (got {pred['intent']})",
            )
            self.assertFalse(pred["needs_clarification"])
            self.assertGreaterEqual(pred["confidence"], 0.90)

    def test_dispatcher_routes_screen_vision(self):
        pred = intent_service.predict("screen par kya hai")
        live_res, tool_name, tool_res = dispatch_intent(pred, "screen par kya hai")
        self.assertEqual(tool_name, "screen_vision")
        self.assertTrue(tool_res["success"])
        self.assertGreater(len(live_res), 5)

    def test_api_command_screen_vision_endpoint(self):
        """Verifies POST /api/command handles screen vision seamlessly without blocking."""
        resp = client.post("/api/command", json={"text": "what is on my screen"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["intent"], "SCREEN_VISION")
        self.assertEqual(data["executed_tool"], "screen_vision")
        self.assertTrue(len(data["live_response"]) > 5)

    def test_dedicated_screen_analyze_endpoint(self):
        """Verifies POST /api/screen/analyze returns live analysis data."""
        resp = client.post("/api/screen/analyze", json={"prompt": "Explain active window"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("output", data)
        self.assertIn("data", data)
