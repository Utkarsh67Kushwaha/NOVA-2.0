"""
Unit and Integration Tests for NOVA Context Memory & Anaphoric Pronoun Resolution
"""

import pytest
from backend.app.services.context_manager import ConversationContextManager, context_manager
from backend.app.services.intent_service import intent_service
from backend.app.services.dispatcher import dispatch_intent


class TestContextMemory:
    def setup_method(self):
        context_manager.clear()

    def teardown_method(self):
        context_manager.clear()

    def test_record_turn_and_state(self):
        ctx = ConversationContextManager()
        ctx.record_turn(
            query="open notepad",
            intent="OPEN_APP",
            entities={"app_name": "notepad"},
            executed_tool="launch_app",
            tool_result={"success": True, "output": "Notepad launched"},
            live_response="Opening notepad.",
        )
        assert ctx.last_app == "notepad"
        assert ctx.last_intent == "OPEN_APP"
        assert ctx.last_tool == "launch_app"
        assert len(ctx.history) == 1

        state = ctx.get_state()
        assert state["last_app"] == "notepad"
        assert state["turn_count"] == 1

    def test_resolve_pronoun_close_app(self):
        ctx = ConversationContextManager()
        ctx.last_app = "chrome"

        resolved = ctx.resolve_pronoun_reference("isko band karo", "CLOSE_APP", {"app_name": "isko"})
        assert resolved["app_name"] == "chrome"
        assert resolved["resolved_from_context"] is True

        resolved_en = ctx.resolve_pronoun_reference("close it please", "CLOSE_APP", {})
        assert resolved_en["app_name"] == "chrome"

    def test_resolve_pronoun_window_action(self):
        ctx = ConversationContextManager()
        ctx.last_app = "spotify"

        resolved = ctx.resolve_pronoun_reference("ise minimize karo", "WINDOW_ACTION", {"action": "minimize", "window_title": "ise"})
        assert resolved["window_title"] == "spotify"
        assert resolved["action"] == "minimize"

    def test_multi_turn_flow_with_dispatcher(self):
        context_manager.clear()

        # Turn 1: Launch Notepad
        pred1 = intent_service.predict("notepad kholo")
        assert pred1["intent"] == "OPEN_APP"
        assert pred1["entities"]["app_name"] == "notepad"

        resp1, tool1, res1 = dispatch_intent(pred1, "notepad kholo")
        assert context_manager.last_app == "notepad"

        # Turn 2: Follow-up with pronoun "isko band karo"
        pred2 = intent_service.predict("isko band karo")
        assert pred2["intent"] == "CLOSE_APP"
        assert pred2["entities"]["app_name"] == "notepad"

        # Turn 3: Window action pronoun "ise minimize karo"
        pred3 = intent_service.predict("ise minimize karo")
        assert pred3["intent"] == "WINDOW_ACTION"
        assert pred3["entities"]["window_title"] == "notepad"

    def test_context_api_endpoints(self):
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        context_manager.clear()

        # Send command
        res = client.post("/api/command", json={"text": "calc kholo"})
        assert res.status_code == 200

        # Query context state
        ctx_res = client.get("/api/context")
        assert ctx_res.status_code == 200
        data = ctx_res.json()
        assert data["status"] == "success"
        assert data["context"]["last_app"] == "calculator"
        assert data["context"]["turn_count"] >= 1

        # Clear context
        clr_res = client.post("/api/context/clear")
        assert clr_res.status_code == 200
        assert context_manager.last_app is None
