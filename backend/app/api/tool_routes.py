"""
NOVA Safe Tools API Routes
Provides REST API endpoints for tool discovery, safe execution,
audit log queries, and sensitive operation confirmation.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.tools import (
    default_registry,
    audit_logger,
    permissions_manager,
    ToolResult,
)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolExecuteRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = Field(default_factory=dict)
    confirmation_token: Optional[str] = None


class ToolConfirmRequest(BaseModel):
    token: str


@router.get("", summary="List all allowlisted safe tools")
def list_tools() -> Dict[str, Any]:
    """Return all registered allowlisted tools, schemas, and risk tiers."""
    tools = default_registry.list_tools()
    return {
        "status": "success",
        "count": len(tools),
        "tools": tools,
    }


@router.post("/execute", summary="Execute an allowlisted tool safely")
def execute_tool(req: ToolExecuteRequest) -> Dict[str, Any]:
    """Execute a tool with parameter validation, audit logging, and verification."""
    result: ToolResult = default_registry.execute(
        tool_name=req.tool_name,
        args=req.args,
        confirmed_token=req.confirmation_token,
    )
    return {
        "status": "success" if result.success else "failed",
        "result": result.model_dump(),
    }


@router.get("/audit", summary="Get recent tool audit history")
def get_audit_log(limit: int = 50) -> Dict[str, Any]:
    """Retrieve chronologically ordered recent tool execution audit trail."""
    entries = audit_logger.get_entries(limit=limit)
    return {
        "status": "success",
        "count": len(entries),
        "entries": [e.model_dump() for e in entries],
    }


@router.post("/confirm", summary="Confirm and execute a pending high-risk action")
def confirm_action(req: ToolConfirmRequest) -> Dict[str, Any]:
    """Confirm a sensitive action using its one-time authorization token."""
    action = permissions_manager.get_pending(req.token)
    if not action:
        raise HTTPException(status_code=400, detail="Invalid, expired, or already consumed confirmation token.")

    # Execute tool with confirmed token
    result = default_registry.execute(
        tool_name=action.tool_name,
        args=action.args,
        confirmed_token=req.token,
    )
    return {
        "status": "success" if result.success else "failed",
        "result": result.model_dump(),
    }


@router.post("/reject", summary="Reject and cancel a pending high-risk action")
def reject_action(req: ToolConfirmRequest) -> Dict[str, Any]:
    """Reject and revoke a pending confirmation token."""
    revoked = permissions_manager.reject(req.token)
    if not revoked:
        raise HTTPException(status_code=400, detail="Token not found or already consumed.")
    return {
        "status": "success",
        "message": "Action successfully rejected and revoked.",
    }
