"""
NOVA Safe Tools Framework - Document & Code Content Analysis Tool
Reads workspace files (markdown, python, json, text) safely within sandbox
and passes them to Gemini 3.8 Flash for intelligent summaries, explanations, or bug reviews.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.services.gemini_service import gemini_service
from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.doc_analysis")


class DocAnalysisTool(BaseTool):
    """Safely analyzes and explains local documents, codebases, and text files using Gemini 3.8 Flash."""

    def __init__(self, workspace_root: Optional[Path] = None):
        super().__init__(
            name="analyze_document",
            description="Reads and provides intelligent summaries, explanations, or bug reviews for a workspace file.",
            category="file",
            risk_level=RiskLevel.READ_ONLY,
        )
        self.workspace_root = workspace_root or Path(__file__).resolve().parent.parent.parent.parent

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="file_path",
                type="string",
                description="Relative path of the file to inspect (e.g. 'README.md', 'CLAUDE.md', 'backend/app/main.py').",
                required=True,
            ),
            ToolParamSchema(
                name="prompt",
                type="string",
                description="Analysis request (e.g. 'summarize key points', 'review code for bugs', 'explain what this file does').",
                required=False,
                default="Summarize this file and explain its main purpose.",
            ),
        ]

    def _resolve_safe_path(self, relative_path: str) -> Optional[Path]:
        """Ensures file is inside allowed workspace root without path traversal."""
        try:
            target = (self.workspace_root / relative_path).resolve()
            if self.workspace_root.resolve() in target.parents or target == self.workspace_root.resolve():
                return target if target.is_file() else None
            return None
        except Exception:
            return None

    def execute(self, **kwargs: Any) -> ToolResult:
        rel_path = str(kwargs.get("file_path", "")).strip()
        user_prompt = str(kwargs.get("prompt", "Summarize this file and explain its main purpose.")).strip()

        if not rel_path:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="File path cannot be empty.",
                error="Missing file_path parameter",
            )

        resolved_file = self._resolve_safe_path(rel_path)
        if not resolved_file:
            # Try searching by basename if user just said "README.md" or "main.py"
            found = list(self.workspace_root.glob(f"**/{rel_path}"))
            if found and found[0].is_file():
                resolved_file = found[0]

        if not resolved_file or not resolved_file.exists():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"File '{rel_path}' not found in workspace.",
                error="FileNotFoundError",
            )

        try:
            content = resolved_file.read_text(encoding="utf-8", errors="replace")
            # Truncate to first 6,000 characters to keep latency fast
            snippet = content[:6000]

            query_for_ai = (
                f"File: {resolved_file.name}\n"
                f"Content Snippet:\n{snippet}\n\n"
                f"Instruction: {user_prompt}\n"
                f"Provide a concise, direct 2-3 sentence answer suitable for text-to-speech."
            )

            analysis = gemini_service.ask(query_for_ai)

            return ToolResult(
                tool_name=self.name,
                success=True,
                output=analysis,
                data={
                    "file_name": resolved_file.name,
                    "file_size": len(content),
                    "prompt": user_prompt,
                },
                verification=VerificationResult(
                    verified=True,
                    method="gemini_file_analysis",
                    details=f"Analyzed {resolved_file.name} successfully.",
                ),
            )
        except Exception as exc:
            logger.error("Failed to analyze file %s: %s", rel_path, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Error reading or analyzing '{rel_path}': {exc}",
                error=str(exc),
            )
