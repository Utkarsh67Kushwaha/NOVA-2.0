import logging
import math
import time
from typing import List, Optional
import numpy as np

logger = logging.getLogger("nova.voice.vad")


class VoiceActivityDetector:
    """Adaptive energy, noise-floor tracking, and zero-crossing rate Voice Activity Detector for human voice."""

    def __init__(
        self,
        energy_threshold: float = 0.0014,
        silence_timeout_sec: float = 1.1,
        min_speech_duration_sec: float = 0.22,
    ):
        self.energy_threshold = energy_threshold
        self.silence_timeout_sec = silence_timeout_sec
        self.min_speech_duration_sec = min_speech_duration_sec

        self.is_speaking = False
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.recorded_frames: List[np.ndarray] = []
        self.pre_speech_buffer: List[np.ndarray] = []  # 256ms pre-roll buffer to prevent cutting first phoneme
        self.ambient_noise_level: float = 0.001

    def is_speech_frame(self, audio_chunk: np.ndarray) -> bool:
        """Determines if a single audio chunk contains human voice activity with adaptive noise rejection."""
        # Calculate RMS energy
        energy = math.sqrt(max(1e-9, float(np.mean(audio_chunk**2))))

        # Update rolling ambient noise floor during non-speech periods
        if not self.is_speaking:
            self.ambient_noise_level = 0.95 * self.ambient_noise_level + 0.05 * energy

        # Dynamic threshold adapts to background noise but has a hard ceiling of 0.005
        # so normal human voice (typically 0.008 to 0.04) can NEVER be blocked by loud noise
        effective_threshold = min(0.005, max(self.energy_threshold, self.ambient_noise_level * 1.25))

        # Calculate Zero Crossing Rate (ZCR) - Human speech typically ranges 0.01 to 0.65
        zero_crossings = np.nonzero(np.diff(audio_chunk > 0))[0]
        zcr = len(zero_crossings) / max(1, len(audio_chunk))

        return energy > effective_threshold and (0.01 < zcr < 0.68)

    def process_chunk(self, audio_chunk: np.ndarray) -> Optional[np.ndarray]:
        """Processes an incoming chunk. Returns complete speech array when silence finishes speaking."""
        has_voice = self.is_speech_frame(audio_chunk)
        now = time.time()

        if has_voice:
            if not self.is_speaking:
                self.is_speaking = True
                self.speech_start_time = now
                # Include pre-speech buffer so leading consonant is never lost
                self.recorded_frames = list(self.pre_speech_buffer)
                self.pre_speech_buffer = []
                logger.debug("Speech activity detected. Starting recording.")

            self.last_speech_time = now
            self.recorded_frames.append(audio_chunk)
            return None

        # Silent frame
        if not self.is_speaking:
            # Maintain up to 4 frames (256ms) of pre-roll audio
            self.pre_speech_buffer.append(audio_chunk)
            if len(self.pre_speech_buffer) > 4:
                self.pre_speech_buffer.pop(0)
            return None

        # If currently in a speaking session but this frame is silent
        self.recorded_frames.append(audio_chunk)

        # Check if silence timeout has elapsed (1.1s for natural human cadence)
        if self.last_speech_time and (now - self.last_speech_time >= self.silence_timeout_sec):
            total_duration = now - (self.speech_start_time or now)
            self.is_speaking = False

            if total_duration >= self.min_speech_duration_sec and self.recorded_frames:
                logger.info("Speech session completed (%.2f seconds audio captured).", total_duration)
                complete_audio = np.concatenate(self.recorded_frames)
                self.recorded_frames = []
                self.pre_speech_buffer = []
                return complete_audio
            else:
                logger.debug("Discarding short noise burst (%.2f sec).", total_duration)
                self.recorded_frames = []
                self.pre_speech_buffer = []
                return None

        return None

    def reset(self) -> None:
        """Resets detector state and recalibrates noise floor."""
        self.is_speaking = False
        self.speech_start_time = None
        self.last_speech_time = None
        self.recorded_frames = []
        self.pre_speech_buffer = []
        self.ambient_noise_level = 0.001
