import logging
from pathlib import Path
import threading
import time
from typing import Optional
import numpy as np
from faster_whisper import WhisperModel

logger = logging.getLogger("nova.voice.stt")

# Context prompt to bias Whisper toward recognizing bilingual Indian/Hinglish commands & popular desktop tasks
DEFAULT_INITIAL_PROMPT = (
    "Hey NOVA desktop assistant. Bilingual Hinglish & English voice commands: "
    "screenshot le lo, screenshot lo, take screenshot, sc le lo, ek screenshot lo, screen capture karo, "
    "volume 50 percent karo, volume badhao, volume kam karo, aawaz badhao, aawaz kam karo, mute karo, unmute karo, "
    "brightness badhao, brightness kam karo, screen light 70 percent karo, "
    "pc lock karo, computer lock karo, lock my pc, "
    "notepad kholo, calculator kholo, chrome kholo, spotify kholo, "
    "kesariya song play karo, gaana bajao, gana roko, pause music, resume music, agla gana, "
    "paani peene ka reminder lagao, 5 minute baad reminder lagao, remind me to drink water."
)


class SpeechToTextService:
    """Local, quantized speech-to-text service using Faster-Whisper with peak normalization and pre-warming."""

    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = Path(__file__).resolve().parent.parent.parent / "models" / "whisper"
        self._model: Optional[WhisperModel] = None
        self._warmup_started = False

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

    def warmup(self) -> None:
        """Pre-warms the Whisper model asynchronously on startup to eliminate first-utterance cold-start delay."""
        if self._warmup_started:
            return
        self._warmup_started = True

        def _worker():
            try:
                model = self._get_model()
                # Run small dummy inference to initialize computation graph in memory
                dummy = np.zeros(16000, dtype=np.float32)
                _ = list(model.transcribe(dummy, beam_size=1)[0])
                logger.info("Faster-Whisper model asynchronously pre-warmed and ready.")
            except Exception as e:
                logger.debug("Whisper pre-warm skipped or deferred: %s", e)

        threading.Thread(target=_worker, name="WhisperWarmupWorker", daemon=True).start()

    def transcribe(
        self,
        audio_data: np.ndarray,
        language: Optional[str] = None,
        initial_prompt: Optional[str] = None,
    ) -> str:
        """Transcribes 16kHz float32 audio numpy array to text with audio peak normalization."""
        if len(audio_data) == 0:
            return ""

        # Normalize audio peak to standard 0.90 to amplify soft/distant speech
        # Dynamic noise gate & automatic gain control (AGC) for distant/soft voices
        peak = float(np.max(np.abs(audio_data)))
        if peak > 0.0008:
            # Clean tiny background mic hiss
            cleaned = np.where(np.abs(audio_data) < 0.0002, 0.0, audio_data)
            normalized_audio = (cleaned / peak) * 0.92
        else:
            normalized_audio = audio_data

        model = self._get_model()
        start_time = time.perf_counter()
        prompt = initial_prompt or DEFAULT_INITIAL_PROMPT

        target_language = language

        segments, info = model.transcribe(
            normalized_audio,
            beam_size=5,
            language=target_language,
            initial_prompt=prompt,
            vad_filter=False,  # We already perform sensitive adaptive VAD before feeding
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
