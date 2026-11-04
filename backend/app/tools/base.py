"""
NOVA Safe Tools Framework - Base Classes & Schema
Provides typed, bounded, allowlisted tool interface with post-action verification,
cancellation support, and tiered risk classification.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Tiered risk levels for allowlisted tools."""
    READ_ONLY = "READ_ONLY"                   # No state changes (e.g. system info, read file, list dir)
    LOW_RISK = "LOW_RISK"                     # Safe changes without destruction (e.g. open URL, launch app)
    HIGH_RISK = "HIGH_RISK_CONFIRMATION"      # File creation, overwrite, or modification (requires confirmation)


class ToolParamSchema(BaseModel):
    """Schema descriptor for a tool parameter."""
    name: str
    type: str = "string"                      # string, integer, boolean, float
    description: str
    required: bool = True
    default: Optional[Any] = None
    choices: Optional[List[str]] = None


class VerificationResult(BaseModel):
    """Post-action verification details confirming actual execution on the system."""
    verified: bool
    method: str
    details: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Structured result returned by every safe tool execution."""
    tool_name: str
    success: bool
    output: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    verification: Optional[VerificationResult] = None
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    confirmation_prompt: Optional[str] = None


class BaseTool(ABC):
    """
    Abstract base class for all safe, allowlisted NOVA tools.
    Every tool must declare its category, risk level, parameter schemas,
    execution logic, and post-action verification check.
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        risk_level: RiskLevel = RiskLevel.READ_ONLY,
    ):
        self.name = name
        self.description = description
        self.category = category
        self.risk_level = risk_level

    @abstractmethod
    def get_parameters_schema(self) -> List[ToolParamSchema]:
        """Return list of typed parameter schemas for this tool."""
        pass

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool action within bounded arguments and return ToolResult."""
        pass

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        """
        Verify that the action actually took effect on the operating system.
        Can be overridden by subclasses for domain-specific checks.
        """
        return VerificationResult(
            verified=result.success,
            method="default_check",
            details="Execution status verified by tool return code."
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tool definition for frontend catalog and API."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "risk_level": self.risk_level.value,
            "parameters": [p.model_dump() for p in self.get_parameters_schema()],
        }
