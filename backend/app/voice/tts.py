import logging
import queue
import threading
from typing import Optional
import pyttsx3

logger = logging.getLogger("nova.voice.tts")


class TextToSpeechService:
    """Local, offline speech synthesis service using pyttsx3 (SAPI5) with a persistent worker thread."""

    def __init__(self, rate: int = 190, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self.is_speaking = False
        self._queue: queue.Queue = queue.Queue()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="NOVA-TTS-Worker",
        )
        self._worker_thread.start()

    def _worker_loop(self) -> None:
        """Dedicated background thread holding a persistent SAPI5 COM engine instance."""
        engine: Optional[pyttsx3.Engine] = None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", self.rate)
            engine.setProperty("volume", self.volume)
            logger.info("Persistent pyttsx3 SAPI5 TTS engine initialized.")
        except Exception as e:
            logger.error("Failed to initialize persistent pyttsx3 engine: %s", e)

        while True:
            try:
                item = self._queue.get()
                if item is None:
                    break
                text, done_event = item

                self.is_speaking = True
                try:
                    if engine is None:
                        engine = pyttsx3.init()
                        engine.setProperty("rate", self.rate)
                        engine.setProperty("volume", self.volume)
                    logger.info("Speaking: '%s'", text)
                    engine.say(text)
                    engine.runAndWait()
                except Exception as exc:
                    logger.error("TTS speech error: %s", exc)
                finally:
                    self.is_speaking = False
                    if done_event is not None:
                        done_event.set()
                    self._queue.task_done()
            except Exception as e:
                logger.error("Error in TTS worker: %s", e)

    def speak(self, text: str, blocking: bool = False) -> None:
        """Speaks text using local TTS. Non-blocking by default to eliminate HTTP latency."""
        if not text or not text.strip():
            return

        done_event = threading.Event() if blocking else None
        self._queue.put((text, done_event))
        if blocking and done_event:
            done_event.wait(timeout=8.0)

    def stop(self) -> None:
        """Stops current speech output (interruption support)."""
        self.is_speaking = False
        # Clear queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Exception:
                break
        try:
            e = pyttsx3.init()
            e.stop()
            logger.info("TTS output stopped.")
        except Exception as exc:
            logger.debug("Error while stopping TTS: %s", exc)


# Singleton instance
tts_service = TextToSpeechService(rate=190, volume=1.0)
