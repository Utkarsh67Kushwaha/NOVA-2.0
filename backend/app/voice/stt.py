import logging
from pathlib import Path
import time
from typing import Optional
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger("nova.voice.stt")


class SpeechToTextService:
    """Local, quantized speech-to-text service using Faster-Whisper."""

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = Path(__file__).resolve().parent.parent.parent / "models" / "whisper"
        self._model: Optional[WhisperModel] = None

    def _get_model(self) -> WhisperModel:
        """Lazy loader for Whisper model to preserve RAM/VRAM until needed."""
        if self._model is None:
            self.download_root.mkdir(parents=True, exist_ok=True)
            logger.info(
                "Loading Faster-Whisper model '%s' (Device: %s, Compute: %s)...",
                self.model_size,
                self.device,
                self.compute_type,
            )
            start_load = time.perf_counter()
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                download_root=str(self.download_root),
            )
            logger.info("Loaded Faster-Whisper model in %.2fs", time.perf_counter() - start_load)
        return self._model

    def transcribe(self, audio_data: np.ndarray, language: Optional[str] = None) -> str:
        """Transcribes 16kHz float32 audio numpy array to text."""
        if len(audio_data) == 0:
            return ""

        model = self._get_model()
        start_time = time.perf_counter()

        # faster-whisper accepts float32 numpy array normalized between -1.0 and 1.0
        segments, info = model.transcribe(
            audio_data,
            beam_size=3,
            language=language,
            vad_filter=False,  # We already perform VAD before feeding
            temperature=0.0,
        )

        transcription = " ".join([segment.text for segment in segments]).strip()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 1)

        logger.info(
            "Transcribed in %sms (Detected lang: %s, prob: %.2f): '%s'",
            elapsed_ms,
            info.language,
            info.language_probability,
            transcription,
        )
        return transcription


# Singleton instance
stt_service = SpeechToTextService(model_size="base", device="cpu", compute_type="int8")
