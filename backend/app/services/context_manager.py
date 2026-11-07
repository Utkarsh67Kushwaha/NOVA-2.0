"""
NOVA Multi-Turn Conversational & Context Memory Engine
=====================================================
Maintains short-term session context across voice and text commands.
Enables:
  1. Anaphoric pronoun resolution ("isko band karo", "close it", "use open karo")
  2. Entity retention (last opened app, last inspected file, last search query)
  3. Conversational dialogue history for seamless multi-turn follow-ups
  4. Inspection and manual reset via /api/context endpoints
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger("nova.services.context")

# Pronouns in Hindi, Hinglish, and English
PRONOUN_PATTERNS = [
    r"\b(?:isko|isey|ise|usey|use|usko|iss|is)\b",
    r"\b(?:it|this|that)\b",
    r"\b(?:this|that|is|iss|use)\s+(?:app|application|window|file|ko)\b",
]

PRONOUN_REGEX = re.compile("|".join(PRONOUN_PATTERNS), re.IGNORECASE)


PRONOUN_TOKENS = {
    "it", "this", "that", "isko", "ise", "isey", "use", "usey", "usko", "iss", "is", "context_last_app", "window"
}


class ConversationContextManager:
    """Thread-safe conversational context and entity memory tracker."""

    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.last_app: Optional[str] = None
        self.last_file: Optional[str] = None
        self.last_search_query: Optional[str] = None
        self.last_intent: Optional[str] = None
        self.last_tool: Optional[str] = None
        self.last_tool_result: Optional[str] = None
        self.history: List[Dict[str, Any]] = []

    def record_turn(
        self,
        query: str,
        intent: str,
        entities: Dict[str, Any],
        executed_tool: Optional[str] = None,
        tool_result: Optional[Any] = None,
        live_response: Optional[str] = None,
    ) -> None:
        """Records an executed turn and updates active entity memory."""
        # 1. Update last app if explicitly provided or resolved
        app_name = entities.get("app_name")
        if app_name and app_name not in ("it", "isko", "use", "context_last_app"):
            self.last_app = app_name
        elif entities.get("window_title") and entities["window_title"] not in ("window", "it", "isko"):
            self.last_app = entities["window_title"]

        # 2. Update last file if referenced
        if entities.get("file_path"):
            self.last_file = entities["file_path"]
        elif entities.get("file_name"):
            self.last_file = entities["file_name"]
        elif entities.get("file_query"):
            self.last_file = entities["file_query"]

        # 3. Update last search query
        if entities.get("search_query"):
            self.last_search_query = entities["search_query"]

        self.last_intent = intent
        self.last_tool = executed_tool

        # Format result snippet
        if isinstance(tool_result, dict):
            self.last_tool_result = str(tool_result.get("output") or tool_result.get("answer") or "")[:200]
        elif tool_result:
            self.last_tool_result = str(tool_result)[:200]

        turn = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "intent": intent,
            "entities": entities,
            "executed_tool": executed_tool,
            "response": live_response,
        }
        self.history.append(turn)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

        logger.debug(
            "Context updated: last_app='%s', last_file='%s', turns=%d",
            self.last_app,
            self.last_file,
            len(self.history),
        )

    def has_pronoun(self, text: str) -> bool:
        """Returns True if user query contains anaphoric pronouns."""
        return bool(PRONOUN_REGEX.search(text))

    def resolve_pronoun_reference(
        self,
        text: str,
        intent: str,
        entities: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Resolves anaphoric pronouns ('isko', 'use', 'it', 'this') using active context."""
        resolved = dict(entities)
        query_has_pronoun = self.has_pronoun(text)

        # Case 1: CLOSE_APP intent
        if intent == "CLOSE_APP":
            app = resolved.get("app_name")
            if (not app or app in PRONOUN_TOKENS) and self.last_app:
                resolved["app_name"] = self.last_app
                resolved["resolved_from_context"] = True
                logger.info("Context resolved CLOSE_APP target: '%s'", self.last_app)

        # Case 2: WINDOW_ACTION intent
        elif intent == "WINDOW_ACTION":
            target = resolved.get("window_title")
            if (not target or target in PRONOUN_TOKENS) and self.last_app:
                resolved["window_title"] = self.last_app
                resolved["resolved_from_context"] = True
                logger.info("Context resolved WINDOW_ACTION target: '%s'", self.last_app)

        # Case 3: OPEN_APP intent with pronoun
        elif intent == "OPEN_APP":
            if (query_has_pronoun or resolved.get("app_name") in PRONOUN_TOKENS) and not resolved.get("app_name"):
                if self.last_app:
                    resolved["app_name"] = self.last_app
                    resolved["resolved_from_context"] = True
                    logger.info("Context resolved OPEN_APP target: '%s'", self.last_app)

        # Case 4: FILE_SEARCH or FILE_READ with pronoun
        elif intent == "FILE_SEARCH":
            if query_has_pronoun and not resolved.get("file_name") and self.last_file:
                resolved["file_name"] = self.last_file
                resolved["resolved_from_context"] = True
                logger.info("Context resolved FILE_SEARCH target: '%s'", self.last_file)

        # Case 5: DOCUMENT_ANALYSIS with pronoun ("isko explain karo", "analyze this file")
        elif intent in ("DOCUMENT_ANALYSIS", "CODE_ANALYSIS"):
            if (query_has_pronoun or not resolved.get("file_path")) and self.last_file:
                resolved["file_path"] = self.last_file
                resolved["resolved_from_context"] = True
                logger.info("Context resolved DOCUMENT_ANALYSIS target: '%s'", self.last_file)

        return resolved

    def get_state(self) -> Dict[str, Any]:
        """Returns current context snapshot for API status inspection."""
        return {
            "last_app": self.last_app,
            "last_file": self.last_file,
            "last_search_query": self.last_search_query,
            "last_intent": self.last_intent,
            "last_tool": self.last_tool,
            "turn_count": len(self.history),
            "recent_turns": self.history[-5:],
        }

    def clear(self) -> None:
        """Resets active context memory."""
        self.last_app = None
        self.last_file = None
        self.last_search_query = None
        self.last_intent = None
        self.last_tool = None
        self.last_tool_result = None
        self.history.clear()
        logger.info("Conversation context cleared.")


# Global context manager singleton
context_manager = ConversationContextManager()
