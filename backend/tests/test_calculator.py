"""
Unit & Integration Tests for NOVA 2.0 Safe Voice Math & Instant Calculator
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.intent_service import intent_service
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry

client = TestClient(app)


class TestCalculatorTool(unittest.TestCase):
    """Tests for CalculatorTool safe AST mathematical evaluation."""

    def setUp(self):
        self.tool = default_registry.get_tool("calculator_tool")
        self.assertIsNotNone(self.tool)

    def test_percentage_calculations(self):
        cases = [
            ("20% of 1500", "20% of 1500 is 300.", 300),
            ("18% GST on 5000", "18% of 5000 is 900.", 900),
            ("500 ka 10 percent", "10% of 500 is 50.", 50),
            ("50% of 80", "50% of 80 is 40.", 40),
            ("12.5% of 200", "12.5% of 200 is 25.", 25),
        ]
        for expr, expected_output, expected_val in cases:
            res = self.tool.execute(expression=expr)
            self.assertTrue(res.success)
            self.assertEqual(res.output, expected_output)
            self.assertEqual(res.data["result"], expected_val)
            self.assertTrue(res.verification.verified)

    def test_basic_arithmetic(self):
        cases = [
            ("100 + 250", 350),
            ("500 - 125", 375),
            ("15 * 40", 600),
            ("500 / 10", 50),
            ("2 ** 8", 256),
            ("100 / 3", 33.3333),
        ]
        for expr, expected_val in cases:
            res = self.tool.execute(expression=expr)
            self.assertTrue(res.success)
            self.assertAlmostEqual(res.data["result"], expected_val, places=4)

    def test_natural_language_math_synonyms(self):
        cases = [
            ("15 into 40", 600),
            ("12 times 8", 96),
            ("500 divided by 10", 50),
            ("100 plus 45", 145),
            ("200 minus 75", 125),
            ("2 raise to 10", 1024),
        ]
        for expr, expected_val in cases:
            res = self.tool.execute(expression=expr)
            self.assertTrue(res.success)
            self.assertEqual(res.data["result"], expected_val)

    def test_invalid_and_empty_expressions(self):
        empty_res = self.tool.execute(expression="")
        self.assertFalse(empty_res.success)

        invalid_res = self.tool.execute(expression="abc def")
        self.assertFalse(invalid_res.success)

    def test_security_against_eval_injection(self):
        malicious = "__import__('os').system('calc')"
        res = self.tool.execute(expression=malicious)
        self.assertFalse(res.success)


class TestCalculatorIntents(unittest.TestCase):
    """Tests intent classification and end-to-end routing for math queries."""

    CALC_QUERIES = [
        "calculate 20% of 1500",
        "calculate 100 + 250",
        "hisab karo 500 divided by 5",
        "15 into 40 kitna hota hai",
        "solve 12 * 8",
        "calculate 18% gst on 5000",
        "500 ka 10 percent kitna hua",
    ]

    def test_calculator_intent_recognition(self):
        for q in self.CALC_QUERIES:
            pred = intent_service.predict(q)
            self.assertEqual(
                pred["intent"],
                "CALCULATE",
                f"Query '{q}' failed to classify as CALCULATE (got {pred['intent']})",
            )
            self.assertFalse(pred["needs_clarification"])
            self.assertGreaterEqual(pred["confidence"], 0.90)

    def test_dispatcher_routes_calculator(self):
        pred = intent_service.predict("calculate 20% of 1500")
        live_res, tool_name, tool_res = dispatch_intent(pred, "calculate 20% of 1500")
        self.assertEqual(tool_name, "calculator_tool")
        self.assertTrue(tool_res["success"])
        self.assertEqual(live_res, "20% of 1500 is 300.")

    def test_api_command_calculator_flow(self):
        resp = client.post("/api/command", json={"text": "calculate 15 into 40"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["intent"], "CALCULATE")
        self.assertEqual(data["executed_tool"], "calculator_tool")
        self.assertIn("600", data["live_response"])
