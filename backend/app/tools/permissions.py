"""
NOVA Safe Tools Framework - Permissions & User Confirmation Manager
Manages authorization tokens for high-risk operations (e.g. file overwrites/creations),
timeouts, and cancellation handles for safe execution.
"""

from datetime import datetime, timezone, timedelta
import secrets
import threading
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PendingAction(BaseModel):
    """Represents a high-risk action awaiting user confirmation."""
    token: str
    tool_name: str
    args: Dict[str, Any]
    prompt: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class PermissionsManager:
    """Thread-safe manager for generating and validating confirmation tokens."""

    def __init__(self, token_ttl_seconds: int = 300):
        self._pending_actions: Dict[str, PendingAction] = {}
        self._lock = threading.Lock()
        self._token_ttl = token_ttl_seconds

    def request_confirmation(
        self, tool_name: str, args: Dict[str, Any], prompt: str
    ) -> PendingAction:
        """Create a cryptographic single-use confirmation token for an action."""
        token = secrets.token_urlsafe(16)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._token_ttl)

        action = PendingAction(
            token=token,
            tool_name=tool_name,
            args=args,
            prompt=prompt,
            expires_at=expires_at,
        )

        with self._lock:
            # Clean expired tokens
            self._pending_actions = {
                t: a for t, a in self._pending_actions.items() if not a.is_expired
            }
            self._pending_actions[token] = action

        return action

    def validate_and_consume(self, token: str) -> Optional[PendingAction]:
        """Validate that a confirmation token is valid, unexpired, and consume it."""
        with self._lock:
            action = self._pending_actions.pop(token, None)
            if not action:
                return None
            if action.is_expired:
                return None
            return action

    def reject(self, token: str) -> bool:
        """Reject and cancel a pending confirmation token."""
        with self._lock:
            if token in self._pending_actions:
                del self._pending_actions[token]
                return True
            return False

    def get_pending(self, token: str) -> Optional[PendingAction]:
        """Inspect a pending action without consuming it."""
        with self._lock:
            action = self._pending_actions.get(token)
            if action and not action.is_expired:
                return action
            return None


# Global permissions manager instance
permissions_manager = PermissionsManager()
