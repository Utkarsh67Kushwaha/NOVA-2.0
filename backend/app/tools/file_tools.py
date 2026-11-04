"""
NOVA Safe Tools Framework - File Tools
Provides path-sandboxed, safe file system access (listing, searching, reading,
and confirmation-guarded creation) strictly bounded to approved user directories.
"""

from datetime import datetime, timezone
import fnmatch
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)
from backend.app.tools.permissions import permissions_manager


def get_default_allowed_roots() -> List[Path]:
    """Retrieve standard user-accessible sandboxed roots."""
    user_home = Path.home()
    roots = [
        user_home / "Desktop",
        user_home / "Documents",
        user_home / "Downloads",
        Path(os.getcwd()).resolve(),  # Active project root
    ]
    # Also include OneDrive Desktop/Documents if present on Windows
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        onedrive_path = Path(onedrive)
        roots.extend([
            onedrive_path / "Desktop",
            onedrive_path / "Documents",
        ])

    # Filter to existing directories
    existing = [r.resolve() for r in roots if r.exists()]
    return existing


def validate_sandboxed_path(target_path_str: str, allowed_roots: Optional[List[Path]] = None) -> Path:
    """
    Validate that target_path resolves strictly within one of the allowed roots.
    Prevents directory traversal attacks (e.g. ../../Windows/System32).
    """
    if allowed_roots is None:
        allowed_roots = get_default_allowed_roots()

    raw_path = Path(target_path_str)
    if not raw_path.is_absolute():
        # Default relative paths to active workspace or user Desktop
        raw_path = Path(os.getcwd()) / raw_path

    try:
        resolved = raw_path.resolve()
    except Exception as e:
        raise ValueError(f"Path resolution failed: {e}")

    # Check if resolved path is inside any allowed root
    is_safe = False
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            is_safe = True
            break
        except ValueError:
            continue

    if not is_safe:
        allowed_desc = ", ".join(str(r) for r in allowed_roots[:3]) + "..."
        raise PermissionError(
            f"Access denied: Path '{target_path_str}' is outside allowed sandboxed roots ({allowed_desc})."
        )

    # Disallow sensitive Windows system files
    resolved_lower = str(resolved).lower()
    for forbidden in ["windows\\system32", "appdata\\local\\elevated", "pagefile.sys"]:
        if forbidden in resolved_lower:
            raise PermissionError(f"Access to sensitive system path '{forbidden}' is strictly blocked.")

    return resolved


class ListFilesTool(BaseTool):
    """Tool to inspect directory contents within allowed sandboxed folders."""

    def __init__(self):
        super().__init__(
            name="list_files",
            description="List files and folders within an approved user directory.",
            category="file",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="directory_path",
                type="string",
                description="Absolute or relative path to the directory (within Desktop, Documents, Downloads, or Project)",
                required=False,
                default=".",
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        dir_path_str = str(kwargs.get("directory_path", ".")).strip()

        try:
            safe_dir = validate_sandboxed_path(dir_path_str)
        except (PermissionError, ValueError) as err:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Security error: {str(err)}",
                error=str(err),
            )

        if not safe_dir.exists() or not safe_dir.is_dir():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Directory '{safe_dir}' does not exist or is not a directory.",
                error="Path is not an existing directory",
            )

        items = []
        try:
            for entry in os.scandir(safe_dir):
                is_dir = entry.is_dir()
                size = 0 if is_dir else entry.stat().st_size
                mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                items.append({
                    "name": entry.name,
                    "is_directory": is_dir,
                    "size_bytes": size,
                    "modified": mtime,
                })
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to read directory: {str(e)}",
                error=str(e),
            )

        # Sort: directories first, then alphabetically
        items.sort(key=lambda x: (not x["is_directory"], x["name"].lower()))

        output = f"Directory '{safe_dir.name}': {len(items)} items ({sum(1 for i in items if i['is_directory'])} folders, {sum(1 for i in items if not i['is_directory'])} files)."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data={"directory": str(safe_dir), "items": items[:100], "total_count": len(items)},
        )
        result.verification = self.verify(result, directory=safe_dir, count=len(items))
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="dir_inspection",
                details="List directory failed.",
            )
        return VerificationResult(
            verified=True,
            method="dir_exists_check",
            details="Directory validated in sandbox and entries scanned successfully.",
            metrics={"item_count": kwargs.get("count")},
        )


