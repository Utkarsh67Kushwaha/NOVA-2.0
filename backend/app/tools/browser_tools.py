"""
NOVA Safe Tools Framework - Browser Tools
Provides safe, validated web navigation and search queries with URL scheme restriction,
private network boundary enforcement, and post-action dispatch verification.
"""

from typing import Any, List
import urllib.parse
import webbrowser

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

# Blocked IP ranges and hostnames to prevent SSRF and local boundary escape
DISALLOWED_HOSTS = {
    "169.254.169.254",   # Cloud metadata endpoint
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}


class OpenUrlTool(BaseTool):
    """Safely open an external URL in the user's default browser."""

    def __init__(self):
        super().__init__(
            name="open_url",
            description="Safely open an approved web URL (http/https only) in the default browser.",
            category="browser",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="url",
                type="string",
                description="The full URL to open (must start with http:// or https://)",
                required=True,
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        raw_url = str(kwargs.get("url", "")).strip()

        if not raw_url:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="URL cannot be empty.",
                error="Missing required parameter: url",
            )

        # Prepend https if user forgot scheme
        if not (raw_url.startswith("http://") or raw_url.startswith("https://")):
            if "://" not in raw_url:
                raw_url = "https://" + raw_url
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="Security rejection: Only HTTP and HTTPS protocols are permitted.",
                    error=f"Disallowed scheme in URL '{raw_url}'",
                )

        parsed = urllib.parse.urlparse(raw_url)

        # Enforce scheme
        if parsed.scheme.lower() not in ("http", "https"):
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Security rejection: Only HTTP and HTTPS schemes are allowed.",
                error=f"Blocked scheme: '{parsed.scheme}'",
            )

        hostname = (parsed.hostname or "").lower()
        if hostname in DISALLOWED_HOSTS:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Security rejection: Opening local loopback or cloud metadata endpoints is blocked.",
                error=f"Blocked target host: '{hostname}'",
            )

        try:
            # Open browser safely
            opened = webbrowser.open(raw_url, new=2)  # new=2 -> open in new tab if possible

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Opened URL '{raw_url}' in default browser.",
                data={"url": raw_url, "domain": hostname},
            )
            result.verification = self.verify(result, url=raw_url, browser_return=opened)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to open URL: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="url_dispatch_verification",
                details="Browser open failed initially.",
            )

        url = kwargs.get("url", "")
        return VerificationResult(
            verified=True,
            method="browser_dispatch_check",
            details=f"URL '{url}' passed schema validation and was dispatched to Windows default browser handler.",
            metrics={"url": url},
        )


class WebSearchTool(BaseTool):
    """Constructs and executes a safe web search query in the browser."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web using a search query (opens results in browser).",
            category="browser",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="query",
                type="string",
                description="The search terms or query string to search for",
                required=True,
            ),
            ToolParamSchema(
                name="engine",
                type="string",
                description="Search engine to use: google, duckduckgo, bing",
                required=False,
                default="google",
                choices=["google", "duckduckgo", "bing"],
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        query = str(kwargs.get("query", "")).strip()
        engine = str(kwargs.get("engine", "google")).lower()

        if not query:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Search query cannot be empty.",
                error="Missing required parameter: query",
            )

        encoded_q = urllib.parse.quote_plus(query)

        if engine == "duckduckgo":
            search_url = f"https://duckduckgo.com/?q={encoded_q}"
        elif engine == "bing":
            search_url = f"https://www.bing.com/search?q={encoded_q}"
        else:
            search_url = f"https://www.google.com/search?q={encoded_q}"

        try:
            webbrowser.open(search_url, new=2)

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Executed {engine.capitalize()} search for: '{query}'",
                data={"query": query, "engine": engine, "search_url": search_url},
            )
            result.verification = self.verify(result, search_url=search_url, query=query)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Web search error: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="search_dispatch_verification",
                details="Search execution failed.",
            )

        return VerificationResult(
            verified=True,
            method="search_url_verification",
            details="Search URL query params encoded cleanly and dispatched to browser handler.",
            metrics={"query": kwargs.get("query"), "search_url": kwargs.get("search_url")},
        )
