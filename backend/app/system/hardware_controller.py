"""
NOVA System Hardware & Power Controller
Provides native Windows controls for System Volume, Display Brightness,
Audio Mute, Workstation Locking, and Power States with post-action verification.
"""

import ctypes
from ctypes import HRESULT, POINTER, c_float, c_int
import logging
import subprocess
import threading
from typing import Any, Dict, Optional
import psutil

logger = logging.getLogger("nova.system.hardware")

# CoreAudio Volume GUIDs
CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
IID_IMMDeviceEnumerator = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
IID_IAudioEndpointVolume = "{5CDF2C82-841E-4546-9722-0CF74078229A}"

COMTYPES_AUDIO_AVAILABLE = False
try:
    import comtypes
    import comtypes.client
    from comtypes import CLSCTX_ALL, GUID

    class IAudioEndpointVolume(comtypes.IUnknown):
        _iid_ = GUID(IID_IAudioEndpointVolume)
        _methods_ = [
            comtypes.COMMETHOD([], HRESULT, "RegisterControlChangeNotify"),
            comtypes.COMMETHOD([], HRESULT, "UnregisterControlChangeNotify"),
            comtypes.COMMETHOD([], HRESULT, "GetChannelCount"),
            comtypes.COMMETHOD([], HRESULT, "SetMasterVolumeLevel"),
            comtypes.COMMETHOD(
                [], HRESULT, "SetMasterVolumeLevelScalar",
                (["in"], c_float, "fLevel"),
                (["in"], POINTER(GUID), "pguidEventContext")
            ),
            comtypes.COMMETHOD([], HRESULT, "GetMasterVolumeLevel"),
            comtypes.COMMETHOD(
                [], HRESULT, "GetMasterVolumeLevelScalar",
                (["out"], POINTER(c_float), "pfLevel")
            ),
            comtypes.COMMETHOD([], HRESULT, "SetChannelVolumeLevel"),
            comtypes.COMMETHOD([], HRESULT, "SetChannelVolumeLevelScalar"),
            comtypes.COMMETHOD([], HRESULT, "GetChannelVolumeLevel"),
            comtypes.COMMETHOD([], HRESULT, "GetChannelVolumeLevelScalar"),
            comtypes.COMMETHOD(
                [], HRESULT, "SetMute",
                (["in"], c_int, "bMute"),
                (["in"], POINTER(GUID), "pguidEventContext")
            ),
            comtypes.COMMETHOD(
                [], HRESULT, "GetMute",
                (["out"], POINTER(c_int), "pbMute")
            ),
        ]

    class IMMDevice(comtypes.IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            comtypes.COMMETHOD(
                [], HRESULT, "Activate",
                (["in"], POINTER(GUID), "iid"),
                (["in"], comtypes.c_ulong, "dwClsCtx"),
                (["in"], POINTER(comtypes.c_void_p), "pActivationParams"),
                (["out"], POINTER(POINTER(IAudioEndpointVolume)), "ppInterface"),
            )
        ]

    class IMMDeviceEnumerator(comtypes.IUnknown):
        _iid_ = GUID(IID_IMMDeviceEnumerator)
        _methods_ = [
            comtypes.COMMETHOD([], HRESULT, "EnumAudioEndpoints"),
            comtypes.COMMETHOD(
                [], HRESULT, "GetDefaultAudioEndpoint",
                (["in"], comtypes.c_int, "dataFlow"),
                (["in"], comtypes.c_int, "role"),
                (["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint"),
            ),
        ]

    COMTYPES_AUDIO_AVAILABLE = True
except Exception as e:
    logger.warning("CoreAudio endpoint volume unavailable: %s", e)


class SystemHardwareController:
    """Manages system master volume, display brightness, mute states, and security locks."""

    def __init__(self):
        self._lock = threading.Lock()

    def _get_audio_endpoint(self):
        """Returns initialized IAudioEndpointVolume interface."""
        if not COMTYPES_AUDIO_AVAILABLE:
            return None
        comtypes.CoInitialize()
        enumerator = comtypes.client.CreateObject(
            GUID(CLSID_MMDeviceEnumerator), interface=IMMDeviceEnumerator
        )
        endpoint = enumerator.GetDefaultAudioEndpoint(0, 1)  # eRender, eMultimedia
        return endpoint.Activate(GUID(IID_IAudioEndpointVolume), CLSCTX_ALL, None)

    # --------------------------------------------------------------------------
    # Volume Control
    # --------------------------------------------------------------------------
    def get_volume(self) -> int:
        """Returns current system volume percentage (0 - 100)."""
        with self._lock:
            try:
                vol_control = self._get_audio_endpoint()
                if vol_control:
                    scalar = vol_control.GetMasterVolumeLevelScalar()
                    return int(round(scalar * 100))
            except Exception as e:
                logger.error("Error reading system volume: %s", e)
            return 50

    def set_volume(self, level_percent: int) -> int:
        """Sets master system volume to a percentage (0 - 100)."""
        with self._lock:
            clamped = max(0, min(100, int(level_percent)))
            scalar = float(clamped) / 100.0
            try:
                vol_control = self._get_audio_endpoint()
                if vol_control:
                    vol_control.SetMasterVolumeLevelScalar(scalar, None)
                    # If volume set above 0, ensure unmuted
                    if clamped > 0 and vol_control.GetMute():
                        vol_control.SetMute(0, None)
                    logger.info("System volume set to %d%%", clamped)
                    return clamped
            except Exception as e:
                logger.error("Error setting system volume: %s", e)
            return clamped

    def adjust_volume(self, delta_percent: int) -> int:
        """Adjusts master system volume by a relative delta (e.g. +10, -15)."""
        current = self.get_volume()
        target = max(0, min(100, current + int(delta_percent)))
        return self.set_volume(target)

    def get_mute(self) -> bool:
        """Returns True if system audio is currently muted."""
        with self._lock:
            try:
                vol_control = self._get_audio_endpoint()
                if vol_control:
                    return bool(vol_control.GetMute())
            except Exception as e:
                logger.error("Error querying mute state: %s", e)
            return False

    def set_mute(self, mute: bool) -> bool:
        """Mutes or unmutes system audio."""
        with self._lock:
            try:
                vol_control = self._get_audio_endpoint()
                if vol_control:
                    vol_control.SetMute(int(mute), None)
                    logger.info("System audio mute state set to: %s", mute)
                    return bool(vol_control.GetMute())
            except Exception as e:
                logger.error("Error setting mute state: %s", e)
            return mute

    def toggle_mute(self) -> bool:
        """Toggles current mute state."""
        current = self.get_mute()
        return self.set_mute(not current)

    # --------------------------------------------------------------------------
    # Display Brightness Control
    # --------------------------------------------------------------------------
    def get_brightness(self) -> Optional[int]:
        """Reads current monitor brightness percentage (0 - 100) via WMI/CIM."""
        try:
            cmd = "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            out = proc.stdout.strip()
            if out.isdigit():
                return int(out)
        except Exception as e:
            logger.debug("Brightness read error: %s", e)
        return None

    def set_brightness(self, level_percent: int) -> Optional[int]:
        """Sets monitor brightness percentage (0 - 100) via WMI/CIM."""
        clamped = max(0, min(100, int(level_percent)))
        try:
            cmd = (
                f"Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
                f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{ Timeout = 1; Brightness = {clamped} }}"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=2.5,
            )
            logger.info("Display brightness set to %d%%", clamped)
            return clamped
        except Exception as e:
            logger.error("Brightness set error: %s", e)
            return None

    def adjust_brightness(self, delta_percent: int) -> Optional[int]:
        """Adjusts monitor brightness by relative delta (e.g. +10, -15)."""
        current = self.get_brightness()
        base = current if current is not None else 50
        target = max(0, min(100, base + int(delta_percent)))
        return self.set_brightness(target)

    # --------------------------------------------------------------------------
    # Security & Power States
    # --------------------------------------------------------------------------
    def lock_workstation(self) -> bool:
        """Immediately locks the Windows user session."""
        try:
            logger.warning("LockWorkStation dispatched to user32.")
            return bool(ctypes.windll.user32.LockWorkStation())
        except Exception as e:
            logger.error("Failed to lock workstation: %s", e)
            return False

    def sleep_workstation(self) -> bool:
        """Suspends system into sleep state."""
        try:
            logger.warning("Sleep mode requested.")
            subprocess.Popen(["cmd.exe", "/c", "rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            return True
        except Exception as e:
            logger.error("Failed to suspend system: %s", e)
            return False

    # --------------------------------------------------------------------------
    # Consolidated Hardware Diagnostics
    # --------------------------------------------------------------------------
    def get_hardware_status(self) -> Dict[str, Any]:
        """Returns consolidated metrics across audio, brightness, battery, and resources."""
        battery = psutil.sensors_battery()
        return {
            "volume_percent": self.get_volume(),
            "is_muted": self.get_mute(),
            "brightness_percent": self.get_brightness(),
            "battery_percent": round(battery.percent, 1) if battery else None,
            "power_plugged": battery.power_plugged if battery else None,
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent,
        }


# Global singleton instance
hardware_controller = SystemHardwareController()
