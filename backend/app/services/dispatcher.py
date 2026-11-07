"""
NOVA Intent Dispatcher — Shared Action Execution Layer
=======================================================
Single source of truth for routing a classified intent to the
correct Safe Tool or Gemini service.  Both `routes.py` and
`voice_manager.py` previously contained identical (and diverging)
copies of this logic.  Centralising it here:

  * Eliminates the DRY violation
  * Guarantees voice and text paths always behave identically
  * Makes it trivial to add a new intent in one place

Usage::

    from backend.app.services.dispatcher import dispatch_intent

    response_text, executed_tool, tool_result = dispatch_intent(
        prediction, original_query, registry
    )
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from backend.app.services.gemini_service import gemini_service
from backend.app.services.context_manager import context_manager
from backend.app.tools import default_registry
from backend.app.tools.base import ToolResult

logger = logging.getLogger("nova.services.dispatcher")

# Type alias for the 3-tuple returned by dispatch_intent
DispatchResult = Tuple[str, Optional[str], Optional[Dict[str, Any]]]


def dispatch_intent(
    prediction: Dict[str, Any],
    original_query: str,
    registry=None,
) -> DispatchResult:
    """Routes a classified intent prediction to the correct tool/service.

    Args:
        prediction: Dict returned by ``IntentClassifierService.predict()``.
        original_query: The raw user text (used as fallback for Gemini).
        registry: Tool registry instance.  Defaults to ``default_registry``.

    Returns:
        ``(live_response, executed_tool, tool_result)`` — a 3-tuple that
        both the HTTP route handler and the voice manager can use directly.
    """
    reg = registry or default_registry
    intent: str = prediction.get("intent", "UNKNOWN_INTENT")
    entities: Dict[str, Any] = prediction.get("entities", {})
    # Resolve anaphoric pronouns using session context memory
    entities = context_manager.resolve_pronoun_reference(original_query, intent, entities)
    prediction["entities"] = entities

    live_response: str = ""
    executed_tool: Optional[str] = None
    tool_result: Optional[Dict[str, Any]] = None

    try:
        if intent == "SYSTEM_CONTROL":
            action = entities.get("action", "status")
            value = entities.get("value")
            t_res: ToolResult = reg.execute("system_control", {"action": action, "value": value})
            executed_tool = "system_control"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "SYSTEM_INFO":
            targets = entities.get("metric_targets", [])
            filter_name = _map_metric_filter(targets)
            t_res = reg.execute("system_status", {"metric_filter": filter_name})
            executed_tool = "system_status"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "CLOSE_APP":
            app_name = entities.get("app_name")
            if app_name:
                t_res = reg.execute("close_app", {"app_name": app_name})
                executed_tool = "close_app"
                tool_result = t_res.model_dump()
                live_response = t_res.output
            else:
                live_response = "App close intent detected, but no app name was provided."

        elif intent == "WINDOW_ACTION":
            window_title = entities.get("window_title", "window")
            action = entities.get("action", "focus")
            t_res = reg.execute("manage_window", {"window_title": window_title, "action": action})
            executed_tool = "manage_window"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "CLIPBOARD_ACTION":
            action = entities.get("action", "read")
            content = entities.get("content", "")
            t_res = reg.execute("clipboard_tool", {"action": action, "content": content})
            executed_tool = "clipboard_tool"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "OPEN_APP":
            app_name = entities.get("app_name")
            if app_name in ("sc", "screenshot", "snippingtool"):
                t_res = reg.execute("take_screenshot", {})
                executed_tool = "take_screenshot"
                tool_result = t_res.model_dump()
                live_response = t_res.output
            elif app_name:
                t_res = reg.execute("launch_app", {"app_name": app_name})
                executed_tool = "launch_app"
                tool_result = t_res.model_dump()
                live_response = t_res.output
            else:
                live_response = "App launch intent detected, but no specific app name recognised."

        elif intent == "BROWSER_ACTION":
            search_query = entities.get("search_query", original_query)
            engine = entities.get("engine", "google")
            t_res = reg.execute("web_search", {"query": search_query, "engine": engine})
            executed_tool = "web_search"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "FILE_SEARCH":
            target = entities.get("file_name", entities.get("file_query", ""))
            if target:
                t_res = reg.execute("search_files", {"query": target})
                executed_tool = "search_files"
                tool_result = t_res.model_dump()
                live_response = t_res.output
            else:
                live_response = "File search ke liye naam specify karein."

        elif intent == "PLAY_MUSIC":
            live_response, executed_tool, tool_result = _handle_music(
                entities, reg
            )

        elif intent == "REMINDER":
            title = entities.get("title") or original_query
            time_exp = entities.get("time_expression", "")
            due_seconds = entities.get("due_seconds")
            t_res = reg.execute(
                "set_reminder",
                {"title": title, "due_seconds": due_seconds, "time_expression": time_exp},
            )
            executed_tool = "set_reminder"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "NOTE_ACTION":
            action = entities.get("action", "list")
            content = entities.get("content", "")
            t_res = reg.execute("note_tool", {"action": action, "content": content})
            executed_tool = "note_tool"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "SCREEN_VISION":
            prompt = entities.get("prompt", original_query)
            t_res = reg.execute("screen_vision", {"prompt": prompt})
            executed_tool = "screen_vision"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "CALCULATE":
            expr = entities.get("expression", original_query)
            t_res = reg.execute("calculator_tool", {"expression": expr})
            executed_tool = "calculator_tool"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "SYSTEM_MAINTENANCE":
            action = entities.get("action", "open_folder")
            target = entities.get("target", "downloads")
            t_res = reg.execute("system_maintenance", {"action": action, "target": target})
            executed_tool = "system_maintenance"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent == "KEYBOARD_ACTION":
            action = entities.get("action", "refresh")
            t_res = reg.execute("keyboard_shortcut", {"action": action})
            executed_tool = "keyboard_shortcut"
            tool_result = t_res.model_dump()
            live_response = t_res.output

        elif intent in ("DOCUMENT_ANALYSIS", "CODE_ANALYSIS", "AI_CHAT", "UNKNOWN_INTENT"):
            # NOTE: callers that run inside async FastAPI handlers should wrap
            # this in `loop.run_in_executor(None, gemini_service.ask, query)`
            # to avoid blocking the event loop.  The voice manager runs in a
            # background thread so direct call is fine there.
            live_response = gemini_service.ask(original_query)
            executed_tool = "gemini_service"
            tool_result = {"status": "success", "answer": live_response}

        else:
            live_response = f"Command samajh gaya: {intent}."

    except Exception as exc:
        logger.error("Error dispatching intent '%s': %s", intent, exc)
        live_response = f"{intent} command process karte waqt issue aaya."

    # Stamp results back onto the prediction dict for callers that pass it on
    prediction["live_response"] = live_response
    prediction["executed_tool"] = executed_tool
    prediction["tool_result"] = tool_result
    prediction["needs_clarification"] = False

    # Record turn in multi-turn conversation context manager
    try:
        context_manager.record_turn(
            query=original_query,
            intent=intent,
            entities=entities,
            executed_tool=executed_tool,
            tool_result=tool_result,
            live_response=live_response,
        )
    except Exception as exc:
        logger.warning("Failed to record conversation turn: %s", exc)

    return live_response, executed_tool, tool_result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _map_metric_filter(targets: list) -> str:
    """Maps entity metric_targets list to a single filter string."""
    if "battery" in targets:
        return "battery"
    if "ram" in targets or "memory" in targets:
        return "memory"
    if "cpu" in targets:
        return "cpu"
    if "disk" in targets or "storage" in targets:
        return "disk"
    return "all"


def _handle_music(
    entities: Dict[str, Any],
    reg,
) -> Tuple[str, str, Dict[str, Any]]:
    """Handles all PLAY_MUSIC sub-actions."""
    action = entities.get("action", "play")

    if action in ("pause", "stop"):
        t_res = reg.execute("media_control", {"action": "pause"})
        return "Media playback paused.", "media_control", t_res.model_dump()

    if action in ("resume", "continue"):
        t_res = reg.execute("media_control", {"action": "resume"})
        return "Media playback resumed.", "media_control", t_res.model_dump()

    if action == "next":
        t_res = reg.execute("media_control", {"action": "next"})
        return "Skipped to next track.", "media_control", t_res.model_dump()

    if action == "previous":
        t_res = reg.execute("media_control", {"action": "previous"})
        return "Returned to previous track.", "media_control", t_res.model_dump()

    # Default: play a specific track
    track = entities.get("track_or_query", "music")
    t_res = reg.execute("play_music", {"track": track})
    return f"Opening '{track}' in Google Chrome.", "play_music", t_res.model_dump()
