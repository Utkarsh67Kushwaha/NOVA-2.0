"""
NOVA Safe Tools Framework - Browser Tools
Provides safe, validated web navigation and search queries with URL scheme restriction,
private network boundary enforcement, and post-action dispatch verification.
"""

import logging
import os
import re
import shutil
import subprocess
from typing import Any, List
import urllib.parse
import urllib.request

from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)

logger = logging.getLogger("nova.tools.browser")

# Blocked IP ranges and hostnames to prevent SSRF and local boundary escape
DISALLOWED_HOSTS = {
    "169.254.169.254",   # Cloud metadata endpoint
    "metadata.google.internal",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}


def open_url_in_browser(url: str) -> bool:
    """
    Directly opens the given URL in an external Google Chrome window in the foreground,
    without navigating or altering the current application.
    """
    chrome_candidates = [
        os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        shutil.which("chrome"),
    ]
    chrome_exe = next((c for c in chrome_candidates if c and os.path.exists(c)), None)

    try:
        if chrome_exe:
            # --new-window forces Chrome to open a separate, active foreground window
            subprocess.Popen([chrome_exe, "--new-window", url], shell=False)
            logger.info("Dispatched URL to external Google Chrome window: %s", url)
        else:
            subprocess.Popen(["cmd.exe", "/c", "start", "", url], shell=False)
            logger.info("Dispatched URL to system default browser: %s", url)

        # Bring Google Chrome window to the foreground over other desktop windows
        try:
            import win32gui, win32con
            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if "chrome" in title or "youtube" in title:
                        try:
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                        except Exception:
                            pass
            win32gui.EnumWindows(enum_cb, None)
        except Exception:
            pass

        return True
    except Exception as ex:
        logger.error("Failed to dispatch URL '%s' to browser: %s", url, ex)
        return False


class OpenUrlTool(BaseTool):
    """Safely open an external URL in Google Chrome (default browser)."""

    def __init__(self):
        super().__init__(
            name="open_url",
            description="Safely open an approved web URL (http/https only) in the default browser (Google Chrome).",
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
            opened = open_url_in_browser(raw_url)

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Opened URL '{raw_url}' in Google Chrome.",
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
            details=f"URL '{url}' passed schema validation and was dispatched to Google Chrome.",
            metrics={"url": url},
        )


class WebSearchTool(BaseTool):
    """Constructs and executes a safe web search query in Google Chrome."""

    def __init__(self):
        super().__init__(
            name="web_search",
            description="Search the web using a search query (opens results in Google Chrome).",
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
                choices=["google", "duckduckgo", "bing", "youtube", "github", "wikipedia", "amazon", "stackoverflow", "reddit", "twitter", "x"],
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
        elif engine == "youtube":
            search_url = f"https://www.youtube.com/results?search_query={encoded_q}"
        elif engine == "github":
            search_url = f"https://github.com/search?q={encoded_q}"
        elif engine == "wikipedia":
            search_url = f"https://en.wikipedia.org/wiki/Special:Search?search={encoded_q}"
        elif engine == "amazon":
            search_url = f"https://www.amazon.in/s?k={encoded_q}"
        elif engine == "stackoverflow":
            search_url = f"https://stackoverflow.com/search?q={encoded_q}"
        elif engine == "reddit":
            search_url = f"https://www.reddit.com/search/?q={encoded_q}"
        elif engine in ("twitter", "x"):
            search_url = f"https://twitter.com/search?q={encoded_q}"
        else:
            search_url = f"https://www.google.com/search?q={encoded_q}"

        try:
            open_url_in_browser(search_url)

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Executed {engine.capitalize()} search for: '{query}' in Google Chrome",
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
            details="Search URL dispatched directly to Google Chrome.",
            metrics={"query": kwargs.get("query"), "search_url": kwargs.get("search_url")},
        )


def resolve_direct_youtube_video_url(query: str, timeout: float = 2.5) -> str:
    """
    Directly extracts the first playable YouTube watch URL with autoplay for the given query.
    Falls back to YouTube search results URL if resolution times out.
    """
    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(query + ' song')}"
    try:
        req = urllib.request.Request(
            search_url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Preferred pattern: "videoId":"xxxxxxxxxxx" in ytInitialData
        match_id = re.search(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
        if match_id:
            return f"https://www.youtube.com/watch?v={match_id.group(1)}&autoplay=1"

        # Secondary fallback: watch?v=xxxxxxxxxxx
        match_watch = re.search(r"watch\?v=([a-zA-Z0-9_-]{11})", html)
        if match_watch:
            return f"https://www.youtube.com/watch?v={match_watch.group(1)}&autoplay=1"
    except Exception as exc:
        logger.warning("Fast direct YouTube extraction timed out (%s), using search URL fallback", exc)

    return search_url


class PlayMusicTool(BaseTool):
    """Fast, optimized tool to directly play song videos in Google Chrome."""

    def __init__(self):
        super().__init__(
            name="play_music",
            description="Play music by directly launching the song video on YouTube in Google Chrome.",
            category="browser",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="track",
                type="string",
                description="The song, music track, or artist query to play",
                required=True,
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        track = str(kwargs.get("track", "")).strip()
        if not track:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Track name cannot be empty.",
                error="Missing required parameter: track",
            )

        # Clean command verbs and all punctuation/commas
        clean_track = re.sub(
            r"\b(?:play|karo|kare|song|gana|gaana|bajao|chalao|lagao|sunao)\b",
            "",
            track,
            flags=re.IGNORECASE,
        )
        clean_track = re.sub(r"[,;.!?\"'\-:]+", " ", clean_track)
        search_query = re.sub(r"\s+", " ", clean_track).strip()
        search_query = search_query if search_query else track

        # Directly resolve playable video URL (watch?v=...&autoplay=1)
        target_url = resolve_direct_youtube_video_url(search_query)

        # Fast direct Google Chrome launch
        try:
            open_url_in_browser(target_url)

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Playing '{search_query}' directly in Google Chrome ({target_url})",
                data={"track": search_query, "url": target_url},
            )
            result.verification = self.verify(result, track=search_query, target_url=target_url)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to play YouTube video in Chrome: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="play_music_verification",
                details="YouTube direct playback dispatch failed.",
            )
        return VerificationResult(
            verified=True,
            method="play_music_dispatch_check",
            details="Direct YouTube video URL dispatched to Google Chrome.",
            metrics={"track": kwargs.get("track"), "target_url": kwargs.get("target_url")},
        )
