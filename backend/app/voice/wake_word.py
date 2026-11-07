import logging
import re
from typing import Tuple

logger = logging.getLogger("nova.voice.wake_word")

WAKE_REGEX = r"\b(?:hey\s+|ok\s+|hello\s+|hi\s+|arey\s+|oye\s+|suno\s+|bhai\s+|yaar\s+|are\s+you\s+there\s+)?(?:nova|noah|noba|knower)\b"


class WakeWordDetector:
    """Detects 'Hey NOVA' wake phrase and strips it from user commands, regardless of position."""

    def __init__(self, wake_word: str = "nova"):
        self.wake_word = wake_word.lower()

    def detect_and_strip(self, text: str) -> Tuple[bool, str]:
        """Checks if text begins with, ends with, or contains wake phrase, and extracts the remainder command."""
        clean = text.lower().strip()

        match = re.search(WAKE_REGEX, clean, flags=re.IGNORECASE)
        if match:
            # Strip the wake phrase from the text wherever it occurs
            remainder = re.sub(WAKE_REGEX, " ", clean, flags=re.IGNORECASE)
            remainder = re.sub(r"\s+", " ", remainder).strip(" ,.?!:;-\t\n")
            logger.info("Wake word detected! Remainder command: '%s'", remainder)
            return True, remainder

        return False, clean


wake_word_detector = WakeWordDetector()
