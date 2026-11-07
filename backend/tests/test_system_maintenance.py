"""
Unit & Integration Tests for NOVA 2.0 Windows System Maintenance, Quick Folders & Diagnostics
"""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.intent_service import intent_service
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry

client = TestClient(app)


class TestSystemMaintenanceTool(unittest.TestCase):
    """Tests for SystemMaintenanceTool sub-actions."""

    def setUp(self):
        self.tool = default_registry.get_tool("system_maintenance")
        self.assertIsNotNone(self.tool)

    def test_empty_recycle_bin(self):
        """Verifies SHEmptyRecycleBinW executes safely without raising exceptions."""
        res = self.tool.execute(action="empty_recycle_bin")
        self.assertTrue(res.success)
        self.assertIn("Recycle Bin has been emptied", res.output)
        self.assertTrue(res.verification.verified)

    @patch("subprocess.Popen")
    def test_open_folder_downloads(self, mock_popen):
        """Verifies folder launcher targets user Downloads directory."""
        res = self.tool.execute(action="open_folder", target="downloads")
        self.assertTrue(res.success)
        self.assertIn("Downloads", res.output)
        self.assertTrue(mock_popen.called)

    @patch("subprocess.Popen")
    def test_open_folder_recycle_bin(self, mock_popen):
        """Verifies Recycle Bin special virtual shell folder launch."""
        res = self.tool.execute(action="open_folder", target="recycle bin")
        self.assertTrue(res.success)
        self.assertIn("Recycle Bin", res.output)
        self.assertTrue(mock_popen.called)

    def test_process_diagnostics(self):
        """Verifies top memory processes aggregation."""
        res = self.tool.execute(action="process_diagnostics")
        self.assertTrue(res.success)
        self.assertIn("Top resource-consuming applications", res.output)
        self.assertIn("top_processes", res.data)
        self.assertGreater(len(res.data["top_processes"]), 0)

    def test_network_status_check(self):
        """Verifies fast internet connectivity and latency measurement."""
        res = self.tool.execute(action="network_status")
        self.assertTrue(res.success)
        self.assertIn("connected", res.data)
        self.assertIsInstance(res.output, str)
        self.assertGreater(len(res.output), 10)

    def test_disk_breakdown(self):
        """Verifies partition free space retrieval across mounted drives."""
        res = self.tool.execute(action="disk_breakdown")
        self.assertTrue(res.success)
        self.assertIn("Drive Storage Status", res.output)
        self.assertIn("drives", res.data)
        self.assertGreater(len(res.data["drives"]), 0)


class TestSystemMaintenanceIntents(unittest.TestCase):
    """Tests intent classification for maintenance voice commands."""

    MAINTENANCE_CASES = [
        ("empty recycle bin", "empty_recycle_bin"),
        ("recycle bin saaf karo", "empty_recycle_bin"),
        ("empty trash", "empty_recycle_bin"),
        ("downloads folder kholo", "open_folder"),
        ("open documents", "open_folder"),
        ("desktop folder kholo", "open_folder"),
        ("open pictures folder", "open_folder"),
        ("top processes batao", "process_diagnostics"),
        ("ram kaun use kar raha hai", "process_diagnostics"),
        ("internet check karo", "network_status"),
        ("check internet connection", "network_status"),
        ("all drives status", "disk_breakdown"),
    ]

    def test_maintenance_intent_recognition(self):
        for q, expected_act in self.MAINTENANCE_CASES:
            pred = intent_service.predict(q)
            self.assertEqual(
                pred["intent"],
                "SYSTEM_MAINTENANCE",
                f"Query '{q}' failed to classify as SYSTEM_MAINTENANCE (got {pred['intent']})",
            )
            self.assertEqual(
                pred["entities"]["action"],
                expected_act,
                f"Query '{q}' extracted action '{pred['entities']['action']}', expected '{expected_act}'",
            )
            self.assertFalse(pred["needs_clarification"])
            self.assertGreaterEqual(pred["confidence"], 0.90)

    def test_dispatcher_routes_maintenance(self):
        pred = intent_service.predict("internet check karo")
        live_res, tool_name, tool_res = dispatch_intent(pred, "internet check karo")
        self.assertEqual(tool_name, "system_maintenance")
        self.assertTrue(tool_res["success"])
        self.assertIn("Internet", live_res)

    def test_api_command_maintenance_flow(self):
        resp = client.post("/api/command", json={"text": "internet check karo"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["intent"], "SYSTEM_MAINTENANCE")
        self.assertEqual(data["executed_tool"], "system_maintenance")

    def test_dedicated_maintenance_endpoint(self):
        resp = client.post("/api/maintenance", json={"action": "network_status"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("output", data)
