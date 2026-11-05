import logging
import math
import queue
import threading
from typing import Any, Callable, Optional
import numpy as np
import sounddevice as sd

logger = logging.getLogger("nova.voice.audio_capture")

SAMPLE_RATE = 16000  # 16kHz standard for VAD and Whisper
CHANNELS = 1
BLOCK_SIZE = 1024  # 64ms per audio chunk


class AudioCaptureService:
    """Manages microphone audio stream capture, RMS volume, and buffering."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, block_size: int = BLOCK_SIZE):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.audio_queue: queue.Queue = queue.Queue(maxsize=500)
        self.stream: Optional[sd.InputStream] = None
        self.is_running = False
        self.is_muted = False
        self.current_rms = 0.0
        self._lock = threading.Lock()
        self.on_audio_chunk: Optional[Callable[[np.ndarray, float], None]] = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags) -> None:
        """Low-latency audio input callback from PortAudio."""
        if status:
            logger.debug("PortAudio status flag: %s", status)

        if not self.is_running or self.is_muted:
            self.current_rms = 0.0
            return

        # Audio data is 1D float32 array
        audio_chunk = indata[:, 0].copy()

        # Compute RMS volume level (0.0 to 1.0 scale)
        mean_square = np.mean(audio_chunk**2)
        rms = math.sqrt(max(1e-9, mean_square))
        self.current_rms = min(1.0, rms * 10.0)

        # Notify listener if registered
        if self.on_audio_chunk:
            try:
                self.on_audio_chunk(audio_chunk, self.current_rms)
            except Exception as e:
                logger.debug("Error in on_audio_chunk listener: %s", e)

        # Buffer chunk
        if not self.audio_queue.full():
            self.audio_queue.put(audio_chunk, block=False)

    def start(self) -> bool:
        """Starts the microphone capture stream."""
        with self._lock:
            if self.is_running:
                return True

            try:
                self.stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=CHANNELS,
                    dtype="float32",
                    blocksize=self.block_size,
                    callback=self._audio_callback,
                )
                self.stream.start()
                self.is_running = True
                logger.info("Microphone audio stream started successfully (16kHz Mono).")
                return True
            except Exception as exc:
                logger.error("Failed to start microphone stream: %s", exc)
                self.is_running = False
                return False

    def stop(self) -> None:
        """Stops the audio capture stream."""
        with self._lock:
            self.is_running = False
            self.current_rms = 0.0
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception as exc:
                    logger.debug("Error closing audio stream: %s", exc)
                finally:
                    self.stream = None
            logger.info("Microphone audio stream stopped.")

    def toggle_mute(self) -> bool:
        """Toggles microphone mute state."""
        self.is_muted = not self.is_muted
        logger.info("Microphone mute set to: %s", self.is_muted)
        return self.is_muted

    def get_status(self) -> dict:
        """Returns current audio capture health and status."""
        return {
            "is_running": self.is_running,
            "is_muted": self.is_muted,
            "sample_rate": self.sample_rate,
            "rms_volume": round(self.current_rms, 3),
            "queue_size": self.audio_queue.qsize(),
        }


# Singleton instance
audio_capture = AudioCaptureService()
