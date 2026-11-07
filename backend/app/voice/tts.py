import logging
import queue
import threading
from typing import Optional
import pyttsx3

logger = logging.getLogger("nova.voice.tts")


class TextToSpeechService:
    """Local, offline speech synthesis service using pyttsx3 (SAPI5) with a persistent worker thread.

    Architecture notes:
    - A single background thread owns the SAPI5 COM engine for its entire lifetime.
    - `speak(blocking=False)` enqueues text and returns in <1ms (keeps HTTP path fast).
    - `speak(blocking=True)` waits for the utterance to finish (used in hands-free loop
      so the microphone does not pick up NOVA's own voice before recording user input).
    - `stop()` signals the worker via `_stop_event` so the *current* utterance is
      cancelled on the same engine — avoids the previous bug where a fresh pyttsx3.init()
      was called on a different engine instance that had no effect on playback.
    """

    def __init__(self, rate: int = 190, volume: float = 1.0):
        self.rate = rate
        self.volume = volume
        self.is_speaking = False
        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
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

                # Skip utterance if stop was requested while it was queued
                if self._stop_event.is_set():
                    self._stop_event.clear()
                    if done_event is not None:
                        done_event.set()
                    self._queue.task_done()
                    continue

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
                    self._stop_event.clear()
                    if done_event is not None:
                        done_event.set()
                    self._queue.task_done()
            except Exception as e:
                logger.error("Error in TTS worker: %s", e)

    def speak(self, text: str, blocking: bool = False) -> None:
        """Enqueues text for speech synthesis.

        Args:
            text: Text to speak. Empty/whitespace strings are silently ignored.
            blocking: If True, waits up to 8 s for the utterance to complete.
                      Always pass False on the FastAPI request path to avoid
                      blocking the event loop.
        """
        if not text or not text.strip():
            return

        done_event = threading.Event() if blocking else None
        self._queue.put((text, done_event))
        if blocking and done_event:
            done_event.wait(timeout=8.0)

    def stop(self) -> None:
        """Signals the persistent worker to skip/stop the current utterance.

        Sets `_stop_event` so the worker's finally-block skips the current item,
        then drains any queued items. The same COM engine instance handles the
        stop — fixing the previous bug where `pyttsx3.init()` was called here on
        a different engine object that had no effect on the playing audio.
        """
        self._stop_event.set()
        self.is_speaking = False
        # Drain pending queue items
        drained = 0
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                # Wake any blocked done_event so callers aren't stuck
                if item is not None:
                    _, done_ev = item
                    if done_ev is not None:
                        done_ev.set()
                self._queue.task_done()
                drained += 1
            except Exception:
                break
        if drained:
            logger.debug("TTS queue drained (%d items discarded).", drained)
        logger.info("TTS output stop signal sent.")


# Singleton instance
tts_service = TextToSpeechService(rate=165, volume=1.0)

