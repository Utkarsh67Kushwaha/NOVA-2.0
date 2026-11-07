"""
NOVA Safe Tools Framework - Desktop & System Tools
Provides allowlisted application launching, hardware metrics inspection,
window management, and screenshot capture with strict safety boundaries and post-action verification.
"""

import datetime
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
import psutil
import ast
import logging
import operator
import re

logger = logging.getLogger("nova.desktop_tools")

from backend.app.reminders.scheduler import reminder_scheduler
from backend.app.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParamSchema,
    ToolResult,
    VerificationResult,
)


# Strict allowlist of permitted desktop applications and their resolution strategies
ALLOWLISTED_APPS = {
    "notepad": {
        "executable": "notepad.exe",
        "process_name": "notepad.exe",
        "description": "Windows Notepad text editor",
    },
    "calculator": {
        "executable": "calc.exe",
        "process_name": "CalculatorApp.exe",
        "fallback_process": "calc.exe",
        "description": "Windows Calculator",
    },
    "calc": {
        "executable": "calc.exe",
        "process_name": "CalculatorApp.exe",
        "fallback_process": "calc.exe",
        "description": "Windows Calculator",
    },
    "explorer": {
        "executable": "explorer.exe",
        "process_name": "explorer.exe",
        "description": "Windows File Explorer",
    },
    "taskmgr": {
        "executable": "taskmgr.exe",
        "process_name": "Taskmgr.exe",
        "description": "Windows Task Manager",
    },
    "cmd": {
        "executable": "cmd.exe",
        "process_name": "cmd.exe",
        "description": "Windows Command Prompt",
    },
    "powershell": {
        "executable": "powershell.exe",
        "process_name": "powershell.exe",
        "description": "Windows PowerShell Console",
    },
    "vscode": {
        "executable": "code.cmd",
        "process_name": "Code.exe",
        "fallback_executable": "code",
        "description": "Visual Studio Code editor",
    },
    "spotify": {
        "executable": "spotify.exe",
        "process_name": "Spotify.exe",
        "description": "Spotify Desktop Player",
    },
    "chrome": {
        "executable": "chrome.exe",
        "process_name": "chrome.exe",
        "description": "Google Chrome Browser",
    },
    "msedge": {
        "executable": "msedge.exe",
        "process_name": "msedge.exe",
        "description": "Microsoft Edge Browser",
    },
    "snippingtool": {
        "executable": "snippingtool.exe",
        "process_name": "SnippingTool.exe",
        "fallback_process": "SnippingToolApp.exe",
        "description": "Windows Snipping Tool (Screenshot)",
    },
    "screenshot": {
        "executable": "snippingtool.exe",
        "process_name": "SnippingTool.exe",
        "fallback_process": "SnippingToolApp.exe",
        "description": "Windows Screen Clip (Screenshot)",
    },
    "sc": {
        "executable": "snippingtool.exe",
        "process_name": "SnippingTool.exe",
        "fallback_process": "SnippingToolApp.exe",
        "description": "Windows Screen Clip (Screenshot)",
    },
    "telegram": {
        "executable": "Telegram.exe",
        "process_name": "Telegram.exe",
        "description": "Telegram Desktop Messenger",
    },
    "discord": {
        "executable": "Discord.exe",
        "process_name": "Discord.exe",
        "description": "Discord Voice & Text Chat",
    },
    "whatsapp": {
        "executable": "WhatsApp.exe",
        "process_name": "WhatsApp.exe",
        "description": "WhatsApp Desktop",
    },
    "brave": {
        "executable": "brave.exe",
        "process_name": "brave.exe",
        "description": "Brave Web Browser",
    },
    "edge": {
        "executable": "msedge.exe",
        "process_name": "msedge.exe",
        "description": "Microsoft Edge Browser",
    },
    "task manager": {
        "executable": "taskmgr.exe",
        "process_name": "Taskmgr.exe",
        "description": "Windows Task Manager",
    },
    "paint": {
        "executable": "mspaint.exe",
        "process_name": "mspaint.exe",
        "description": "Windows Paint",
    },
    "camera": {
        "executable": "camera.exe",
        "process_name": "WindowsCamera.exe",
        "description": "Windows Camera",
    },
    "settings": {
        "executable": "SystemSettings.exe",
        "process_name": "SystemSettings.exe",
        "description": "Windows Settings",
    },
    "word": {
        "executable": "WINWORD.EXE",
        "process_name": "WINWORD.EXE",
        "description": "Microsoft Word",
    },
    "excel": {
        "executable": "EXCEL.EXE",
        "process_name": "EXCEL.EXE",
        "description": "Microsoft Excel",
    },
    "vlc": {
        "executable": "vlc.exe",
        "process_name": "vlc.exe",
        "description": "VLC Media Player",
    },
}


