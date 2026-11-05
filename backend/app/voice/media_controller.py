"""
NOVA Media & Audio Controller
Manages system audio playback inspection, Windows System Media Transport Controls (SMTC),
and hardware media key emulation with scan codes (Play/Pause, Stop, Next, Previous).
"""

import ctypes
from ctypes import HRESULT, POINTER, c_float, c_int
import logging
from pathlib import Path
import subprocess
import threading
import time
from typing import Optional

logger = logging.getLogger("nova.voice.media_controller")

# Windows Virtual Key Codes
VK_VOLUME_MUTE = 0xAD
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

SMTC_SCRIPT_PATH = Path(__file__).resolve().parent / "smtc_helper.ps1"

# Initialize Windows CoreAudio COM interfaces for audio peak monitoring
COMTYPES_AVAILABLE = False
try:
    import comtypes
    import comtypes.client
    from comtypes import CLSCTX_ALL, GUID

    CLSID_MMDeviceEnumerator = GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")
    IID_IMMDeviceEnumerator = GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")
    IID_IAudioMeterInformation = GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")

    class IAudioMeterInformation(comtypes.IUnknown):
        _iid_ = IID_IAudioMeterInformation
        _methods_ = [
            comtypes.COMMETHOD(
                [], HRESULT, "GetPeakValue",
                (["out"], POINTER(c_float), "pfPeak")
            )
        ]

    class IMMDevice(comtypes.IUnknown):
        _iid_ = GUID("{D666063F-1587-4E43-81F1-B948E807363F}")
        _methods_ = [
            comtypes.COMMETHOD(
                [], HRESULT, "Activate",
                (["in"], POINTER(GUID), "iid"),
                (["in"], comtypes.c_ulong, "dwClsCtx"),
                (["in"], POINTER(comtypes.c_void_p), "pActivationParams"),
                (["out"], POINTER(POINTER(IAudioMeterInformation)), "ppInterface"),
            )
        ]

    class IMMDeviceEnumerator(comtypes.IUnknown):
        _iid_ = IID_IMMDeviceEnumerator
        _methods_ = [
            comtypes.COMMETHOD([], HRESULT, "EnumAudioEndpoints"),
            comtypes.COMMETHOD(
                [], HRESULT, "GetDefaultAudioEndpoint",
                (["in"], comtypes.c_int, "dataFlow"),
                (["in"], comtypes.c_int, "role"),
                (["out"], POINTER(POINTER(IMMDevice)), "ppEndpoint"),
            ),
        ]

    COMTYPES_AVAILABLE = True
except Exception as exc:
    logger.warning("CoreAudio COM initialization deferred or unavailable: %s", exc)


class MediaController:
    """Controls system-wide media playback using SMTC and hardware media keys."""

    def __init__(self):
        self._lock = threading.Lock()
        self._paused_for_voice: bool = False

    def is_system_audio_playing(self, threshold: float = 0.003) -> bool:
        """Returns True if speakers or default audio endpoint is actively outputting sound."""
        if not COMTYPES_AVAILABLE:
            return False
        try:
            comtypes.CoInitialize()
            try:
                enumerator = comtypes.client.CreateObject(
                    CLSID_MMDeviceEnumerator, interface=IMMDeviceEnumerator
                )
                endpoint = enumerator.GetDefaultAudioEndpoint(0, 1)  # 0=eRender, 1=eMultimedia
                meter = endpoint.Activate(IID_IAudioMeterInformation, CLSCTX_ALL, None)
                peak = float(meter.GetPeakValue())
                return peak >= threshold
            finally:
                comtypes.CoUninitialize()
        except Exception as exc:
            logger.debug("Failed to query CoreAudio peak value: %s", exc)
            return False

    def send_key(self, vk_code: int) -> bool:
        """Dispatches hardware media key event using Win32 API with scan code mapping."""
        try:
            user32 = ctypes.windll.user32
            scan_code = user32.MapVirtualKeyW(vk_code, 0)
            # Key down with extended key flag and scan code
            user32.keybd_event(vk_code, scan_code, KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.02)
            # Key up
            user32.keybd_event(vk_code, scan_code, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            return True
        except Exception as exc:
            logger.error("Error sending virtual media key %s: %s", vk_code, exc)
            return False

    def smtc_action(self, action: str) -> bool:
        """Executes native Windows System Media Transport Controls pause/resume."""
        if not SMTC_SCRIPT_PATH.exists():
            return False
        try:
            proc = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SMTC_SCRIPT_PATH),
                    "-Action",
                    action,
                ],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            out = proc.stdout.strip().lower()
            return "true" in out
        except Exception as e:
            logger.debug("SMTC action error: %s", e)
            return False

    def pause_media(self) -> bool:
        """Pauses active playback across Chrome, Spotify, Edge, or Windows apps."""
        with self._lock:
            self._paused_for_voice = True
            logger.info("Pausing active media playback via Windows SMTC & hardware keys.")
            # Trigger SMTC pause in thread or direct
            smtc_ok = self.smtc_action("pause")
            key_ok = self.send_key(VK_MEDIA_PLAY_PAUSE)
            return smtc_ok or key_ok

    def resume_media(self) -> bool:
        """Resumes media playback."""
        with self._lock:
            self._paused_for_voice = False
            logger.info("Resuming media playback via Windows SMTC & hardware keys.")
            smtc_ok = self.smtc_action("resume")
            key_ok = self.send_key(VK_MEDIA_PLAY_PAUSE)
            return smtc_ok or key_ok

    def pause_if_playing(self) -> bool:
        """Pauses media unconditionally when wake word is detected."""
        return self.pause_media()

    def resume_if_paused_by_voice(self) -> bool:
        """Resumes playback if media was paused specifically by the wake-word listener."""
        with self._lock:
            if self._paused_for_voice:
                self._paused_for_voice = False
                logger.info("Auto-resuming media playback after voice response completed.")
                # Run SMTC resume in a background thread to prevent latency
                threading.Thread(target=self.resume_media, daemon=True).start()
                return True
            return False

    def clear_paused_state(self) -> None:
        """Clears the pause flag (e.g. when a new song is started or user explicitly commanded stop)."""
        with self._lock:
            self._paused_for_voice = False

    @property
    def is_paused_for_voice(self) -> bool:
        with self._lock:
            return self._paused_for_voice

    def toggle_playback(self) -> bool:
        """Toggles Play/Pause unconditionally."""
        return self.send_key(VK_MEDIA_PLAY_PAUSE)

    def pause(self) -> bool:
        """Pauses media playback and clears auto-resume flag."""
        self.clear_paused_state()
        return self.pause_media()

    def resume(self) -> bool:
        """Resumes media playback and clears auto-resume flag."""
        self.clear_paused_state()
        return self.resume_media()

    def stop(self) -> bool:
        """Stops media playback and clears auto-resume flag."""
        self.clear_paused_state()
        self.smtc_action("pause")
        return self.send_key(VK_MEDIA_STOP)

    def next_track(self) -> bool:
        return self.send_key(VK_MEDIA_NEXT_TRACK)

    def previous_track(self) -> bool:
        return self.send_key(VK_MEDIA_PREV_TRACK)


# Global singleton instance
media_controller = MediaController()
