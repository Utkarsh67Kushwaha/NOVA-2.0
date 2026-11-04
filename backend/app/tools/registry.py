"""
NOVA Safe Tools Framework - Central Tool Registry & Executor
Orchestrates allowlisted tools, validates schemas, enforces risk policies,
coordinates execution with audit logging, and runs post-action verifications.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from backend.app.tools.base import BaseTool, RiskLevel, ToolResult
from backend.app.tools.audit import audit_logger, AuditEntry
from backend.app.tools.permissions import permissions_manager

logger = logging.getLogger("nova.tools.registry")


class ToolRegistry:
    """Central registry and execution coordinator for allowlisted NOVA tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register an allowlisted tool instance."""
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool registration: %s", tool.name)
        self._tools[tool.name] = tool
        logger.info("Registered safe tool '%s' [category: %s, risk: %s]", tool.name, tool.category, tool.risk_level.value)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Lookup tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, Any]]:
        """Return catalog of all registered tools and their schemas."""
        return [tool.to_dict() for tool in self._tools.values()]

    def execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        confirmed_token: Optional[str] = None,
    ) -> ToolResult:
        """
        Safely execute a tool with argument binding, timing, audit logging,
        and post-action verification.
        """
        start_time = time.perf_counter()
        tool = self.get_tool(tool_name)

        if not tool:
            duration_ms = (time.perf_counter() - start_time) * 1000
            err_msg = f"Security rejection: Tool '{tool_name}' is not in the allowlisted registry."
            audit_logger.record(
                tool_name=tool_name,
                category="unknown",
                risk_level="UNKNOWN",
                args=args,
                status="BLOCKED",
                duration_ms=duration_ms,
                output=err_msg,
                verification_status="FAILED",
            )
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=err_msg,
                error="Unregistered or blocked tool.",
            )

        # Pass through confirmation token if provided
        exec_args = dict(args)
        if confirmed_token:
            exec_args["confirmation_token"] = confirmed_token

        try:
            # Execute tool implementation
            result = tool.execute(**exec_args)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Determine audit status
            if result.requires_confirmation:
                status = "PENDING_CONFIRMATION"
            elif result.success:
                status = "SUCCESS"
            else:
                status = "FAILED"

            verification_status = "N/A"
            if result.verification:
                verification_status = "VERIFIED" if result.verification.verified else "UNVERIFIED"

            audit_logger.record(
                tool_name=tool.name,
                category=tool.category,
                risk_level=tool.risk_level.value,
                args=args,
                status=status,
                duration_ms=duration_ms,
                output=result.output,
                verification_status=verification_status,
            )

            return result

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.exception("Unexpected exception executing tool '%s'", tool_name)
            err_str = str(exc)

            audit_logger.record(
                tool_name=tool.name,
                category=tool.category,
                risk_level=tool.risk_level.value,
                args=args,
                status="FAILED",
                duration_ms=duration_ms,
                output=f"Internal tool execution error: {err_str}",
                verification_status="FAILED",
            )

            return ToolResult(
                tool_name=tool.name,
                success=False,
                output=f"Error executing tool '{tool_name}': {err_str}",
                error=err_str,
            )


# Global default registry
default_registry = ToolRegistry()