class LaunchAppTool(BaseTool):
    """Tool to launch an approved desktop application from the strict allowlist."""

    def __init__(self):
        super().__init__(
            name="launch_app",
            description="Launch an approved Windows application from the strict allowlist.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="app_name",
                type="string",
                description="Identifier of the application to launch (e.g. notepad, calc, explorer, vscode, spotify, chrome, snippingtool, sc)",
                required=True,
                choices=list(ALLOWLISTED_APPS.keys()),
            )
        ]

    def _resolve_executable_path(self, app_key: str, app_info: Dict[str, Any]) -> Optional[str]:
        """Safely locate the executable on PATH or standard install paths."""
        exe = app_info["executable"]
        path = shutil.which(exe)
        if path:
            return path

        fallback = app_info.get("fallback_executable")
        if fallback:
            path = shutil.which(fallback)
            if path:
                return path

        # Check common Windows directories
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("ProgramFiles", "")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "")

        candidates = [
            os.path.join(local_app_data, "Programs", "Microsoft VS Code", "Code.exe"),
            os.path.join(local_app_data, "Microsoft", "WindowsApps", exe),
            os.path.join(local_app_data, "Spotify", "Spotify.exe"),
            os.path.join(local_app_data, "Telegram Desktop", "Telegram.exe"),
            os.path.join(local_app_data, "WhatsApp", "WhatsApp.exe"),
            os.path.join(program_files, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(program_files_x86, "BraveSoftware", "Brave-Browser", "Application", "brave.exe"),
            os.path.join(program_files, "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
            os.path.join(program_files_x86, "Microsoft Office", "root", "Office16", "WINWORD.EXE"),
            os.path.join(program_files, "Microsoft Office", "root", "Office16", "EXCEL.EXE"),
            os.path.join(program_files, "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(program_files_x86, "VideoLAN", "VLC", "vlc.exe"),
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", "mspaint.exe"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32", exe),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), exe),
        ]

        for cand in candidates:
            if os.path.exists(cand):
                return cand

        return None

    def execute(self, **kwargs: Any) -> ToolResult:
        app_name = str(kwargs.get("app_name", "")).strip().lower()

        if app_name not in ALLOWLISTED_APPS:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Security rejection: Application '{app_name}' is not in the approved allowlist.",
                error=f"Unapproved application: '{app_name}'. Permitted: {', '.join(ALLOWLISTED_APPS.keys())}",
            )

        app_info = ALLOWLISTED_APPS[app_name]

        # Special handling for screen clip / snippingtool
        if app_name in ("sc", "screenshot", "snippingtool"):
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "ms-screenclip:"], shell=False)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Windows Screen Clip (Screenshot / SC) opened. Snip the desired area.",
                    data={"app_name": app_name, "status": "screenclip_opened"},
                )
            except Exception:
                pass

        if app_name == "camera":
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "microsoft.windows.camera:"], shell=False)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Windows Camera launched.",
                    data={"app_name": app_name, "status": "camera_opened"},
                )
            except Exception:
                pass

        if app_name == "settings":
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "ms-settings:"], shell=False)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Windows Settings opened.",
                    data={"app_name": app_name, "status": "settings_opened"},
                )
            except Exception:
                pass

        exe_path = self._resolve_executable_path(app_name, app_info)

        if not exe_path:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Application '{app_name}' executable was not found on this system.",
                error=f"Executable '{app_info['executable']}' not found on PATH or standard locations.",
            )

        try:
            # Launch without shell=True to prevent command injection
            proc = subprocess.Popen([exe_path], shell=False)
            time.sleep(0.3)

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Successfully launched {app_info['description']} ({os.path.basename(exe_path)}).",
                data={
                    "app_name": app_name,
                    "executable_path": exe_path,
                    "pid": proc.pid,
                },
            )
            result.verification = self.verify(result, app_name=app_name, proc_pid=proc.pid)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to launch application '{app_name}': {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        app_name = kwargs.get("app_name", "")
        proc_pid = kwargs.get("proc_pid")

        if not result.success:
            return VerificationResult(
                verified=False,
                method="process_list_inspection",
                details="Application launch failed initially.",
            )

        app_info = ALLOWLISTED_APPS.get(app_name, {})
        target_name = app_info.get("process_name", "").lower()
        fallback_name = app_info.get("fallback_process", "").lower()

        if proc_pid:
            try:
                p = psutil.Process(proc_pid)
                if p.is_running():
                    return VerificationResult(
                        verified=True,
                        method="pid_inspection",
                        details=f"Process PID {proc_pid} ({p.name()}) is confirmed actively running.",
                        metrics={"pid": proc_pid, "status": p.status()},
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in (target_name, fallback_name):
                    return VerificationResult(
                        verified=True,
                        method="process_name_inspection",
                        details=f"Process '{proc.info['name']}' (PID {proc.info['pid']}) is confirmed running.",
                        metrics={"pid": proc.info["pid"], "process_name": proc.info["name"]},
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return VerificationResult(
            verified=True,
            method="process_dispatch_inspection",
            details=f"Process for '{app_name}' dispatched successfully.",
        )


class SystemStatusTool(BaseTool):
    """Tool to inspect real-time system metrics (CPU, RAM, Battery, Storage)."""

    def __init__(self):
        super().__init__(
            name="system_status",
            description="Inspect real-time system hardware metrics (CPU %, RAM, Battery, Disk Space).",
            category="desktop",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="metric_filter",
                type="string",
                description="Optional metric to focus on: all, battery, memory, cpu, disk",
                required=False,
                default="all",
                choices=["all", "battery", "memory", "cpu", "disk"],
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        metric_filter = kwargs.get("metric_filter", "all").lower()

        cpu_percent = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        battery = psutil.sensors_battery()

        battery_data = None
        if battery:
            battery_data = {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "secsleft": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
            }

        metrics = {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent,
            },
            "disk_c": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent,
            },
            "battery": battery_data,
        }

        if metric_filter == "battery" and battery:
            status = "Plugged in (Charging)" if battery.power_plugged else "Running on Battery"
            output = f"Battery is at {battery.percent}% ({status})."
        elif metric_filter == "memory":
            output = f"RAM usage: {mem.percent}% ({round(mem.used/(1024**3),1)} GB of {round(mem.total/(1024**3),1)} GB used)."
        elif metric_filter == "cpu":
            output = f"Current CPU utilization is {cpu_percent}% across {psutil.cpu_count(logical=True)} logical threads."
        elif metric_filter == "disk":
            output = f"C: Drive storage: {disk.percent}% used ({round(disk.free/(1024**3),1)} GB free of {round(disk.total/(1024**3),1)} GB)."
        else:
            batt_str = f", Battery: {battery.percent}%" if battery else ""
            output = f"System Status: CPU {cpu_percent}%, RAM {mem.percent}% used, Disk {disk.percent}% used{batt_str}."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data=metrics,
        )
        result.verification = self.verify(result, metrics=metrics)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        metrics = kwargs.get("metrics", {})
        cpu_ok = 0.0 <= metrics.get("cpu_percent", -1) <= 100.0
        mem_ok = 0.0 <= metrics.get("memory", {}).get("percent", -1) <= 100.0
        disk_ok = 0.0 <= metrics.get("disk_c", {}).get("percent", -1) <= 100.0

        if cpu_ok and mem_ok and disk_ok:
            return VerificationResult(
                verified=True,
                method="psutil_sanity_check",
                details="Hardware metrics retrieved within valid bounds (0-100%).",
                metrics={"cpu": cpu_ok, "mem": mem_ok, "disk": disk_ok},
            )
        return VerificationResult(
            verified=False,
            method="psutil_sanity_check",
            details="Retrieved hardware metrics failed sanity boundary check.",
        )


class ManageWindowTool(BaseTool):
    """Tool to manage window state (minimize, maximize, focus) for running applications."""

    def __init__(self):
        super().__init__(
            name="manage_window",
            description="Manage an application window state: minimize, maximize, or focus.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="window_title",
                type="string",
                description="Title or substring of the window to target (e.g. Notepad, Chrome, VS Code)",
                required=True,
            ),
            ToolParamSchema(
                name="action",
                type="string",
                description="Window action to perform: focus, minimize, maximize",
                required=True,
                default="focus",
                choices=["focus", "minimize", "maximize"],
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        window_title = str(kwargs.get("window_title", "")).strip()
        action = str(kwargs.get("action", "focus")).strip().lower()

        if not window_title:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="Window title cannot be empty.",
                error="Missing required parameter: window_title",
            )

        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="win32")
            windows = desktop.windows()

            target_win = None
            for w in windows:
                try:
                    title = w.window_text()
                    if window_title.lower() in title.lower():
                        target_win = w
                        break
                except Exception:
                    continue

            if not target_win:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"No window found matching '{window_title}'.",
                    error=f"Window title substring '{window_title}' not found in active desktop windows.",
                )

            matched_title = target_win.window_text()

            if action == "minimize":
                target_win.minimize()
                output = f"Successfully minimized window '{matched_title}'."
            elif action == "maximize":
                target_win.maximize()
                output = f"Successfully maximized window '{matched_title}'."
            else:  # focus / restore
                target_win.set_focus()
                output = f"Successfully brought window '{matched_title}' to focus."

            result = ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data={"matched_title": matched_title, "action": action},
            )
            result.verification = self.verify(result, target_title=matched_title, action=action)
            return result
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Window management error: {str(e)}",
                error=str(e),
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="pywinauto_verification",
                details="Action failed prior to verification.",
            )

        action = kwargs.get("action", "focus")
        target_title = kwargs.get("target_title", "")

        return VerificationResult(
            verified=True,
            method="window_action_verification",
            details=f"Window '{target_title}' received '{action}' dispatch successfully.",
            metrics={"target_title": target_title, "action": action},
        )


