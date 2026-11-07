"""
NOVA Safe Tools Framework - Document & Code Content Analysis Tool
Reads workspace files (markdown, python, json, text) safely within sandbox
and passes them to Gemini 3.8 Flash for intelligent summaries, explanations, or bug reviews.
Includes smart offline heuristic fallback if Gemini is offline or unconfigured.
"""

from __future__ import annotations

import logging
from pathlib import Path
import re
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

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

BINARY_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".bin",
    ".pyc",
    ".mp3",
    ".mp4",
    ".wav",
}


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

    def _find_file_in_workspace(self, file_name: str) -> Optional[Path]:
        """Searches workspace root excluding virtualenvs, git, and node_modules."""
        base_name = Path(file_name).name.lower()
        for root_dir, dirs, files in self._walk_safe():
            for f in files:
                if f.lower() == base_name:
                    return Path(root_dir) / f
        return None

    def _walk_safe(self):
        """Walks workspace tree skipping ignored directories."""
        import os

        for root, dirs, files in os.walk(self.workspace_root):
            # Mutate dirs in-place to avoid traversing into ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".")]
            yield root, dirs, files

    def _generate_offline_summary(self, file_path: Path, content: str) -> str:
        """Heuristic summary when Gemini is offline or unconfigured."""
        lines = content.splitlines()
        line_count = len(lines)
        size_kb = round(len(content) / 1024, 1)
        ext = file_path.suffix.lower()

        components: List[str] = []
        if ext in (".py", ".pyw"):
            funcs = re.findall(r"^\s*def\s+([a-zA-Z_]\w*)", content, re.MULTILINE)
            classes = re.findall(r"^\s*class\s+([a-zA-Z_]\w*)", content, re.MULTILINE)
            if classes:
                components.append(f"Classes: {', '.join(classes[:3])}")
            if funcs:
                components.append(f"Functions: {', '.join(funcs[:4])}")
        elif ext in (".md", ".txt"):
            headers = re.findall(r"^\s*#+\s+(.+)$", content, re.MULTILINE)
            if headers:
                components.append(f"Sections: {', '.join(headers[:3])}")
        elif ext == ".json":
            keys = re.findall(r'"([a-zA-Z0-9_\-]+)"\s*:', content)
            if keys:
                components.append(f"Keys: {', '.join(list(dict.fromkeys(keys))[:4])}")

        comp_str = f" Highlights: {'; '.join(components)}." if components else ""
        return (
            f"{file_path.name} ek {ext or 'text'} file hai jisme {line_count} lines ({size_kb} KB) hain.{comp_str} "
            f"(Local Offline Analysis)"
        )

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
            # Search by basename in workspace excluding node_modules / venv
            resolved_file = self._find_file_in_workspace(rel_path)

        if not resolved_file or not resolved_file.exists():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"File '{rel_path}' workspace me nahi mili.",
                error="FileNotFoundError",
            )

        ext = resolved_file.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"'{resolved_file.name}' binary/media file hai. Document analysis sirf text aur code files (.py, .md, .json, .ts, .txt, etc.) support karta hai.",
                error="UnsupportedBinaryFile",
            )

        try:
            # Read first 8,000 characters safely without reading huge files entirely into memory
            with open(resolved_file, "r", encoding="utf-8", errors="replace") as f:
                snippet = f.read(8000)

            # Check if Gemini is configured and accessible
            if gemini_service.is_configured():
                lang_tag = ext.lstrip(".") or "text"
                query_for_ai = (
                    f"File: {resolved_file.name} ({lang_tag})\n\n"
                    f"```{lang_tag}\n{snippet}\n```\n\n"
                    f"Instruction: {user_prompt}\n"
                    f"Provide a concise, clear 2-3 sentence summary suitable for text-to-speech."
                )
                try:
                    analysis = gemini_service.ask(query_for_ai)
                    method_used = "gemini_3.8_flash_analysis"
                except Exception as g_err:
                    logger.warning("Gemini ask failed, using offline fallback: %s", g_err)
                    analysis = self._generate_offline_summary(resolved_file, snippet)
                    method_used = "offline_heuristic_fallback"
            else:
                analysis = self._generate_offline_summary(resolved_file, snippet)
                method_used = "offline_heuristic_fallback"

            return ToolResult(
                tool_name=self.name,
                success=True,
                output=analysis,
                data={
                    "file_name": resolved_file.name,
                    "file_path": str(resolved_file.relative_to(self.workspace_root))
                    if resolved_file.is_relative_to(self.workspace_root)
                    else resolved_file.name,
                    "prompt": user_prompt,
                    "method": method_used,
                },
                verification=VerificationResult(
                    verified=True,
                    method=method_used,
                    details=f"Analyzed {resolved_file.name} via {method_used}.",
                ),
            )
        except Exception as exc:
            logger.error("Failed to read or analyze file %s: %s", rel_path, exc)
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Error reading or analyzing '{rel_path}': {exc}",
                error=str(exc),
            )
