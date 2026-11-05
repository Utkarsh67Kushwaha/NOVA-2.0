"""NOVA Gemini AI Brain & Conversational Service.
Connects to Google Gemini API for intelligent, natural language Q&A, coding assistance,
and general conversation in English, Hindi, and Hinglish.
Includes a smart offline conversational engine when no API key is set.
"""

import os
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("nova.services.gemini")

SYSTEM_INSTRUCTION = (
    "You are NOVA, a fast, intelligent, and friendly desktop AI voice assistant built for Utkarsh. "
    "You speak naturally in Hindi, Hinglish, or English depending on how the user talks to you. "
    "Keep responses concise, conversational, and direct (1-3 sentences) so they sound natural when read aloud via text-to-speech. "
    "Never use markdown tables, asterisks for formatting, or excessive lists. Be warm, accurate, and helpful."
)

DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-1.5-flash"


class GeminiService:
    def __init__(self):
        self.api_key: Optional[str] = self._load_api_key()
        self.chat_history: List[Dict[str, Any]] = []
        self._max_history = 10

    def _load_api_key(self) -> Optional[str]:
        # 1. Environment variable
        key = os.environ.get("GEMINI_API_KEY")
        if key and key.strip():
            return key.strip()

        # 2. Check .env file
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"\'')
                        if val:
                            return val
            except Exception:
                pass
        return None

    def set_api_key(self, key: str) -> bool:
        """Dynamically updates the Gemini API key and persists to .env."""
        cleaned = key.strip()
        self.api_key = cleaned
        env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
        try:
            lines = []
            found = False
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("GEMINI_API_KEY="):
                        lines.append(f'GEMINI_API_KEY="{cleaned}"')
                        found = True
                    else:
                        lines.append(line)
            if not found:
                lines.append(f'GEMINI_API_KEY="{cleaned}"')
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            logger.info("Persisted new GEMINI_API_KEY to .env successfully.")
            return True
        except Exception as e:
            logger.error("Failed to persist GEMINI_API_KEY: %s", e)
            return False

    def is_configured(self) -> bool:
        """Returns True if a valid Gemini API key is configured."""
        return bool(self.api_key and len(self.api_key) > 10)

    def ask(self, user_query: str) -> str:
        """Generates an intelligent conversational response via Gemini API or offline fallback."""
        cleaned = user_query.strip()
        if not cleaned:
            return "Aapne kuch bola nahi, kripya bolein."

        # If API key configured, use Google Gemini
        if self.is_configured():
            res = self._ask_gemini(cleaned)
            if res:
                return res

        # Otherwise, use rich offline conversational intelligence
        return self._offline_conversational_brain(cleaned)

    def _ask_gemini(self, query: str) -> Optional[str]:
        """Calls Google Gemini REST API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{DEFAULT_MODEL}:generateContent?key={self.api_key}"

        # Build contents with context
        messages = []
        for turn in self.chat_history[-6:]:
            messages.append(turn)

        messages.append({"role": "user", "parts": [{"text": query}]})

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": messages,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 200,
            },
        }

        try:
            with httpx.Client(timeout=6.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            # Clean markdown asterisks so speech sounds clean
                            text = re.sub(r"[*_#`]+", "", text)
                            # Record history
                            self.chat_history.append({"role": "user", "parts": [{"text": query}]})
                            self.chat_history.append({"role": "model", "parts": [{"text": text}]})
                            if len(self.chat_history) > self._max_history:
                                self.chat_history = self.chat_history[-self._max_history:]
                            return text
                else:
                    logger.warning("Gemini API returned status %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.error("Gemini API call failed: %s", e)

        return None

    def _offline_conversational_brain(self, query: str) -> str:
        """Fast, robust offline conversational AI answering small talk, identity, and queries."""
        lowered = query.lower().strip()

        # 1. Identity & Persona
        if any(w in lowered for w in ["tum kaun ho", "who are you", "naam kya hai", "what is your name", "kya naam hai"]):
            return "Main NOVA hoon, aapka personal intelligent desktop AI assistant. Main aapki har command sunkar execute kar sakta hoon!"

        # 2. Greetings
        if any(w in lowered for w in ["kaise ho", "how are you", "kya haal", "sab theek", "kaisa chal raha"]):
            return "Main bilkul badiya aur ready hoon! Aap bataiye aaj computer me kya kaam karna hai?"

        if any(w in lowered for w in ["hello", "hi nova", "hey nova", "namaste", "pranaam"]):
            return "Hello! Main sun raha hoon, bataiye kya help chahiye?"

        # 3. Capabilities & Help
        if any(w in lowered for w in ["kya kar sakte ho", "what can you do", "features", "madad", "help"]):
            return (
                "Main aapke computer ka volume aur brightness control kar sakta hoon, screenshot le sakta hoon, "
                "apps launch kar sakta hoon, reminders set kar sakta hoon, YouTube par gaane chala sakta hoon, aur PC lock kar sakta hoon!"
            )

        # 4. Time & Date
        if any(w in lowered for w in ["time", "samay", "kitne baje", "kya time", "current time"]):
            now_str = datetime.now().strftime("%I:%M %p")
            return f"Abhi time {now_str} ho raha hai."

        if any(w in lowered for w in ["date", "tareekh", "aaj kya din", "today"]):
            now_str = datetime.now().strftime("%A, %d %B %Y")
            return f"Aaj {now_str} hai."

        # 5. Humor / Jokes
        if any(w in lowered for w in ["joke", "chutkula", "hasao", "funny"]):
            jokes = [
                "Programmer ne biwi se pucha: Bazaar se 1 litre doodh lao, agar ande mile toh 10 le aana. Wo 10 litre doodh le aaya kyunki ande mil gaye the!",
                "Computer doctor ke paas gaya aur bola: Doctor sahab, mujhe lagta hai mujhe virus ho gaya hai! Doctor bola: Windows khol ke taaza hawa lo!",
            ]
            import random
            return random.choice(jokes)

        # 6. Gratitude / Courtesies
        if any(w in lowered for w in ["thank you", "dhanyawad", "shukriya", "thanks", "badhiya"]):
            return "Aapka swagat hai! Kabhi bhi koi zaroorat ho toh bas boliye."

        # 7. Fallback for open-domain questions when API key is not yet set
        return (
            f"Maine aapka sawal sun liya: '{query}'. "
            "Iska detailed AI answer paane ke liye aap Dashboard Settings me apna free Gemini API Key connect kar sakte hain!"
        )


# Global singleton
gemini_service = GeminiService()