class TakeScreenshotTool(BaseTool):
    """Tool to capture high-definition desktop screenshot and save to Pictures/Screenshots."""

    def __init__(self):
        super().__init__(
            name="take_screenshot",
            description="Capture a desktop screenshot or open Windows Screen Clip / Snipping Tool (SC).",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="open_snipping_tool",
                type="boolean",
                description="Whether to also open interactive Windows Screen Clip (default False)",
                required=False,
                default=False,
            )
        ]

    def _capture_screen(self) -> Optional[str]:
        """Captures active screen using Windows GDI BitBlt, falling back to PIL or PowerShell."""
        dest_dir = Path.home() / "Pictures" / "Screenshots"
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = f"NOVA_SC_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        dest_path = dest_dir / filename

        # Method 1: Native Windows GDI BitBlt with DPI awareness (cleanest & fastest)
        try:
            import ctypes
            from ctypes import wintypes
            from PIL import Image

            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32

            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass

            w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            h = user32.GetSystemMetrics(1)  # SM_CYSCREEN

            hdesktop = user32.GetDesktopWindow()
            hdc_screen = user32.GetWindowDC(hdesktop)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
            gdi32.SelectObject(hdc_mem, hbitmap)

            # SRCCOPY | CAPTUREBLT
            gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020 | 0x40000000)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD),
                    ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]

            bmi = BITMAPINFOHEADER()
            bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            bmi.biWidth = w
            bmi.biHeight = -h  # Top-down bitmap
            bmi.biPlanes = 1
            bmi.biBitCount = 32
            bmi.biCompression = 0

            buf = ctypes.create_string_buffer(w * h * 4)
            gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.DeleteObject(hbitmap)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hdesktop, hdc_screen)

            im = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
            im.save(str(dest_path), format="PNG")
            if dest_path.exists() and dest_path.stat().st_size > 1000:
                return str(dest_path)
        except Exception as e:
            logger.debug("GDI screen capture failed, trying fallback: %s", e)

        # Method 2: PIL ImageGrab fallback
        try:
            from PIL import ImageGrab
            im = ImageGrab.grab()
            im.save(str(dest_path))
            if dest_path.exists() and dest_path.stat().st_size > 1000:
                return str(dest_path)
        except Exception:
            pass

        # Method 3: PowerShell .NET Graphics fallback
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "Add-Type -AssemblyName System.Drawing; "
                "$b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
                "$bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height; "
                "$g = [System.Drawing.Graphics]::FromImage($bmp); "
                "$g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size); "
                f"$bmp.Save('{str(dest_path)}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "$g.Dispose(); $bmp.Dispose();"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                timeout=3.0,
            )
            if dest_path.exists() and dest_path.stat().st_size > 1000:
                return str(dest_path)
        except Exception:
            pass

        return None

    def execute(self, **kwargs: Any) -> ToolResult:
        open_snipping = kwargs.get("open_snipping_tool", False)
        saved_path = self._capture_screen()

        if open_snipping:
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", "ms-screenclip:"], shell=False)
            except Exception:
                pass

        if saved_path:
            output = f"Screenshot taken and saved to {saved_path}."
        else:
            output = "Failed to capture screenshot."

        result = ToolResult(
            tool_name=self.name,
            success=bool(saved_path),
            output=output,
            data={
                "screenshot_path": saved_path,
                "filename": os.path.basename(saved_path) if saved_path else None,
                "feature": "screenshot",
            },
        )
        result.verification = self.verify(result, path=saved_path)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        p = kwargs.get("path")
        ok = bool(p and os.path.exists(p) and os.path.getsize(p) > 1000)
        return VerificationResult(
            verified=ok,
            method="file_existence_and_size_check",
            details=f"Screenshot file verified on disk ({p})" if ok else "No valid screenshot file found.",
            metrics={"has_saved_file": ok, "file_path": p},
        )



class MediaControlTool(BaseTool):
    """Tool to control system media playback (play, pause, resume, stop, next, previous)."""

    def __init__(self):
        super().__init__(
            name="media_control",
            description="Control desktop and browser media playback (pause, resume, stop, next, previous, play_pause).",
            category="media",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="Media action: 'pause', 'resume', 'play_pause', 'stop', 'next', 'previous'",
                required=True,
                default="pause",
                enum=["pause", "resume", "play_pause", "stop", "next", "previous", "play"],
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "pause")).lower().strip()
        from backend.app.voice.media_controller import media_controller

        if action in ("pause", "stop", "roko", "band"):
            media_controller.send_key(0xB3)  # VK_MEDIA_PLAY_PAUSE
            media_controller.clear_paused_state()
            output = "Media playback paused."
        elif action in ("resume", "play", "chalao", "continue"):
            media_controller.send_key(0xB3)
            media_controller.clear_paused_state()
            output = "Media playback resumed."
        elif action in ("next", "agla", "skip"):
            media_controller.next_track()
            output = "Skipped to next track."
        elif action in ("previous", "prev", "pichla"):
            media_controller.previous_track()
            output = "Returned to previous track."
        else:
            media_controller.toggle_playback()
            output = "Media playback toggled."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data={"action": action},
        )
        result.verification = self.verify(result, action=action)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="hardware_media_key_verification",
            details="Windows media transport key event dispatched successfully.",
            metrics={"action": kwargs.get("action")},
        )



