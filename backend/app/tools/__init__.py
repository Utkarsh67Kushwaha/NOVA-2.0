"""
NOVA Safe Tools Framework Package
Exposes initialized default_registry with all desktop, browser, and file tools.
"""

from backend.app.tools.base import BaseTool, RiskLevel, ToolResult, VerificationResult
from backend.app.tools.registry import default_registry, ToolRegistry
from backend.app.tools.audit import audit_logger, AuditEntry
from backend.app.tools.permissions import permissions_manager, PendingAction

# Import tool classes
from backend.app.tools.desktop_tools import LaunchAppTool, SystemStatusTool, ManageWindowTool
from backend.app.tools.browser_tools import OpenUrlTool, WebSearchTool
from backend.app.tools.file_tools import (
    ListFilesTool,
    SearchFilesTool,
    ReadTextFileTool,
    CreateFileTool,
)

# Register all built-in tools into default registry
def setup_default_tools(registry: ToolRegistry = default_registry) -> ToolRegistry:
    """Register all allowlisted tools into the given registry."""
    # Desktop tools
    registry.register(LaunchAppTool())
    registry.register(SystemStatusTool())
    registry.register(ManageWindowTool())

    # Browser tools
    registry.register(OpenUrlTool())
    registry.register(WebSearchTool())

    # File tools
    registry.register(ListFilesTool())
    registry.register(SearchFilesTool())
    registry.register(ReadTextFileTool())
    registry.register(CreateFileTool())

    return registry


# Run setup on import
setup_default_tools(default_registry)

__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolResult",
    "VerificationResult",
    "ToolRegistry",
    "default_registry",
    "audit_logger",
    "AuditEntry",
    "permissions_manager",
    "PendingAction",
    "setup_default_tools",
]
