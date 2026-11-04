import logging
import threading
import time
from typing import Optional
import pyttsx3

logger = logging.getLogger("nova.voice.tts")


class TextToSpeechService:
    """Local, offline speech synthesis service using pyttsx3 (SAPI5)."""

    def __init__(self, rate: int = 180, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self._lock = threading.Lock()
        self.is_speaking = False

    def speak(self, text: str, blocking: bool = False) -> None:
        """Speaks text using local TTS. Runs non-blocking by default."""
        if not text or not text.strip():
            return

        def _run_tts():
            with self._lock:
                self.is_speaking = True
                try:
                    engine = pyttsx3.init()
                    engine.setProperty("rate", self.rate)
                    engine.setProperty("volume", self.volume)
                    logger.info("Speaking: '%s'", text)
                    engine.say(text)
                    engine.runAndWait()
                    engine.stop()
                except Exception as exc:
                    logger.error("TTS speech error: %s", exc)
                finally:
                    self.is_speaking = False

        if blocking:
            _run_tts()
        else:
            thread = threading.Thread(target=_run_tts, daemon=True)
            thread.start()

    def stop(self) -> None:
        """Stops current speech output (interruption support)."""
        self.is_speaking = False
        try:
            engine = pyttsx3.init()
            engine.stop()
            logger.info("TTS output stopped.")
        except Exception as exc:
            logger.debug("Error while stopping TTS: %s", exc)


# Singleton instance
tts_service = TextToSpeechService(rate=185, volume=1.0)