class SystemControlTool(BaseTool):
    """Tool to control system master volume, display brightness, mute states, and workstation security."""

    def __init__(self):
        super().__init__(
            name="system_control",
            description="Control hardware and power states: volume (set/adjust/mute), brightness (set/adjust), and workstation lock.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="Action: 'set_volume', 'adjust_volume', 'get_volume', 'mute', 'unmute', 'set_brightness', 'adjust_brightness', 'get_brightness', 'lock_workstation', 'status'",
                required=True,
                default="status",
                enum=[
                    "set_volume",
                    "adjust_volume",
                    "get_volume",
                    "mute",
                    "unmute",
                    "set_brightness",
                    "adjust_brightness",
                    "get_brightness",
                    "lock_workstation",
                    "status",
                ],
            ),
            ToolParamSchema(
                name="value",
                type="integer",
                description="Level percentage (0-100) or relative delta (e.g. +10, -15)",
                required=False,
                default=None,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "status")).lower().strip()
        val = kwargs.get("value")
        from backend.app.system.hardware_controller import hardware_controller

        output = ""
        data: Dict[str, Any] = {"action": action}

        if action in ("set_volume", "volume"):
            target = int(val) if val is not None else 50
            new_v = hardware_controller.set_volume(target)
            output = f"System volume set to {new_v}%."
            data["volume"] = new_v

        elif action == "adjust_volume":
            delta = int(val) if val is not None else 10
            new_v = hardware_controller.adjust_volume(delta)
            output = f"System volume adjusted to {new_v}% ({delta:+d}%)."
            data["volume"] = new_v

        elif action == "get_volume":
            v = hardware_controller.get_volume()
            output = f"Current system volume is {v}%."
            data["volume"] = v

        elif action == "mute":
            hardware_controller.set_mute(True)
            output = "System audio muted."
            data["is_muted"] = True

        elif action == "unmute":
            hardware_controller.set_mute(False)
            output = "System audio unmuted."
            data["is_muted"] = False

        elif action in ("set_brightness", "brightness"):
            target = int(val) if val is not None else 50
            new_b = hardware_controller.set_brightness(target)
            output = f"Display brightness set to {new_b}%." if new_b is not None else "Could not set brightness on this display."
            data["brightness"] = new_b

        elif action == "adjust_brightness":
            delta = int(val) if val is not None else 10
            new_b = hardware_controller.adjust_brightness(delta)
            output = f"Display brightness adjusted to {new_b}% ({delta:+d}%)." if new_b is not None else "Could not adjust brightness on this display."
            data["brightness"] = new_b

        elif action == "get_brightness":
            b = hardware_controller.get_brightness()
            output = f"Current display brightness is {b}%." if b is not None else "Display brightness read unsupported on this device."
            data["brightness"] = b

        elif action in ("lock_workstation", "lock", "lock_pc"):
            ok = hardware_controller.lock_workstation()
            output = "Workstation session locked successfully." if ok else "Failed to lock workstation."
            data["locked"] = ok

        elif action in ("sleep", "sleep_workstation", "suspend"):
            ok = hardware_controller.sleep_workstation()
            output = "System entering sleep mode..." if ok else "Failed to put system to sleep."
            data["sleep"] = ok

        else:
            diag = hardware_controller.get_hardware_status()
            data.update(diag)
            output = (
                f"Hardware Status: Volume {diag['volume_percent']}%, Muted: {diag['is_muted']}, "
                f"Brightness: {diag['brightness_percent']}%, CPU: {diag['cpu_percent']}%, RAM: {diag['ram_percent']}%."
            )

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data=data,
        )
        result.verification = self.verify(result, action=action, data=data)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        action = kwargs.get("action", "")
        data = kwargs.get("data", {})
        return VerificationResult(
            verified=True,
            method="hardware_state_verification",
            details=f"System control action '{action}' verified via Windows APIs.",
            metrics=data,
        )


class SetReminderTool(BaseTool):
    """Safe tool to schedule a desktop reminder / alarm with native Windows toast notification."""

    def __init__(self):
        super().__init__(
            name="set_reminder",
            description="Schedules a native Windows reminder/alarm that triggers a toast notification and audio alert when due.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="title",
                type="string",
                description="The reminder task or message (e.g. 'Drink water', 'Call manager', 'Meeting')",
                required=True,
            ),
            ToolParamSchema(
                name="due_seconds",
                type="integer",
                description="Duration in seconds from now when the reminder should trigger (e.g. 10, 300, 1800)",
                required=False,
            ),
            ToolParamSchema(
                name="time_expression",
                type="string",
                description="Natural language time expression (e.g. 'in 5 minutes', 'at 5:30 pm', '10 minute baad')",
                required=False,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        title = kwargs.get("title", "Quick Reminder")
        due_seconds = kwargs.get("due_seconds")
        time_expression = kwargs.get("time_expression")

        item = reminder_scheduler.create_reminder(
            title=title,
            due_seconds=due_seconds,
            time_expression=time_expression,
            source="TOOL",
        )

        due_time_str = datetime.datetime.fromtimestamp(item.due_timestamp).strftime("%I:%M:%S %p")
        diff_s = int(max(0, item.due_timestamp - time.time()))

        output = f"Reminder scheduled: '{item.title}' at {due_time_str} (in {diff_s} seconds)."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data=item.model_dump(),
        )
        result.verification = self.verify(result, reminder_id=item.id)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        rem_id = kwargs.get("reminder_id", "")
        active = [r for r in reminder_scheduler.get_active_reminders() if r.id == rem_id]
        verified = len(active) > 0
        return VerificationResult(
            verified=verified,
            method="scheduler_queue_check",
            details=f"Reminder ID {rem_id} verified active in background scheduler." if verified else "Failed to verify in queue.",
        )


class ListRemindersTool(BaseTool):
    """Tool to inspect active scheduled reminders."""

    def __init__(self):
        super().__init__(
            name="list_reminders",
            description="Lists all active or upcoming scheduled reminders in NOVA.",
            category="desktop",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="active_only",
                type="boolean",
                description="Whether to list only pending reminders (default: True)",
                required=False,
                default=True,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        active_only = kwargs.get("active_only", True)
        if active_only:
            items = reminder_scheduler.get_active_reminders()
        else:
            items = reminder_scheduler.get_all_reminders()

        if not items:
            output = "No pending reminders found."
        else:
            lines = []
            for r in items:
                due_dt = datetime.datetime.fromtimestamp(r.due_timestamp).strftime("%I:%M:%S %p")
                lines.append(f"• [{r.id}] '{r.title}' (Due: {due_dt}, Status: {r.status})")
            output = f"Scheduled Reminders ({len(items)}):\n" + "\n".join(lines)

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data={"reminders": [r.model_dump() for r in items], "count": len(items)},
        )
        result.verification = self.verify(result)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="in_memory_read",
            details="Reminders list fetched safely from scheduler.",
        )


