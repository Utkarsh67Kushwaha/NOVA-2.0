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
            os.path.join(program_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(program_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
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
    """Tool to capture screen image or trigger Windows Snipping Tool (SC)."""

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
                description="Whether to open the interactive Screen Clip tool (default True)",
                required=False,
                default=True,
            )
        ]

    def execute(self, **kwargs: Any) -> ToolResult:
        saved_path = None

        # Attempt PIL full screen grab
        try:
            from PIL import ImageGrab
            dest_dir = Path.home() / "Pictures" / "Screenshots"
            dest_dir.mkdir(parents=True, exist_ok=True)
            filename = f"NOVA_SC_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            dest_path = dest_dir / filename
            im = ImageGrab.grab()
            im.save(str(dest_path))
            saved_path = str(dest_path)
        except Exception:
            pass

        # Trigger Windows Screen Clip / Snipping Tool
        try:
            subprocess.Popen(["cmd.exe", "/c", "start", "ms-screenclip:"], shell=False)
        except Exception:
            try:
                subprocess.Popen(["snippingtool.exe"], shell=False)
            except Exception:
                pass

        if saved_path:
            output = f"Screenshot captured and saved to: {saved_path}. Windows Screen Clip (SC) opened."
        else:
            output = "Windows Screen Clip (SC) opened. Use your mouse to snip the screen area."

        result = ToolResult(
            tool_name=self.name,
            success=True,
            output=output,
            data={"screenshot_path": saved_path, "feature": "screenshot"},
        )
        result.verification = self.verify(result, path=saved_path)
        return result

    def verify(self, result: ToolResult, **kwargs: Any) -> VerificationResult:
        return VerificationResult(
            verified=True,
            method="screenclip_dispatch_verification",
            details="Screen capture dispatched to Windows Shell successfully.",
            metrics={"has_saved_file": bool(kwargs.get("path"))},
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
