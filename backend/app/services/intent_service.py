import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
import numpy as np

logger = logging.getLogger("nova.intent_service")

# Entity dictionaries
KNOWN_APPS = [
    "chrome",
    "vscode",
    "visual studio code",
    "spotify",
    "calculator",
    "notepad",
    "telegram",
    "excel",
    "word",
    "paint",
    "control panel",
    "edge",
    "powershell",
    "cmd",
    "command prompt",
    "discord",
    "whatsapp",
    "file explorer",
    "camera",
    "brave",
    "settings",
    "task manager",
]


class IntentClassifierService:
    """Production service for intent prediction and entity extraction."""

    def __init__(self, model_path: Optional[Path] = None):
        if model_path is None:
            base_dir = Path(__file__).resolve().parent.parent.parent
            model_path = base_dir / "models" / "intent_model.joblib"

        self.model_path = model_path
        self.bundle: Optional[Dict[str, Any]] = None
        self.model = None
        self.vectorizer = None
        self.label_encoder = None
        self.confidence_threshold = 0.65
        self.model_name = "Unknown"
        self._load_model()

    def _load_model(self) -> None:
        """Loads serialized model bundle."""
        if not self.model_path.exists():
            logger.warning("Intent model bundle not found at %s", self.model_path)
            return

        try:
            self.bundle = joblib.load(self.model_path)
            self.model = self.bundle["model"]
            self.vectorizer = self.bundle["vectorizer"]
            self.label_encoder = self.bundle["label_encoder"]
            self.confidence_threshold = self.bundle.get("confidence_threshold", 0.65)
            self.model_name = self.bundle.get("model_name", "Trained Classifier")
            logger.info("Loaded ML Intent model '%s' successfully.", self.model_name)
        except Exception as exc:
            logger.error("Failed to load intent model: %s", exc)

    def is_ready(self) -> bool:
        """Returns True if model is loaded and ready for inference."""
        return self.model is not None and self.vectorizer is not None

    def normalize(self, text: str) -> str:
        """Preprocesses input query and corrects common phonetic STT errors."""
        text = text.lower().strip()
        text = re.sub(r"[.!?,\"]+$", "", text).strip()
        text = re.sub(r"\s+", " ", text)

        # Phonetic corrections for common Faster-Whisper mishearings on Indian/Hinglish phrases
        whisper_phonetic_fixes = [
            (r"\b(?:lay|let|play)\s+it\s+serious\s+on\b", "play kesariya song"),
            (r"\b(?:lay|play)\s+it\s+serious\b", "play kesariya"),
            (r"\b(?:it\s+)?serious\s+on\b", "kesariya song"),
            (r"\bserious\s+song\b", "kesariya song"),
            (r"\b(?:cash\s*area|kiss\s*area)\b", "kesariya"),
            (r"\b(?:but\s+leave\s*,?\s*but\s+leave|but\s+leave)\b", "bollywood"),
        ]
        for pattern, replacement in whisper_phonetic_fixes:
            text = re.sub(pattern, replacement, text)

        return text

    def extract_entities(self, text: str, intent: str) -> Dict[str, Any]:
        """Rule and regex-based entity extractor for desktop commands."""
        clean = self.normalize(text)
        entities: Dict[str, Any] = {}

        if intent == "OPEN_APP":
            for app in KNOWN_APPS:
                if app in clean:
                    entities["app_name"] = app
                    break

        elif intent == "PLAY_MUSIC":
            clean_lower = clean.lower().strip()
            # Media control actions
            pause_keywords = [
                "pause", "stop", "pause the song", "pause music", "stop music",
                "gana roko", "gana band karo", "music band karo", "ruk jao", "chup ho jao",
                "pause kar do", "pause karo", "stop the song"
            ]
            resume_keywords = [
                "resume", "play", "continue", "resume the song", "resume song", "resume music",
                "gana chalao", "wapas bajao", "fir se chalao", "aage chalao", "aage play karo"
            ]
            next_keywords = ["next song", "agla gana", "skip song", "next track", "skip"]
            prev_keywords = ["previous song", "pichla gana", "prev song", "previous track"]

            if clean_lower in pause_keywords:
                entities["action"] = "pause"
                entities["track_or_query"] = ""
                return entities

            if clean_lower in resume_keywords:
                entities["action"] = "resume"
                entities["track_or_query"] = ""
                return entities

            if any(k in clean_lower for k in next_keywords):
                entities["action"] = "next"
                entities["track_or_query"] = ""
                return entities

            if any(k in clean_lower for k in prev_keywords):
                entities["action"] = "previous"
                entities["track_or_query"] = ""
                return entities

            entities["action"] = "play"
            # Extract song or artist name
            # 1. Check: [song] (song) play karo/kare/bajao/chalao
            end_match = re.search(
                r"^(.*?)\s*(?:ko\s+)?(?:song\s+)?(?:play\s+karo|play\s+kare|bajao|chalao|lagao|sunao|play)\s*(?:karo|kare)?$",
                clean,
            )
            raw_track = clean
            if end_match and end_match.group(1).strip():
                raw_track = end_match.group(1).strip()
            else:
                # 2. Check: play/bajao [song]
                start_match = re.search(
                    r"^(?:play|bajao|chalao|lagao|sunao)\s+(?:some\s+)?(?:music\s+)?(?:on\s+spotify\s+)?(.+?)(?:\s+(?:karo|kare))?$",
                    clean,
                )
                if start_match and start_match.group(1).strip():
                    raw_track = start_match.group(1).strip()

            raw_track = re.sub(r"^[,\s.!?\"'\-:]+|[,\s.!?\"'\-:]+$", "", raw_track).strip()
            raw_track = re.sub(r"^(?:song|gana|gaana)[,\s]+", "", raw_track, flags=re.IGNORECASE).strip()
            entities["track_or_query"] = raw_track

        elif intent == "FILE_SEARCH":
            # Extract target file or extension
            file_match = re.search(
                r"([\w\-_\.]+\.(?:pdf|docx|xlsx|pptx|txt|csv|zip|png|jpg|mp4))",
                clean,
            )
            if file_match:
                entities["file_name"] = file_match.group(1)
            else:
                entities["file_query"] = clean

        elif intent == "BROWSER_ACTION":
            # Extract search query
            search_match = re.search(
                r"(?:search|google par|google pe|youtube par|khojo)\s+(.+?)(?:\s+on\s+google|\s+in\s+browser|\s+on\s+youtube|$)",
                clean,
            )
            if search_match:
                entities["search_query"] = search_match.group(1).strip()

        elif intent == "SYSTEM_INFO":
            targets = []
            for t in ["ram", "cpu", "battery", "disk", "storage", "wifi", "network", "hardware", "process"]:
                if t in clean:
                    targets.append(t)
            entities["metric_targets"] = targets if targets else ["overview"]

        elif intent == "REMINDER":
            # Extract time expression
            time_match = re.search(
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|baje|hours?|minutes?|mins?))",
                clean,
            )
            if time_match:
                entities["time_expression"] = time_match.group(1)

        return entities

    def predict(self, text: str) -> Dict[str, Any]:
        """Predicts intent with calibrated confidence thresholding."""
        if not self.is_ready():
            return {
                "error": "ML model is not loaded.",
                "intent": "UNKNOWN_INTENT",
                "confidence": 0.0,
                "needs_clarification": True,
            }

        clean = self.normalize(text)
        if not clean:
            return {
                "intent": "UNKNOWN_INTENT",
                "confidence": 0.0,
                "needs_clarification": True,
                "clarification_message": "Command was empty. Please provide a command.",
            }

        # Rule priority for Hardware & System Controls (Volume, Brightness, Lock)
        # 1. Volume commands
        vol_set_match = re.search(
            r"\b(?:volume|sound|aawaz)\s+(?:ko\s+)?(\d{1,3})\s*(?:%|percent)?(?:\s*(?:pe|par|karo|set|kar do))?\b",
            clean,
        ) or re.search(
            r"\b(?:set\s+)?(?:volume|sound|aawaz)\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?\b",
            clean,
        )
        if vol_set_match:
            val = int(vol_set_match.group(1))
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": "set_volume", "value": val},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["volume badhao", "volume up", "sound badhao", "volume increase", "aawaz badhao", "volume thoda badhao"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": "adjust_volume", "value": 15},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["volume kam karo", "volume down", "sound kam karo", "volume decrease", "aawaz kam karo", "volume thoda kam karo"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": "adjust_volume", "value": -15},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["unmute system", "unmute audio", "unmute sound", "unmute karo", "unmute kar do", "unmute"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": "unmute", "value": None},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["mute system", "mute audio", "system mute", "mute sound", "volume mute", "mute kar do", "mute karo"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": "mute", "value": None},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        # 2. Brightness commands
        bright_set_match = re.search(
            r"\b(?:brightness|screen\s+light|screen\s+brightness)\s+(?:ko\s+)?(\d{1,3})\s*(?:%|percent)?(?:\s*(?:pe|par|karo|set|kar do))?\b",
            clean,
        ) or re.search(
            r"\b(?:set\s+)?(?:brightness|screen\s+light)\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?\b",
            clean,
        )
        if bright_set_match:
            val = int(bright_set_match.group(1))
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "brightness", "action": "set_brightness", "value": val},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["brightness badhao", "brightness up", "screen light badhao", "increase brightness", "brightness increase"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "brightness", "action": "adjust_brightness", "value": 15},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        if any(p in clean for p in ["brightness kam karo", "brightness down", "screen light kam karo", "decrease brightness", "brightness decrease"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "brightness", "action": "adjust_brightness", "value": -15},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        # 3. Security & Power Lock commands
        if any(p in clean for p in ["lock pc", "pc lock karo", "lock my pc", "lock computer", "computer lock karo", "lock workstation", "system lock karo"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "power", "action": "lock_workstation", "value": None},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        # Rule priority for hardware media transport control commands
        media_pause_patterns = {
            "stop", "pause", "pause the song", "pause music", "stop music", "stop the song",
            "gana roko", "gana band karo", "music band karo", "ruk jao", "chup ho jao",
            "pause karo", "pause kar do"
        }
        media_resume_patterns = {
            "play", "resume", "continue", "resume music", "resume song", "resume the song",
            "gana chalao", "wapas bajao", "aage play karo", "fir se chalao"
        }
        media_next_patterns = {"next song", "agla gana", "skip song", "next track", "skip"}
        media_prev_patterns = {"previous song", "pichla gana", "prev song", "previous track"}

        if clean in media_pause_patterns:
            return {
                "query": text,
                "intent": "PLAY_MUSIC",
                "raw_intent": "PLAY_MUSIC",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "pause", "track_or_query": ""},
                "model_name": "RulePriority-MediaControl",
                "top_probabilities": {"PLAY_MUSIC": 0.98},
            }
        if clean in media_resume_patterns:
            return {
                "query": text,
                "intent": "PLAY_MUSIC",
                "raw_intent": "PLAY_MUSIC",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "resume", "track_or_query": ""},
                "model_name": "RulePriority-MediaControl",
                "top_probabilities": {"PLAY_MUSIC": 0.98},
            }
        if clean in media_next_patterns:
            return {
                "query": text,
                "intent": "PLAY_MUSIC",
                "raw_intent": "PLAY_MUSIC",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "next", "track_or_query": ""},
                "model_name": "RulePriority-MediaControl",
                "top_probabilities": {"PLAY_MUSIC": 0.98},
            }
        if clean in media_prev_patterns:
            return {
                "query": text,
                "intent": "PLAY_MUSIC",
                "raw_intent": "PLAY_MUSIC",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "previous", "track_or_query": ""},
                "model_name": "RulePriority-MediaControl",
                "top_probabilities": {"PLAY_MUSIC": 0.98},
            }

        vec = self.vectorizer.transform([clean])
        probs = self.model.predict_proba(vec)[0]

        max_idx = int(np.argmax(probs))
        confidence = float(probs[max_idx])
        predicted_class = self.label_encoder.classes_[max_idx]

        # All class probabilities sorted
        prob_dict = {
            self.label_encoder.classes_[i]: round(float(probs[i]), 4)
            for i in np.argsort(-probs)
        }

        # Confidence threshold check
        is_confident = confidence >= self.confidence_threshold
        intent = predicted_class if is_confident else "UNKNOWN_INTENT"

        entities = self.extract_entities(text, predicted_class)

        response = {
            "query": text,
            "intent": intent,
            "raw_intent": predicted_class,
            "confidence": round(confidence, 4),
            "confidence_percent": round(confidence * 100, 2),
            "threshold": self.confidence_threshold,
            "needs_clarification": not is_confident,
            "entities": entities,
            "model_name": self.model_name,
            "top_probabilities": prob_dict,
        }

        if not is_confident:
            response["clarification_message"] = (
                f"Confidence ({round(confidence * 100, 1)}%) was below threshold. "
                f"Did you mean to perform a '{predicted_class}' action? Please clarify."
            )

        return response


# Global singleton instance
intent_service = IntentClassifierService()
