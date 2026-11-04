"""
NOVA Safe Tools Framework - Structured Audit Logging
Records structured history of all tool invocations, arguments, outcomes,
execution durations, and verification states for security and traceability.
"""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class AuditEntry(BaseModel):
    """A single audit log record of a tool execution."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    tool_name: str
    category: str
    risk_level: str
    args: Dict[str, Any]
    status: str       # 'SUCCESS', 'FAILED', 'BLOCKED', 'CANCELLED', 'PENDING_CONFIRMATION'
    duration_ms: float
    output: str
    verification_status: str  # 'VERIFIED', 'UNVERIFIED', 'FAILED', 'N/A'
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ToolAuditLogger:
    """Thread-safe in-memory circular audit store for tool invocations."""

    def __init__(self, max_entries: int = 200):
        self._entries: List[AuditEntry] = []
        self._lock = threading.Lock()
        self._max_entries = max_entries

    def record(
        self,
        tool_name: str,
        category: str,
        risk_level: str,
        args: Dict[str, Any],
        status: str,
        duration_ms: float,
        output: str,
        verification_status: str = "N/A",
    ) -> AuditEntry:
        """Create and store a new audit record."""
        # Sanitize sensitive fields if any
        sanitized_args = {k: v for k, v in args.items() if not k.lower().endswith("token")}

        entry = AuditEntry(
            tool_name=tool_name,
            category=category,
            risk_level=risk_level,
            args=sanitized_args,
            status=status,
            duration_ms=round(duration_ms, 2),
            output=output[:500] if output else "",
            verification_status=verification_status,
        )

        with self._lock:
            self._entries.insert(0, entry)  # Newest first
            if len(self._entries) > self._max_entries:
                self._entries.pop()

        return entry

    def get_entries(self, limit: int = 50) -> List[AuditEntry]:
        """Return the most recent audit entries."""
        with self._lock:
            return list(self._entries[:limit])

    def clear(self) -> None:
        """Clear audit history (for test fixtures)."""
        with self._lock:
            self._entries.clear()


# Global audit logger instance
audit_logger = ToolAuditLogger()