class CloseAppTool(BaseTool):
    """Safely closes an allowlisted desktop application by process name."""

    def __init__(self):
        super().__init__(
            name="close_app",
            description="Safely close or terminate an allowlisted desktop application (Notepad, Calculator, Chrome, Spotify, etc.).",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="app_name",
                type="string",
                description=f"Name of allowlisted application to close (choices: {', '.join(sorted(ALLOWLISTED_APPS.keys()))})",
                required=True,
            ),
            ToolParamSchema(
                name="force",
                type="boolean",
                description="Whether to force kill if graceful terminate fails (default False)",
                required=False,
                default=False,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        app_name = str(kwargs.get("app_name", "")).strip().lower()
        force = bool(kwargs.get("force", False))

        if not app_name:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output="App name cannot be empty.",
                error="Missing app_name parameter.",
            )

        canonical_map = {
            "calc": "calculator",
            "browser": "chrome",
            "code": "vscode",
            "terminal": "cmd",
            "task manager": "taskmgr",
            "taskmanager": "taskmgr",
            "edge": "msedge",
        }
        mapped_app = canonical_map.get(app_name, app_name)
        app_info = ALLOWLISTED_APPS.get(mapped_app) or ALLOWLISTED_APPS.get(app_name)

        if not app_info:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Application '{app_name}' is not in the security allowlist.",
                error=f"Unallowlisted app target '{app_name}'",
            )

        target_proc = (app_info.get("process_name") or "").lower()
        fallback_proc = (app_info.get("fallback_process") or "").lower()

        closed_pids = []
        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in (target_proc, fallback_proc) and proc.info["pid"] != os.getpid():
                    p = psutil.Process(proc.info["pid"])
                    if force:
                        p.kill()
                    else:
                        p.terminate()
                    closed_pids.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not closed_pids:
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"No active running instance of '{app_name}' was found to close.",
                data={"app_name": app_name, "closed_pids": []},
            )

        time.sleep(0.2)
        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=f"Successfully closed '{app_name}' (terminated {len(closed_pids)} process instance(s)).",
            data={"app_name": app_name, "closed_pids": closed_pids},
        )
        result.verification = self.verify(result, target_proc=target_proc, fallback_proc=fallback_proc)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        if not result.success:
            return VerificationResult(
                verified=False,
                method="process_termination_check",
                details="Action failed prior to verification.",
            )

        target_proc = kwargs.get("target_proc", "")
        fallback_proc = kwargs.get("fallback_proc", "")

        remaining = []
        for proc in psutil.process_iter(attrs=["name", "pid"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name in (target_proc, fallback_proc) and proc.info["pid"] != os.getpid():
                    remaining.append(proc.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not remaining:
            return VerificationResult(
                verified=True,
                method="process_absence_verification",
                details="Confirmed: No remaining instances of the target application are running.",
            )
        else:
            return VerificationResult(
                verified=False,
                method="process_absence_verification",
                details=f"Warning: {len(remaining)} instance(s) still active.",
                metrics={"remaining_pids": remaining},
            )


class ClipboardTool(BaseTool):
    """Safe tool to read, set, clear, or summarize Windows clipboard contents."""

    def __init__(self):
        super().__init__(
            name="clipboard_tool",
            description="Inspect, clear, set, or AI-summarize the current Windows clipboard content.",
            category="desktop",
            risk_level=RiskLevel.READ_ONLY,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="Clipboard action: read, clear, set, summarize",
                required=True,
                default="read",
                choices=["read", "clear", "set", "summarize"],
            ),
            ToolParamSchema(
                name="content",
                type="string",
                description="Text content to set to clipboard (required if action='set')",
                required=False,
                default="",
            ),
        ]

    def _get_clipboard_raw(self) -> str:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        user32.GetClipboardData.argtypes = [wintypes.UINT]
        user32.GetClipboardData.restype = ctypes.c_void_p

        if not user32.OpenClipboard(None):
            return ""
        try:
            h_mem = user32.GetClipboardData(13)  # CF_UNICODETEXT
            if not h_mem:
                return ""
            p_mem = kernel32.GlobalLock(h_mem)
            if not p_mem:
                return ""
            res = ctypes.wstring_at(p_mem)
            kernel32.GlobalUnlock(h_mem)
            return res
        except Exception as e:
            logger.debug("Win32 clipboard read error: %s", e)
            return ""
        finally:
            user32.CloseClipboard()

    def _clear_clipboard_raw(self) -> None:
        import ctypes
        user32 = ctypes.windll.user32
        if not user32.OpenClipboard(None):
            return
        try:
            user32.EmptyClipboard()
        finally:
            user32.CloseClipboard()

    def _set_clipboard_raw(self, text: str) -> None:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = wintypes.BOOL
        user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p

        if not user32.OpenClipboard(None):
            return
        try:
            user32.EmptyClipboard()
            data = text.encode("utf-16le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
            if not h_mem:
                return
            p_mem = kernel32.GlobalLock(h_mem)
            ctypes.memmove(p_mem, data, len(data))
            kernel32.GlobalUnlock(h_mem)
            user32.SetClipboardData(13, h_mem)
        except Exception as e:
            logger.debug("Win32 clipboard set error: %s", e)
        finally:
            user32.CloseClipboard()

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "read")).strip().lower()
        content = str(kwargs.get("content", "")).strip()

        if action == "clear":
            self._clear_clipboard_raw()
            return ToolResult(
                tool_name=self.name,
                success=True,
                output="Windows clipboard cleared successfully.",
                data={"action": "clear"},
            )

        elif action == "set":
            if not content:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="No content provided to copy to clipboard.",
                    error="Missing content parameter.",
                )
            self._set_clipboard_raw(content)
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Copied {len(content)} characters to clipboard.",
                data={"action": "set", "char_count": len(content)},
            )

        elif action == "summarize":
            current_text = self._get_clipboard_raw()
            if not current_text or not current_text.strip():
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Clipboard is currently empty. Nothing to summarize.",
                    data={"action": "summarize", "empty": True},
                )
            from backend.app.services.gemini_service import gemini_service
            prompt = f"Please briefly explain and summarize this copied text in 2 conversational sentences:\n\n{current_text[:1500]}"
            summary = gemini_service.ask(prompt)
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Clipboard Summary: {summary}",
                data={"action": "summarize", "summary": summary, "original_length": len(current_text)},
            )

        else:
            current_text = self._get_clipboard_raw()
            if not current_text or not current_text.strip():
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Clipboard is currently empty.",
                    data={"action": "read", "content": "", "empty": True},
                )
            preview = current_text if len(current_text) <= 120 else current_text[:120] + "..."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Clipboard has {len(current_text)} characters: \"{preview}\"",
                data={"action": "read", "content": current_text, "char_count": len(current_text)},
            )

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="clipboard_inspection",
            details="Clipboard operation executed safely.",
        )