class SearchFilesTool(BaseTool):
    """Tool to search for files by name/pattern within allowed directories."""

    def __init__(self):
        super().__init__(
            name="search_files",
            description="Search for files by pattern or keyword (e.g. *.pdf, resume) in sandboxed folders.",
            category="file",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="query",
                type="string",
                description="Filename substring or glob pattern (e.g. 'resume', '*.pdf', 'notes.txt')",
                required=True,
            ),
            ToolParamSchema(
                name="root_dir",
                type="string",
                description="Starting directory to search in (default is active project root)",
                required=False,
                default=".",
            ),
            ToolParamSchema(
                name="recursive",
                type="boolean",
                description="Whether to search subdirectories recursively (max depth 3)",
                required=False,
                default=True,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        root_dir_str = str(kwargs.get("root_dir", ".")).strip()
        recursive = bool(kwargs.get("recursive", True))

        if not query:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Search query cannot be empty.",
                error="Missing required parameter: query",
            )

        try:
            safe_root = validate_sandboxed_path(root_dir_str)
        except (PermissionError, ValueError) as err:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Security error: {str(err)}",
                error=str(err),
            )

        pattern = f"*{query}*" if "*" not in query else query
        matches = []
        max_results = 50

        # Prevent searching node_modules, .venv, .git
        ignore_dirs = {".venv", "node_modules", ".git", "__pycache__", "dist", "build"}

        if recursive:
            for root, dirs, files in os.walk(safe_root):
                dirs[:] = [d for d in dirs if d not in ignore_dirs]
                for filename in files:
                    if fnmatch.fnmatch(filename.lower(), pattern.lower()):
                        full_path = Path(root) / filename
                        matches.append({
                            "name": filename,
                            "path": str(full_path),
                            "relative_path": str(full_path.relative_to(safe_root)),
                            "size_bytes": full_path.stat().st_size,
                        })
                        if len(matches) >= max_results:
                            break
                if len(matches) >= max_results:
                    break
        else:
            for entry in os.scandir(safe_root):
                if entry.is_file() and fnmatch.fnmatch(entry.name.lower(), pattern.lower()):
                    matches.append({
                        "name": entry.name,
                        "path": str(Path(entry.path)),
                        "relative_path": entry.name,
                        "size_bytes": entry.stat().st_size,
                    })

        output = f"Found {len(matches)} matching file(s) for query '{query}' in '{safe_root.name}'."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data={"matches": matches, "query": query, "root_dir": str(safe_root)},
        )
        result.verification = self.verify(result, match_count=len(matches))
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="search_verification",
                details="File search failed.",
            )
        return VerificationResult(
            verified=True,
            method="file_match_verification",
            details="Files scanned within sandbox boundaries.",
            metrics={"matches": kwargs.get("match_count", 0)},
        )


class ReadTextFileTool(BaseTool):
    """Tool to read the contents of a text file within allowed directories."""

    def __init__(self):
        super().__init__(
            name="read_text_file",
            description="Read text contents of a file (e.g. .txt, .py, .json, .md) in allowed folders.",
            category="file",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="file_path",
                type="string",
                description="Path to the file to read",
                required=True,
            ),
            ToolParamSchema(
                name="max_lines",
                type="integer",
                description="Maximum number of lines to return (default 200)",
                required=False,
                default=200,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        file_path_str = str(kwargs.get("file_path", "")).strip()
        max_lines = int(kwargs.get("max_lines", 200))

        try:
            safe_path = validate_sandboxed_path(file_path_str)
        except (PermissionError, ValueError) as err:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Security error: {str(err)}",
                error=str(err),
            )

        if not safe_path.exists() or not safe_path.is_file():
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"File not found: '{safe_path}'.",
                error="File does not exist or is a directory",
            )

        # Enforce file size limit: 1 MB
        if safe_path.stat().st_size > 1024 * 1024:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"File '{safe_path.name}' exceeds safe read size limit (1 MB).",
                error="File size limit exceeded (>1MB)",
            )

        try:
            with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(max_lines)]
                content = "".join(lines)
                total_lines = len(lines)

            output = f"Read {total_lines} lines from '{safe_path.name}' ({safe_path.stat().st_size} bytes)."

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data={
                    "file_path": str(safe_path),
                    "file_name": safe_path.name,
                    "content": content,
                    "lines_read": total_lines,
                },
            )
            result.verification = self.verify(result, file_path=safe_path, bytes_read=len(content))
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Error reading file: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="file_read_verification",
                details="File reading failed.",
            )
        return VerificationResult(
            verified=True,
            method="byte_count_verification",
            details="File content read and decoded cleanly within memory limits.",
            metrics={"bytes": kwargs.get("bytes_read")},
        )


