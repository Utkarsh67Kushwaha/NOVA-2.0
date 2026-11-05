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




def strip_conversational_fillers(text: str) -> str:
    """Strips colloquial Hindi/Hinglish filler words while preserving core intent."""
    fillers = [
        r'\b(?:bhai|yaar|bro|dude|buddy)\b',
        r'\b(?:zara|thoda|thodi|thoda\s+sa|please|kripya)\b',
        r'\b(?:arre|arey|oye|sun|suno)\b',
        r'\b(?:ek\s+kaam\s+kar|dekh|dekho)\b',
        r'\b(?:jaldi\s+se|turant|fast)\b',
    ]
    cleaned = text
    for f in fillers:
        cleaned = re.sub(f, '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()

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
        """Preprocesses input query, transliterates Hindi/Devanagari, and corrects common phonetic STT errors."""
        text = text.lower().strip()
        text = re.sub(r"""[.!?,'"]+$""", "", text).strip()
        text = re.sub(r"\s+", " ", text)

        # Transliterate common Hindi/Devanagari voice terms to standard Latin Hinglish
        devanagari_map = {
            'स्क्रीनशॉट': 'screenshot', 'स्क्रीन शॉट': 'screenshot', 'स्क्रीन': 'screen', 'खींचो': 'kheencho',
            'वॉल्यूम': 'volume', 'आवाज़': 'aawaz', 'आवाज': 'aawaz', 'साउंड': 'sound', 'बढ़ाओ': 'badhao',
            'बढ़ा': 'badha', 'कम': 'kam', 'घटाओ': 'kam', 'म्यूट': 'mute', 'अनम्यूट': 'unmute',
            'ब्राइटनेस': 'brightness', 'लाइट': 'light', 'रोशनी': 'light',
            'लॉक': 'lock', 'पीसी': 'pc', 'कंप्यूटर': 'computer', 'सिस्टम': 'system', 'बंद': 'band',
            'नोटपैड': 'notepad', 'कैलकुलेटर': 'calculator', 'कैलक': 'calc', 'क्रोम': 'chrome',
            'ब्राउज़र': 'browser', 'स्पॉटिफ़ाई': 'spotify', 'स्पॉटीफाई': 'spotify', 'खोलो': 'kholo',
            'ओपन': 'open', 'चलाओ': 'chalao', 'शुरू': 'shuru',
            'गाना': 'gana', 'गाने': 'gana', 'गीत': 'gana', 'म्यूजिक': 'music', 'सॉन्ग': 'song',
            'बजाओ': 'bajao', 'रोको': 'roko', 'पॉज़': 'pause', 'पॉज': 'pause', 'रिज्यूम': 'resume',
            'अगला': 'next', 'पिछला': 'previous',
            'रिमाइंडर': 'reminder', 'अलार्म': 'alarm', 'याद': 'yaad', 'दिलाओ': 'dilao', 'लगाओ': 'lagao',
            'मिनट': 'minute', 'सेकंड': 'second', 'घंटे': 'ghante', 'घंटा': 'ghanta', 'बाद': 'baad',
            'पानी': 'water', 'पीने': 'peene', 'बैटरी': 'battery', 'रैम': 'ram', 'सीपीयू': 'cpu',
            'डिस्क': 'disk', 'प्रतिशत': '%', 'परसेंट': '%', 'करो': 'karo', 'कर': 'kar', 'दो': 'do', 'ले': 'le', 'लो': 'lo',
        }
        for dev_k, dev_v in devanagari_map.items():
            if dev_k in text:
                text = text.replace(dev_k, dev_v)

        # Phonetic normalizations for varied human voice phrasings
        voice_phonetics = [
            (r"\b(?:awaz|awaaz|avaz|avaj|aawaaz|sound)\b", "aawaz"),
            (r"\b(?:bada|badhao|badao|badha|tez)\b", "badha"),
            (r"\b(?:kam|ghata|ghatao|dheemi|dheema)\b", "kam"),
            (r"\b(?:screen\s*shot|clean\s*shot|screen\s*short)\b", "screenshot"),
            (r"\b(?:roshni|screen\s*light|display\s*light)\b", "light"),
            (r"\b(?:laptop|computer|system|workstation|machine)\b", "pc"),
        ]
        for p, r in voice_phonetics:
            text = re.sub(p, r, text)

        # Phonetic corrections for common Faster-Whisper mishearings on Indian/Hinglish speech
        whisper_phonetic_fixes = [
            # Screenshot variants
            (r"\b(?:screen\s*shot\s+lay\s+low|screen\s*short|clean\s*shot|screan\s*shot|take\s+clean\s*shot)\b", "take screenshot"),
            (r"\b(?:sc\s+lay\s+low|ask\s+lay\s+low|sc\s+lelo)\b", "sc le lo"),
            (r"\b(?:screen\s*shot\s+lo|screen\s*shot\s+le\s+lo)\b", "screenshot le lo"),
            # Audio & Volume variants
            (r"\b(?:always\s+bad\s*how|always\s+badhao|our\s+badhao|always\s+badha\s*do)\b", "aawaz badhao"),
            (r"\b(?:always\s+come\s*car|always\s+kam\s*karo|our\s+kam\s*karo)\b", "aawaz kam karo"),
            (r"\b(?:volume\s+badao|volume\s+badha\s+do|volume\s+inc)\b", "volume badhao"),
            (r"\b(?:volume\s+bada\s+do|sound\s+badao)\b", "volume badhao"),
            (r"\b(?:volume\s+kam\s+karo|volume\s+ghatao|volume\s+thoda\s+kam)\b", "volume kam karo"),
            # Power & Lock
            (r"\b(?:piece\s+lock|peace\s+lock|pc\s+log|lock\s+peace)\b", "pc lock karo"),
            # Music & Media
            (r"\b(?:gonna\s+rock\s+oh|ganna\s+roko|gana\s+rock\s*o)\b", "gana roko"),
            (r"\b(?:ganna\s+bajao|ganna\s+chalao)\b", "gana bajao"),
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
            from backend.app.reminders.time_parser import parse_time_expression
            due_secs, clean_title, expr = parse_time_expression(clean)
            entities["due_seconds"] = due_secs
            entities["title"] = clean_title or "Reminder"
            entities["time_expression"] = expr or "10 minutes" 

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
        stripped = strip_conversational_fillers(clean)
        if not clean:
            return {
                "intent": "UNKNOWN_INTENT",
                "confidence": 0.0,
                "needs_clarification": True,
                "clarification_message": "Command was empty. Please provide a command.",
            }

        # Check conversational queries & AI questions
        ai_chat_keywords = [
            "tum kaun ho", "who are you", "naam kya hai", "what is your name", "kya naam hai",
            "kaise ho", "how are you", "kya haal", "sab theek", "kaisa chal raha",
            "hello", "hi nova", "namaste", "pranaam",
            "kya kar sakte ho", "what can you do", "features", "madad", "help",
            "aaj kya date", "today date", "tareekh", "what is the date",
            "kitne baje", "kya time", "current time", "what time is it",
            "joke", "chutkula", "hasao", "funny",
            "who is", "what is", "kya hota hai", "kaun hai", "explain", "samjhao",
            "kaise kare", "tell me about", "batao", "write a", "essay", "kavita", "shayari"
        ]
        # Only route to AI_CHAT if it doesn't match desktop hardware terms (like volume/brightness/screenshot/app)
        has_hw = any(w in clean for w in ["volume", "sound", "aawaz", "brightness", "light", "screenshot", "lock", "pc", "kholo", "open", "gana", "song", "reminder", "alarm", "battery", "ram", "cpu", "disk", "memory", "storage", "spec", "hardware", "wifi", "network", "process", "task"])
        if not has_hw and any(w in clean for w in ai_chat_keywords):
            return {
                "query": text,
                "intent": "AI_CHAT",
                "raw_intent": "AI_CHAT",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"query": text},
                "model_name": "RulePriority-Conversational",
                "top_probabilities": {"AI_CHAT": 0.98},
            }

        # 0. Screenshot & Screen Clip commands (with photo/picture/tasveer synonyms)
        is_sc = (
            re.search(r"\b(?:screenshot|screen\s*shot|screen\s*clip|screencapture|screen\s*capture)\b", clean)
            or any(p in clean or p in stripped for p in [
                "screenshot lo", "screenshot le lo", "sc le lo", "take screenshot", "take a screenshot",
                "ek screenshot", "screen capture karo", "kheencho", "screen capture", "capture screen",
                "screen shot lo", "screen shot le lo", "screenshot nikal lo", "screenshot lelo",
                "sc lo", "sc kheencho", "sc lelo", "screen ka photo", "screen photo", "screen ki pic",
                "screen capture", "desktop photo", "display photo"
            ])
            or (("screen" in clean or "desktop" in clean) and any(w in clean for w in ["photo", "pic", "tasveer", "snap", "snip"]))
        )
        if is_sc:
            return {
                "query": text,
                "intent": "OPEN_APP",
                "raw_intent": "OPEN_APP",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"app_name": "screenshot"},
                "model_name": "RulePriority-Screenshot",
                "top_probabilities": {"OPEN_APP": 0.98},
            }

        # 0.5 App Launching Rules (e.g., "notepad kholo", "open calculator", "browser kholo")
        app_open_match = (
            re.search(r"\b(?:open|launch|kholo|chalao|start)\s+(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint)\b", clean)
            or re.search(r"\b(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint)\s+(?:kholo|open|launch|chalao|start)\b", clean)
        )
        if app_open_match:
            raw_app = app_open_match.group(1).lower().strip()
            canonical_map = {
                "calc": "calculator",
                "browser": "chrome",
                "code": "vscode",
                "terminal": "cmd",
            }
            app_id = canonical_map.get(raw_app, raw_app)
            return {
                "query": text,
                "intent": "OPEN_APP",
                "raw_intent": "OPEN_APP",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"app_name": app_id},
                "model_name": "RulePriority-AppLaunch",
                "top_probabilities": {"OPEN_APP": 0.98},
            }

        # 0.7 System Specs & Hardware Diagnostics Rules
        if any(p in clean for p in [
            "battery kitni hai", "battery percent", "battery percentage", "what is my battery", "battery status", "charge kitna hai", "battery check",
            "ram usage", "ram kitni", "memory usage", "cpu usage", "cpu load", "disk space",
            "storage kitni", "system specs", "system status", "hardware status"
        ]):
            metric = "all"
            if "battery" in clean or "charge" in clean:
                metric = "battery"
            elif "ram" in clean or "memory" in clean:
                metric = "memory"
            elif "cpu" in clean:
                metric = "cpu"
            elif "disk" in clean or "storage" in clean:
                metric = "disk"
            return {
                "query": text,
                "intent": "SYSTEM_INFO",
                "raw_intent": "SYSTEM_INFO",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"metric_targets": [metric]},
                "model_name": "RulePriority-SystemInfo",
                "top_probabilities": {"SYSTEM_INFO": 0.98},
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

        has_vol = any(w in clean or w in stripped for w in ["volume", "sound", "aawaz", "awaj", "awaaz"])
        is_vol_up = has_vol and any(w in clean or w in stripped for w in ["badha", "increase", "up", "tez", "high", "plus", "+"])
        is_vol_down = has_vol and any(w in clean or w in stripped for w in ["kam", "ghata", "decrease", "down", "dheemi", "low", "minus", "-"])

        if is_vol_up:
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

        if is_vol_down:
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

        has_bright = any(w in clean or w in stripped for w in ["brightness", "light", "screen light", "display light", "screen roshni", "roshni"])
        is_bright_up = has_bright and any(w in clean or w in stripped for w in ["badha", "increase", "up", "tez", "high", "plus", "+"])
        is_bright_down = has_bright and any(w in clean or w in stripped for w in ["kam", "ghata", "decrease", "down", "low", "minus", "-"])

        if is_bright_up:
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

        if is_bright_down:
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

        # 2.5 Reminder & Alarm commands
        if any(p in clean for p in [
            "remind me to", "remind me", "set a reminder", "set reminder", "reminder for",
            "reminder set karo", "reminder lagao", "ka reminder lagao", "mujhe yaad dilao",
            "yaad dilana", "alarm set karo", "alarm lagao"
        ]):
            from backend.app.reminders.time_parser import parse_time_expression
            due_secs, clean_title, expr = parse_time_expression(clean)
            return {
                "query": text,
                "intent": "REMINDER",
                "raw_intent": "REMINDER",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {
                    "title": clean_title or "Reminder",
                    "due_seconds": due_secs,
                    "time_expression": expr or "10 minutes",
                },
                "model_name": "RulePriority-Reminder",
                "top_probabilities": {"REMINDER": 0.98},
            }

        # 3. Security & Power Lock commands
        is_lock_cmd = (
            ("lock" in clean or "lock" in stripped)
            and any(w in clean or w in stripped for w in ["pc", "screen", "computer", "laptop", "system", "workstation", "windows", "desktop"])
        ) or any(p in clean or p in stripped for p in [
            "lock pc", "pc lock", "lock karo", "lock kar do", "screen lock", "lock screen", "laptop lock", "computer lock", "lock computer"
        ])
        if is_lock_cmd:
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

        if any(p in clean or p in stripped for p in ["sleep karo", "pc sleep", "suspend karo", "computer sleep", "sleep mode", "sleep"]):
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "power", "action": "sleep", "value": None},
                "model_name": "RulePriority-SystemControl",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        # Rule priority for hardware media transport control commands
        media_pause_patterns = [
            "stop", "pause", "pause the song", "pause music", "stop music", "stop the song",
            "gana roko", "gana band karo", "gaana band", "music band karo", "ruk jao", "chup ho jao",
            "pause karo", "pause kar do", "band kar do", "band karo"
        ]
        media_resume_patterns = [
            "play", "resume", "continue", "resume music", "resume song", "resume the song",
            "gana chalao", "wapas bajao", "aage play karo", "fir se chalao"
        ]
        media_next_patterns = ["next song", "agla gana", "skip song", "next track", "skip"]
        media_prev_patterns = ["previous song", "pichla gana", "prev song", "previous track"]

        has_media_stop = any(p in clean or p in stripped for p in media_pause_patterns) or (
            any(w in clean or w in stripped for w in ["gana", "gaana", "music", "song"]) and
            any(w in clean or w in stripped for w in ["band", "roko", "rok", "pause", "stop"])
        )
        if has_media_stop:
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
        if is_confident:
            intent = predicted_class
            entities = self.extract_entities(text, predicted_class)
            needs_clar = False
            clar_msg = None
        else:
            intent = "UNKNOWN_INTENT"
            entities = {}
            needs_clar = True
            clar_msg = "Command confidence was below threshold. Please clarify your command."

        response = {
            "query": text,
            "intent": intent,
            "raw_intent": predicted_class,
            "confidence": round(confidence, 4),
            "confidence_percent": round(confidence * 100, 2),
            "threshold": self.confidence_threshold,
            "needs_clarification": needs_clar,
            "entities": entities,
            "model_name": self.model_name,
            "top_probabilities": prob_dict,
        }
        if clar_msg:
            response["clarification_message"] = clar_msg

        return response


# Global singleton instance
intent_service = IntentClassifierService()