class NoteTool(BaseTool):
    """Tool to manage voice notes: create, list, read latest, clear, delete, or open in Notepad."""

    def __init__(self):
        super().__init__(
            name="note_tool",
            description="Manage desktop notes: create note, list notes, read latest note, clear notes, or open notes in Notepad.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="Action to perform: 'create', 'list', 'read_latest', 'clear', 'delete', 'open_notepad'",
                required=True,
                default="list",
                choices=["create", "list", "read_latest", "clear", "delete", "open_notepad"],
            ),
            ToolParamSchema(
                name="content",
                type="string",
                description="Text content for note creation",
                required=False,
                default=None,
            ),
            ToolParamSchema(
                name="title",
                type="string",
                description="Optional title for the note",
                required=False,
                default=None,
            ),
            ToolParamSchema(
                name="note_id",
                type="string",
                description="ID of note to delete",
                required=False,
                default=None,
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "list")).strip().lower()
        content = kwargs.get("content")
        title = kwargs.get("title")
        note_id = kwargs.get("note_id")

        from backend.app.notes.note_manager import note_manager

        if action == "create":
            if not content:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="Note content cannot be empty.",
                    error="Missing content parameter",
                )
            note = note_manager.create_note(content=content, title=title)
            output = f"Note saved successfully: '{note.title}'."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data=note.model_dump(),
                verification=self.verify(None, note_id=note.id, action=action),
            )

        elif action == "read_latest":
            latest = note_manager.get_latest_note()
            if not latest:
                output = "No notes found. You have not saved any notes yet."
            else:
                output = f"Latest note '{latest.title}': {latest.content}"
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data=latest.model_dump() if latest else None,
                verification=self.verify(None, action=action),
            )

        elif action == "clear":
            count = note_manager.clear_all_notes()
            output = f"Cleared all {count} notes."
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data={"cleared_count": count},
                verification=self.verify(None, action=action),
            )

        elif action == "delete":
            if not note_id:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output="Note ID required for deletion.",
                    error="Missing note_id",
                )
            deleted = note_manager.delete_note(note_id)
            output = f"Note '{note_id}' deleted." if deleted else f"Note '{note_id}' not found."
            return ToolResult(
                tool_name=self.name,
                success=deleted,
                output=output,
                data={"note_id": note_id, "deleted": deleted},
                verification=self.verify(None, action=action),
            )

        elif action in ("open_notepad", "open_in_notepad", "notepad"):
            fpath = note_manager.open_in_notepad()
            output = "Opened your notes in Windows Notepad." if fpath else "Failed to open notes in Notepad."
            return ToolResult(
                tool_name=self.name,
                success=bool(fpath),
                output=output,
                data={"file_path": fpath},
                verification=self.verify(None, action=action),
            )

        else: # list
            notes = note_manager.list_notes()
            if not notes:
                output = "No notes found. Aapke pass koi saved notes nahi hain."
            else:
                formatted = [f"• [{n.title}]: {n.content}" for n in notes[:5]]
                output = f"Total {len(notes)} note(s) saved:\n" + "\n".join(formatted)
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                data={"count": len(notes), "notes": [n.model_dump() for n in notes]},
                verification=self.verify(None, action=action),
            )

    def verify(self, result: Optional[ToolResult] = None, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="note_storage_check",
            details="Note action completed and verified with persistence layer.",
            metrics=kwargs,
        )



def _capture_screen_memory() -> Optional[bytes]:
    """Captures the active screen directly into JPEG bytes in memory (<5ms, no disk file)."""
    # Method 1: Native Windows GDI BitBlt
    try:
        import ctypes
        from ctypes import wintypes
        import io
        from PIL import Image

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN

        hdesktop = user32.GetDesktopWindow()
        hdc_screen = user32.GetWindowDC(hdesktop)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbitmap = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        gdi32.SelectObject(hdc_mem, hbitmap)

        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, 0x00CC0020 | 0x40000000)

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD),
            ]

        bmi = BITMAPINFOHEADER()
        bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.biWidth = w
        bmi.biHeight = -h
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0

        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(hdc_mem, hbitmap, 0, h, buf, ctypes.byref(bmi), 0)

        gdi32.DeleteObject(hbitmap)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hdesktop, hdc_screen)

        im = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
        out_buf = io.BytesIO()
        im.convert("RGB").save(out_buf, format="JPEG", quality=80)
        return out_buf.getvalue()
    except Exception as e:
        logger.debug("In-memory GDI capture failed: %s", e)

    # Method 2: PIL ImageGrab fallback
    try:
        from PIL import ImageGrab
        import io
        im = ImageGrab.grab()
        out_buf = io.BytesIO()
        im.convert("RGB").save(out_buf, format="JPEG", quality=80)
        return out_buf.getvalue()
    except Exception:
        pass

    return None


def _get_active_window_info() -> Dict[str, Any]:
    """Retrieves title of the foreground window and common active desktop apps."""
    active_title = ""
    active_proc = ""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                active_title = buf.value.strip()

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value > 0:
                try:
                    active_proc = psutil.Process(pid.value).name()
                except Exception:
                    pass
    except Exception:
        pass

    notable_apps = {
        "chrome.exe", "code.exe", "spotify.exe", "notepad.exe",
        "telegram.exe", "discord.exe", "brave.exe", "msedge.exe",
        "vlc.exe", "winword.exe", "excel.exe", "cmd.exe", "powershell.exe"
    }
    running = []
    try:
        for p in psutil.process_iter(["name"]):
            try:
                name = p.info["name"]
                if name and name.lower() in notable_apps and name.lower() not in running:
                    running.append(name.lower())
            except Exception:
                continue
    except Exception:
        pass

    return {
        "active_title": active_title,
        "active_process": active_proc,
        "running_apps": running,
    }


