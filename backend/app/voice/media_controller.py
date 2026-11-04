"""
NOVA Media & Audio Controller
Manages system audio playback state inspection, Windows System Media Transport Controls (SMTC),
and hardware media key emulation (Play/Pause, Stop, Next, Previous).
"""

import ctypes
from ctypes import HRESULT, POINTER, c_float
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger("nova.voice.media_controller")

# Windows Virtual Key Codes for Hardware Media Control
VK_VOLUME_MUTE = 0xAD
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

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
    """Controls system-wide media playback and inspects speaker audio emission."""

    def __init__(self):
        self._lock = threading.Lock()
        self._paused_for_voice: bool = False

    def is_system_audio_playing(self, threshold: float = 0.012) -> bool:
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
        """Dispatches hardware media key event using Win32 API."""
        try:
            user32 = ctypes.windll.user32
            # Key down
            user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
            time.sleep(0.02)
            # Key up
            user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
            return True
        except Exception as exc:
            logger.error("Error sending virtual media key %s: %s", vk_code, exc)
            return False

    def pause_if_playing(self) -> bool:
        """If sound is currently emitting from speakers, pauses media and records state."""
        with self._lock:
            if self.is_system_audio_playing():
                logger.info("Active audio output detected on speakers. Pausing media for voice recognition.")
                self.send_key(VK_MEDIA_PLAY_PAUSE)
                self._paused_for_voice = True
                return True
            return False

    def resume_if_paused_by_voice(self) -> bool:
        """Resumes playback if media was paused specifically by the wake-word listener."""
        with self._lock:
            if self._paused_for_voice:
                logger.info("Resuming media playback that was paused for voice command.")
                self.send_key(VK_MEDIA_PLAY_PAUSE)
                self._paused_for_voice = False
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
        return self.send_key(VK_MEDIA_PLAY_PAUSE)

    def resume(self) -> bool:
        """Resumes media playback and clears auto-resume flag."""
        self.clear_paused_state()
        return self.send_key(VK_MEDIA_PLAY_PAUSE)

    def stop(self) -> bool:
        """Stops media playback and clears auto-resume flag."""
        self.clear_paused_state()
        return self.send_key(VK_MEDIA_STOP)

    def next_track(self) -> bool:
        return self.send_key(VK_MEDIA_NEXT_TRACK)

    def previous_track(self) -> bool:
        return self.send_key(VK_MEDIA_PREV_TRACK)


# Global singleton instance
media_controller = MediaController()