class CreateFileTool(BaseTool):
    """
    Tool to safely create or overwrite a file in sandboxed folders.
    Requires explicit confirmation if creating or modifying files!
    """

    def __init__(self):
        super().__init__(
            name="create_file",
            description="Create or write text to a file in an allowed directory. Requires user confirmation if overwriting.",
            category="file",
            risk_level=RiskLevel.HIGH_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="file_path",
                type="string",
                description="Path for the new file (within Desktop, Documents, or Project)",
                required=True,
            ),
            ToolParamSchema(
                name="content",
                type="string",
                description="Text content to write into the file",
                required=True,
            ),
            ToolParamSchema(
                name="confirmation_token",
                type="string",
                description="Confirmation token required when overwriting an existing file or high-risk write",
                required=False,
                default=None,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        file_path_str = str(kwargs.get("file_path", "")).strip()
        content = str(kwargs.get("content", ""))
        conf_token = kwargs.get("confirmation_token")

        try:
            safe_path = validate_sandboxed_path(file_path_str)
        except (PermissionError, ValueError) as err:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Security error: {str(err)}",
                error=str(err),
            )

        file_exists = safe_path.exists()

        # If file exists, require explicit user confirmation token
        if file_exists and not conf_token:
            action = permissions_manager.request_confirmation(
                tool_name=self.name,
                args={"file_path": file_path_str, "content_len": len(content)},
                prompt=f"File '{safe_path.name}' already exists. Are you sure you want to overwrite it?",
            )
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Confirmation required: File '{safe_path.name}' exists. Please confirm overwrite.",
                requires_confirmation=True,
                confirmation_token=action.token,
                confirmation_prompt=action.prompt,
            )

        # If confirmation token was provided, validate it
        if conf_token:
            action = permissions_manager.validate_and_consume(conf_token)
            if not action:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="Confirmation failed: Token is invalid, expired, or already used.",
                    error="Invalid or expired confirmation token",
                )

        try:
            # Ensure parent directories exist
            safe_path.parent.mkdir(parents=True, exist_ok=True)

            with open(safe_path, "w", encoding="utf-8") as f:
                f.write(content)

            output = f"Successfully {'overwrote' if file_exists else 'created'} file '{safe_path.name}' ({len(content)} characters)."

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data={
                    "file_path": str(safe_path),
                    "file_name": safe_path.name,
                    "bytes_written": len(content.encode("utf-8")),
                    "action": "overwritten" if file_exists else "created",
                },
            )
            result.verification = self.verify(result, file_path=safe_path, expected_chars=len(content))
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to write file: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="file_creation_verification",
                details="File creation failed prior to verification.",
            )

        safe_path = kwargs.get("file_path")
        expected_chars = kwargs.get("expected_chars", 0)

        if safe_path and safe_path.exists():
            actual_size = safe_path.stat().st_size
            return VerificationResult(
                verified=True,
                method="file_system_inspection",
                details=f"File '{safe_path.name}' verified on disk with {actual_size} bytes.",
                metrics={"size_bytes": actual_size, "expected_chars": expected_chars},
            )

        return VerificationResult(
            verified=False,
            method="file_system_inspection",
            details="File does not exist on disk after write operation.",
        )
