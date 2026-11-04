import logging
import re
from typing import Optional, Tuple

logger = logging.getLogger("nova.voice.wake_word")

WAKE_PATTERNS = [
    r"^(?:hey\s+|ok\s+|hello\s+|hi\s+|arey\s+|oye\s+|suno\s+|are\s+you\s+there\s+)?(?:nova|noah|noba|knower)\b",
    r"\b(?:hey\s+nova|ok\s+nova|hello\s+nova|hi\s+nova|arey\s+nova|oye\s+nova|suno\s+nova)\b",
    r"\bnova\b",
]


class WakeWordDetector:
    """Detects 'Hey NOVA' wake phrase and strips it from user commands."""

    def __init__(self, wake_word: str = "nova"):
        self.wake_word = wake_word.lower()

    def detect_and_strip(self, text: str) -> Tuple[bool, str]:
        """Checks if text begins with or contains wake phrase, and extracts the remainder command."""
        clean = text.lower().strip()

        # Check explicit patterns
        for pattern in WAKE_PATTERNS:
            match = re.search(pattern, clean)
            if match:
                # Command is everything after the wake word
                start, end = match.span()
                remainder = clean[end:].strip(" ,.?!:;-\t\n")
                logger.info("Wake word detected! Remainder command: '%s'", remainder)
                return True, remainder

        return False, clean


wake_word_detector = WakeWordDetector()