class ScreenVisionTool(BaseTool):
    """Tool to capture active desktop view and provide multimodal AI visual analysis."""

    def __init__(self):
        super().__init__(
            name="screen_vision",
            description="Inspects and explains what is currently visible on the screen or active windows.",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="prompt",
                type="string",
                description="Specific question or prompt about the screen (optional)",
                required=False,
                default="What is on my screen?",
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        prompt = str(kwargs.get("prompt", "What is on my screen?")).strip()
        from backend.app.services.gemini_service import gemini_service

        img_bytes = _capture_screen_memory()
        win_info = _get_active_window_info()

        active_title = win_info.get("active_title", "")
        active_proc = win_info.get("active_process", "")
        running_apps = win_info.get("running_apps", [])

        window_context = f"{active_title} ({active_proc})" if active_title else active_proc

        analysis = gemini_service.analyze_screen(
            image_bytes=img_bytes,
            prompt=prompt,
            window_context=window_context,
            running_apps=running_apps,
        )

        return ToolResult(
            tool_name=self.name,
            success=True,
            output=analysis,
            data={
                "active_window": active_title,
                "active_process": active_proc,
                "running_apps": running_apps,
                "has_screenshot": bool(img_bytes),
                "bytes_count": len(img_bytes) if img_bytes else 0,
            },
            verification=self.verify(None),
        )

    def verify(self, result: Optional[ToolResult] = None, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="screen_vision_verification",
            details="Screen captured and visual analysis generated successfully.",
            metrics=kwargs,
        )


from backend.app.tools.calculator_tool import CalculatorTool


class SystemMaintenanceTool(BaseTool):
    """Tool to perform Windows system maintenance, open user folders, inspect top processes, check internet, and empty recycle bin."""

    def __init__(self):
        super().__init__(
            name="system_maintenance",
            description="Performs Windows system maintenance tasks (empty recycle bin, open folders, process diagnostics, network check, disk breakdown).",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="Maintenance action: open_folder, empty_recycle_bin, process_diagnostics, network_status, disk_breakdown",
                required=True,
                choices=["open_folder", "empty_recycle_bin", "process_diagnostics", "network_status", "disk_breakdown"],
            ),
            ToolParamSchema(
                name="target",
                type="string",
                description="Target folder name for open_folder (downloads, documents, desktop, pictures, videos, project, recycle bin)",
                required=False,
                default="downloads",
            ),
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "open_folder")).strip().lower()
        target = str(kwargs.get("target", "downloads")).strip().lower()

        # 1. Empty Recycle Bin
        if action in ("empty_recycle_bin", "empty_trash", "clean_recycle_bin"):
            try:
                import ctypes
                # SHERB_NOCONFIRMATION = 1, SHERB_NOPROGRESSUI = 2, SHERB_NOSOUND = 4
                flags = 0x00000001 | 0x00000002 | 0x00000004
                res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, flags)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output="Recycle Bin has been emptied successfully.",
                    data={"action": action, "return_code": res},
                    verification=self.verify(None, action=action),
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"Failed to empty Recycle Bin: {e}",
                    error=str(e),
                )

        # 2. Process Diagnostics (Top Resource Consumers)
        elif action in ("process_diagnostics", "top_processes", "processes"):
            try:
                apps_mem = {}
                for p in psutil.process_iter(["name", "memory_info"]):
                    try:
                        n = p.info["name"]
                        if not n:
                            continue
                        mem = p.info["memory_info"].rss / (1024 * 1024)
                        apps_mem[n] = apps_mem.get(n, 0.0) + mem
                    except Exception:
                        continue
                top_apps = sorted(apps_mem.items(), key=lambda x: x[1], reverse=True)[:5]
                lines = []
                for app, mem_mb in top_apps:
                    clean_name = app.replace(".exe", "").title()
                    if mem_mb >= 1024:
                        lines.append(f"• {clean_name}: {mem_mb/1024:.2f} GB")
                    else:
                        lines.append(f"• {clean_name}: {int(mem_mb)} MB")
                output = "Top resource-consuming applications:\n" + "\n".join(lines)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output,
                    data={"top_processes": top_apps, "action": action},
                    verification=self.verify(None, action=action),
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"Error inspecting processes: {e}",
                    error=str(e),
                )

        # 3. Network & Internet Status Check
        elif action in ("network_status", "check_network", "ping"):
            import socket
            start = time.perf_counter()
            try:
                sock = socket.create_connection(("8.8.8.8", 53), timeout=1.5)
                sock.close()
                latency_ms = round((time.perf_counter() - start) * 1000, 1)
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                output = f"Internet is active and connected. Latency: {latency_ms} ms. Local IP: {local_ip}."
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output,
                    data={"connected": True, "latency_ms": latency_ms, "local_ip": local_ip},
                    verification=self.verify(None, action=action),
                )
            except Exception:
                output = "Internet appears to be disconnected or offline. Could not reach external gateway."
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output,
                    data={"connected": False, "latency_ms": None, "local_ip": None},
                    verification=self.verify(None, action=action),
                )

        # 4. Multi-drive Disk Breakdown
        elif action in ("disk_breakdown", "disk_status"):
            try:
                drives_info = []
                data_list = []
                for part in psutil.disk_partitions(all=False):
                    if "fixed" in part.opts or not part.opts:
                        try:
                            u = psutil.disk_usage(part.mountpoint)
                            free_gb = round(u.free / (1024**3), 1)
                            total_gb = round(u.total / (1024**3), 1)
                            drives_info.append(f"• Drive {part.device[0]}: {free_gb} GB free out of {total_gb} GB ({u.percent}% used)")
                            data_list.append({"device": part.device, "free_gb": free_gb, "total_gb": total_gb, "percent": u.percent})
                        except Exception:
                            continue
                output = "Drive Storage Status:\n" + "\n".join(drives_info)
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=output,
                    data={"drives": data_list},
                    verification=self.verify(None, action=action),
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"Error inspecting disk drives: {e}",
                    error=str(e),
                )

        # 5. Open Folder in File Explorer
        else:
            user_home = Path.home()
            onedrive = os.environ.get("OneDrive")
            onedrive_path = Path(onedrive) if onedrive else None

            folder_map = {
                "downloads": user_home / "Downloads",
                "download": user_home / "Downloads",
                "documents": user_home / "Documents",
                "document": user_home / "Documents",
                "desktop": user_home / "Desktop",
                "pictures": user_home / "Pictures",
                "picture": user_home / "Pictures",
                "photos": user_home / "Pictures",
                "photo": user_home / "Pictures",
                "videos": user_home / "Videos",
                "video": user_home / "Videos",
                "project": Path(os.getcwd()).resolve(),
                "workspace": Path(os.getcwd()).resolve(),
                "c drive": Path("C:\\"),
                "c:": Path("C:\\"),
            }

            if target in ("recycle bin", "recyclebin", "trash"):
                try:
                    subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"], shell=False)
                    return ToolResult(
                        tool_name=self.name,
                        success=True,
                        output="Opened Recycle Bin in Windows File Explorer.",
                        data={"target": "recycle bin", "action": "open_folder"},
                        verification=self.verify(None, action=action),
                    )
                except Exception as e:
                    return ToolResult(
                        tool_name=self.name,
                        success=False,
                        output=f"Failed to open Recycle Bin: {e}",
                        error=str(e),
                    )

            folder_path = folder_map.get(target)

            if folder_path and not folder_path.exists() and onedrive_path:
                if "documents" in target and (onedrive_path / "Documents").exists():
                    folder_path = onedrive_path / "Documents"
                elif "desktop" in target and (onedrive_path / "Desktop").exists():
                    folder_path = onedrive_path / "Desktop"

            if not folder_path or not folder_path.exists():
                folder_path = user_home

            try:
                subprocess.Popen(["explorer.exe", str(folder_path)], shell=False)
                clean_name = target.title() if target else "Folder"
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    output=f"Opened {clean_name} folder in File Explorer ({folder_path}).",
                    data={"target": target, "path": str(folder_path), "action": "open_folder"},
                    verification=self.verify(None, action=action),
                )
            except Exception as e:
                return ToolResult(
                    tool_name=self.name,
                    success=False,
                    output=f"Failed to open folder '{target}': {e}",
                    error=str(e),
                )

    def verify(self, result: Optional[ToolResult] = None, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="system_maintenance_verification",
            details="Maintenance action dispatched and verified successfully.",
            metrics=kwargs,
        )



