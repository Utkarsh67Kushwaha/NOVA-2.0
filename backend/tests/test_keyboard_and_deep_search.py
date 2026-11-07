"""
Unit & Integration Tests for NOVA 2.0 Voice Keyboard Shortcuts & Deep Search Engines
"""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.intent_service import intent_service
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry

client = TestClient(app)


class TestKeyboardShortcutTool(unittest.TestCase):
    """Tests for KeyboardShortcutTool executing hands-free Win32 key events."""

    def setUp(self):
        self.tool = default_registry.get_tool("keyboard_shortcut")
        self.assertIsNotNone(self.tool)

    @patch("backend.app.tools.desktop_tools.KeyboardShortcutTool._send_keys")
    def test_all_registered_shortcut_actions(self, mock_send):
        actions = [
            "new_tab", "close_tab", "reopen_tab", "next_tab", "prev_tab",
            "copy", "paste", "cut", "select_all", "save", "undo", "redo",
            "refresh", "fullscreen", "zoom_in", "zoom_out", "zoom_reset",
            "show_desktop", "switch_window", "file_explorer"
        ]
        for act in actions:
            res = self.tool.execute(action=act)
            self.assertTrue(res.success, f"Action '{act}' failed execution.")
            self.assertIn("Executed keyboard shortcut", res.output)
            self.assertTrue(res.verification.verified)
        self.assertEqual(mock_send.call_count, len(actions))

    def test_unknown_shortcut_action(self):
        res = self.tool.execute(action="invalid_action_xyz")
        self.assertFalse(res.success)
        self.assertIn("Unknown keyboard action", res.output)


class TestDeepSearchEngines(unittest.TestCase):
    """Tests for WebSearchTool multi-engine search execution."""

    def setUp(self):
        self.tool = default_registry.get_tool("web_search")
        self.assertIsNotNone(self.tool)

    @patch("backend.app.tools.browser_tools.open_url_in_browser")
    def test_search_engines(self, mock_open):
        mock_open.return_value = True
        cases = [
            ("youtube", "lofi beats", "youtube.com/results?search_query="),
            ("github", "fastapi template", "github.com/search?q="),
            ("wikipedia", "quantum physics", "wikipedia.org"),
            ("amazon", "mechanical keyboard", "amazon.in/s?k="),
            ("stackoverflow", "NameError python", "stackoverflow.com/search?q="),
            ("reddit", "machinelearning", "reddit.com/search/?q="),
        ]
        for engine, q, expected_url_sub in cases:
            res = self.tool.execute(query=q, engine=engine)
            self.assertTrue(res.success)
            self.assertIn(expected_url_sub, res.data["search_url"])
            self.assertEqual(res.data["engine"], engine)


class TestKeyboardAndSearchIntents(unittest.TestCase):
    """Tests intent classification for shortcut phrases and deep searches."""

    HOTKEY_INTENT_CASES = [
        ("new tab kholo", "new_tab"),
        ("open new tab", "new_tab"),
        ("tab band karo", "close_tab"),
        ("close tab", "close_tab"),
        ("tab switch karo", "next_tab"),
        ("next tab", "next_tab"),
        ("copy karo", "copy"),
        ("paste karo", "paste"),
        ("select all karo", "select_all"),
        ("sab select karo", "select_all"),
        ("save karo", "save"),
        ("undo karo", "undo"),
        ("page refresh karo", "refresh"),
        ("full screen karo", "fullscreen"),
        ("zoom in karo", "zoom_in"),
        ("zoom out karo", "zoom_out"),
        ("show desktop", "show_desktop"),
        ("switch window", "switch_window"),
    ]

    def test_keyboard_intent_recognition(self):
        for q, expected_act in self.HOTKEY_INTENT_CASES:
            pred = intent_service.predict(q)
            self.assertEqual(
                pred["intent"],
                "KEYBOARD_ACTION",
                f"Query '{q}' failed to classify as KEYBOARD_ACTION (got {pred['intent']})",
            )
            self.assertEqual(
                pred["entities"]["action"],
                expected_act,
                f"Query '{q}' extracted action '{pred['entities']['action']}', expected '{expected_act}'",
            )
            self.assertFalse(pred["needs_clarification"])
            self.assertGreaterEqual(pred["confidence"], 0.90)

    DEEP_SEARCH_CASES = [
        ("search youtube for lofi beats", "youtube", "lofi beats"),
        ("youtube par search karo lofi beats", "youtube", "lofi beats"),
        ("search github for fastapi", "github", "fastapi"),
        ("search wikipedia for quantum computing", "wikipedia", "quantum computing"),
        ("search amazon for headphones", "amazon", "headphones"),
        ("search stackoverflow for TypeError", "stackoverflow", "TypeError"),
    ]

    def test_deep_search_intent_recognition(self):
        for q, expected_eng, expected_q in self.DEEP_SEARCH_CASES:
            pred = intent_service.predict(q)
            self.assertEqual(
                pred["intent"],
                "BROWSER_ACTION",
                f"Query '{q}' failed to classify as BROWSER_ACTION (got {pred['intent']})",
            )
            self.assertEqual(pred["entities"]["engine"], expected_eng)
            self.assertIn(expected_q.lower(), pred["entities"]["search_query"].lower())
            self.assertFalse(pred["needs_clarification"])

    @patch("backend.app.tools.desktop_tools.KeyboardShortcutTool._send_keys")
    def test_dispatcher_routes_keyboard_shortcut(self, mock_send):
        pred = intent_service.predict("new tab kholo")
        live_res, tool_name, tool_res = dispatch_intent(pred, "new tab kholo")
        self.assertEqual(tool_name, "keyboard_shortcut")
        self.assertTrue(tool_res["success"])
        self.assertIn("Ctrl+T", live_res)

    @patch("backend.app.tools.browser_tools.open_url_in_browser")
    def test_dispatcher_routes_deep_search(self, mock_open):
        mock_open.return_value = True
        pred = intent_service.predict("search youtube for lofi beats")
        live_res, tool_name, tool_res = dispatch_intent(pred, "search youtube for lofi beats")
        self.assertEqual(tool_name, "web_search")
        self.assertTrue(tool_res["success"])
        self.assertIn("youtube", tool_res["data"]["search_url"])

    @patch("backend.app.tools.desktop_tools.KeyboardShortcutTool._send_keys")
    def test_api_shortcut_endpoint(self, mock_send):
        resp = client.post("/api/shortcut", json={"action": "refresh"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("Refreshed", data["output"])
