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
        """Preprocesses input query."""
        text = text.lower().strip()
        text = re.sub(r"\s+", " ", text)
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
            # Extract song or artist name
            music_match = re.search(
                r"(?:play|bajao|chalao|lagao|sunao)\s+(?:some\s+)?(?:music\s+)?(?:on\s+spotify\s+)?(.+)",
                clean,
            )
            if music_match:
                entities["track_or_query"] = music_match.group(1).strip()
            else:
                entities["track_or_query"] = clean

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