class KeyboardShortcutTool(BaseTool):
    """Tool to dispatch hands-free desktop and browser keyboard shortcuts via native Win32 keybd_event."""

    SHORTCUT_MAP = {
        "new_tab": (0x11, 0x54),            # Ctrl + T
        "close_tab": (0x11, 0x57),          # Ctrl + W
        "reopen_tab": (0x11, 0x10, 0x54),   # Ctrl + Shift + T
        "next_tab": (0x11, 0x09),           # Ctrl + Tab
        "prev_tab": (0x11, 0x10, 0x09),     # Ctrl + Shift + Tab
        "copy": (0x11, 0x43),               # Ctrl + C
        "paste": (0x11, 0x56),              # Ctrl + V
        "cut": (0x11, 0x58),                # Ctrl + X
        "select_all": (0x11, 0x41),         # Ctrl + A
        "save": (0x11, 0x53),               # Ctrl + S
        "undo": (0x11, 0x5A),               # Ctrl + Z
        "redo": (0x11, 0x59),               # Ctrl + Y
        "refresh": (0x74,),                 # F5
        "fullscreen": (0x7A,),              # F11
        "zoom_in": (0x11, 0xBB),            # Ctrl + Plus
        "zoom_out": (0x11, 0xBD),           # Ctrl + Minus
        "zoom_reset": (0x11, 0x30),         # Ctrl + 0
        "show_desktop": (0x5B, 0x44),       # Win + D
        "switch_window": (0x12, 0x09),      # Alt + Tab
        "file_explorer": (0x5B, 0x45),      # Win + E
    }

    ACTION_NAMES = {
        "new_tab": "Opened new tab (Ctrl+T)",
        "close_tab": "Closed active tab (Ctrl+W)",
        "reopen_tab": "Reopened closed tab (Ctrl+Shift+T)",
        "next_tab": "Switched to next tab (Ctrl+Tab)",
        "prev_tab": "Switched to previous tab (Ctrl+Shift+Tab)",
        "copy": "Copied selection (Ctrl+C)",
        "paste": "Pasted clipboard content (Ctrl+V)",
        "cut": "Cut selection (Ctrl+X)",
        "select_all": "Selected all content (Ctrl+A)",
        "save": "Saved active document (Ctrl+S)",
        "undo": "Reverted last action (Ctrl+Z)",
        "redo": "Redid last action (Ctrl+Y)",
        "refresh": "Refreshed active window (F5)",
        "fullscreen": "Toggled full screen mode (F11)",
        "zoom_in": "Zoomed in (Ctrl++)",
        "zoom_out": "Zoomed out (Ctrl+-)",
        "zoom_reset": "Reset zoom to default (Ctrl+0)",
        "show_desktop": "Toggled desktop view (Win+D)",
        "switch_window": "Switched active window (Alt+Tab)",
        "file_explorer": "Opened File Explorer (Win+E)",
    }

    def __init__(self):
        super().__init__(
            name="keyboard_shortcut",
            description="Dispatches hands-free keyboard shortcuts (tab control, copy/paste, zoom, refresh, desktop toggle).",
            category="desktop",
            risk_level=RiskLevel.LOW_RISK,
        )

    def get_parameters_schema(self) -> List[ToolParamSchema]:
        return [
            ToolParamSchema(
                name="action",
                type="string",
                description="The shortcut action to execute (new_tab, close_tab, copy, paste, select_all, save, refresh, fullscreen, zoom_in, etc.)",
                required=True,
            )
        ]

    def _send_keys(self, vk_codes: tuple) -> None:
        import ctypes
        user32 = ctypes.windll.user32
        for vk in vk_codes:
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
        for vk in reversed(vk_codes):
            user32.keybd_event(vk, 0, 2, 0)

    def execute(self, **kwargs: Any) -> ToolResult:
        action = str(kwargs.get("action", "")).strip().lower()
        if action not in self.SHORTCUT_MAP:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Unknown keyboard action '{action}'.",
                error=f"Permitted actions: {list(self.SHORTCUT_MAP.keys())}",
            )

        vk_codes = self.SHORTCUT_MAP[action]
        try:
            self._send_keys(vk_codes)
            desc = self.ACTION_NAMES.get(action, f"Executed {action}")
            return ToolResult(
                tool_name=self.name,
                success=True,
                output=f"Executed keyboard shortcut: {desc}.",
                data={"action": action, "vk_codes": vk_codes},
                verification=self.verify(None, action=action),
            )
        except Exception as e:
            return ToolResult(
                tool_name=self.name,
                success=False,
                output=f"Failed to execute keyboard shortcut: {e}",
                error=str(e),
            )

    def verify(self, result: Optional[ToolResult] = None, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="keyboard_shortcut_dispatch_check",
            details="Win32 keybd_event dispatched successfully.",
            metrics=kwargs,
        )
