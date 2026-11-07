import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
import joblib
from backend.app.services.context_manager import context_manager
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
    "vlc",
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
        for pattern, replacement in voice_phonetics:
            text = re.sub(pattern, replacement, text)

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
            app_canonical_map = {
                "chrome": "chrome", "browser": "chrome", "google chrome": "chrome",
                "spotify": "spotify", "music app": "spotify",
                "notepad": "notepad", "text editor": "notepad",
                "calculator": "calculator", "calc": "calculator",
                "vscode": "vscode", "visual studio code": "vscode", "code": "vscode",
                "terminal": "cmd", "cmd": "cmd", "command prompt": "cmd",
                "powershell": "powershell",
                "explorer": "explorer", "file explorer": "explorer",
                "settings": "settings",
                "camera": "camera",
                "paint": "paint",
                "telegram": "telegram",
                "discord": "discord",
                "whatsapp": "whatsapp",
                "brave": "brave",
                "edge": "edge", "microsoft edge": "edge", "msedge": "edge",
                "task manager": "task manager", "taskmanager": "task manager", "taskmgr": "task manager",
                "word": "word", "microsoft word": "word",
                "excel": "excel", "microsoft excel": "excel",
                "vlc": "vlc",
                "snippingtool": "screenshot", "screenshot": "screenshot", "sc": "screenshot",
            }
            for alias, canonical in app_canonical_map.items():
                if alias in clean:
                    entities["app_name"] = canonical
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
                r"(?:search|google par|google pe|youtube par|khojo|google karo|search karo)\s+(.+?)(?:\s+on\s+google|\s+in\s+browser|\s+on\s+youtube|$)",
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

        # 0. Alexa-grade Direct Single-Word App Invocations
        direct_apps = {
            "calc": "calculator",
            "calculator": "calculator",
            "notepad": "notepad",
            "chrome": "chrome",
            "browser": "chrome",
            "spotify": "spotify",
            "vscode": "vscode",
            "code": "vscode",
            "terminal": "cmd",
            "cmd": "cmd",
            "powershell": "powershell",
            "camera": "camera",
            "paint": "paint",
            "settings": "settings",
            "explorer": "explorer",
            "taskmanager": "task manager",
            "task manager": "task manager",
            "taskmgr": "task manager",
            "telegram": "telegram",
            "discord": "discord",
            "whatsapp": "whatsapp",
            "brave": "brave",
            "edge": "edge",
            "word": "word",
            "excel": "excel",
            "vlc": "vlc",
        }
        if clean in direct_apps or stripped in direct_apps:
            app_id = direct_apps.get(clean, direct_apps.get(stripped))
            return {
                "query": text,
                "intent": "OPEN_APP",
                "raw_intent": "OPEN_APP",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"app_name": app_id},
                "model_name": "RulePriority-DirectApp",
                "top_probabilities": {"OPEN_APP": 0.98},
            }

        # 0.1 Alexa-grade Direct Mute / Unmute
        if clean in ("mute", "unmute") or stripped in ("mute", "unmute") or re.search(r"\b(?:mute|unmute)\b", clean):
            action = "unmute" if "unmute" in clean else "mute"
            return {
                "query": text,
                "intent": "SYSTEM_CONTROL",
                "raw_intent": "SYSTEM_CONTROL",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"control_type": "volume", "action": action, "value": None},
                "model_name": "RulePriority-Mute",
                "top_probabilities": {"SYSTEM_CONTROL": 0.98},
            }

        # 0.2 Alexa-grade Direct Battery, Time, Date, Weather
        if clean == "battery" or stripped == "battery" or any(p in clean for p in ["battery kitni", "battery status", "charge kitna", "battery bachi"]):
            return {
                "query": text,
                "intent": "SYSTEM_INFO",
                "raw_intent": "SYSTEM_INFO",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"metric_targets": ["battery"]},
                "model_name": "RulePriority-Battery",
                "top_probabilities": {"SYSTEM_INFO": 0.98},
            }

        is_search_query = any(w in clean for w in ["search", "google", "khojo", "dhoondo", "find"])

        # 0.21 Live Real-Time Weather Intelligence
        if not is_search_query and any(w in clean for w in ["weather", "mausam", "temperature", "taapman"]):
            city_match = (
                re.search(r'\b(?:weather|mausam|temperature|taapman)\s+(?:in|of|me|ka|ki)\s+([a-zA-Z]+)\b', clean)
                or re.search(r'\b([a-zA-Z]+)\s+(?:ka|ki|me|in)\s+(?:weather|mausam|temperature|taapman)\b', clean)
                or re.search(r'\b(?:weather|mausam|temperature|taapman)\s+([a-zA-Z]+)\b', clean)
            )
            city = ""
            if city_match:
                candidate = city_match.group(1).lower().strip()
                if candidate not in ("kaisa", "kya", "aaj", "today", "hai", "batao", "bata", "check", "live", "kitna"):
                    city = candidate

            return {
                "query": text,
                "intent": "WEATHER",
                "raw_intent": "WEATHER",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"city": city},
                "model_name": "RulePriority-LiveWeather",
                "top_probabilities": {"WEATHER": 0.98},
            }

        # 0.23 Document & Code Content Analysis
        doc_ext_match = re.search(r'\b([\w\-_\./\\]+\.(?:md|py|json|txt|js|ts|tsx|html|css|yaml|yml|csv))\b', clean, re.IGNORECASE)
        has_analysis_word = any(w in clean for w in ["analyze", "explain", "review", "summary", "summarize", "padho", "samjhao"]) or (doc_ext_match and "check" in clean)
        is_anaphoric_file_doc = any(p in clean for p in ["isko", "ise", "use", "is file", "this file"]) and any(w in clean for w in ["analyze", "explain", "review", "summary", "summarize", "samjhao"])
        if (doc_ext_match and has_analysis_word) or is_anaphoric_file_doc:
            file_target = doc_ext_match.group(1).strip() if doc_ext_match else ""
            return {
                "query": text,
                "intent": "DOCUMENT_ANALYSIS",
                "raw_intent": "DOCUMENT_ANALYSIS",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"file_path": file_target, "prompt": text},
                "model_name": "RulePriority-DocAnalysis",
                "top_probabilities": {"DOCUMENT_ANALYSIS": 0.98},
            }

        # 0.22 WhatsApp Messaging Automation
        if "whatsapp" in clean and any(w in clean for w in ["message", "msg", "bhejo", "bhej", "send", "text"]):
            phone_match = re.search(r'\b(?:to|par|pe|number)?\s*(\+?\d{10,12})\b', clean)
            phone = phone_match.group(1) if phone_match else ""
            msg_match = re.search(r'(?::|message|msg|text|likho)\s+(.+)$', text, re.IGNORECASE)
            msg = msg_match.group(1).strip() if msg_match else "Hello from NOVA!"

            return {
                "query": text,
                "intent": "WHATSAPP_MESSAGE",
                "raw_intent": "WHATSAPP_MESSAGE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"phone": phone, "message": msg},
                "model_name": "RulePriority-WhatsAppMessage",
                "top_probabilities": {"WHATSAPP_MESSAGE": 0.98},
            }

        if not is_search_query and any(w in clean for w in ["time", "samay", "kitne baje", "kya time", "date", "tareekh", "today"]):
            return {
                "query": text,
                "intent": "AI_CHAT",
                "raw_intent": "AI_CHAT",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"query": text},
                "model_name": "RulePriority-TimeDateWeather",
                "top_probabilities": {"AI_CHAT": 0.98},
            }

        # 0.25 Voice Math & Instant Calculator Rules
        is_calc = (
            bool(re.search(r'\b(?:calculate|hisab\s+karo|compute|solve)\b', clean))
            or bool(re.search(r'\d+(?:\.\d+)?\s*(?:%|percent|pratishat)\s*(?:of|ka|pe|par|on|gst\s+on)?\s*\d+', clean))
            or bool(re.search(r'\d+(?:\.\d+)?\s*(?:ka|of)\s*\d+(?:\.\d+)?\s*(?:%|percent|pratishat)', clean))
            or (bool(re.search(r'\b\d+\s*(?:[\+\-\*\/]|\binto\b|\btimes\b|\bguna\b|\bdivided\s+by\b|\bbhag\b|\bplus\b|\bminus\b)\s*\d+', clean)) and any(w in clean for w in ["calculate", "kitna", "what is", "solve", "batao", "result", "answer", "equals"]))
        )
        if is_calc:
            return {
                "query": text,
                "intent": "CALCULATE",
                "raw_intent": "CALCULATE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"expression": text},
                "model_name": "RulePriority-Calculator",
                "top_probabilities": {"CALCULATE": 0.98},
            }

        # 0.26 Screen Vision & Desktop Multimodal Understanding
        is_screen_vision = (
            any(p in clean for p in [
                "what's on my screen", "whats on my screen", "what is on my screen",
                "what is on screen", "what's on screen", "whats on screen",
                "screen par kya hai", "screen pe kya hai", "screen par kya chal raha hai", "screen pe kya chal raha hai",
                "look at my screen", "look at the screen", "look at screen",
                "screen dekho", "screen dekh kar batao", "screen dekh ke batao", "screen dekhna",
                "describe screen", "describe my screen", "summarize screen", "summarize my screen",
                "explain screen", "screen explain karo", "screen explain",
                "explain this window", "explain active window", "active window explain",
                "read my screen", "read screen", "display par kya hai", "display pe kya hai",
                "desktop par kya hai", "desktop pe kya hai", "what am i looking at",
                "ye window explain karo", "window me kya hai", "screen reading",
            ])
            or (("screen" in clean or "display" in clean or "desktop" in clean) and any(w in clean for w in ["kya chal raha", "kya chal rha", "kya dikh raha", "kya dikh rha", "explain karo", "samjhao", "summarize karo", "dekh kar batao", "dekh ke batao"]))
        )
        if is_screen_vision:
            return {
                "query": text,
                "intent": "SCREEN_VISION",
                "raw_intent": "SCREEN_VISION",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"prompt": text},
                "model_name": "RulePriority-ScreenVision",
                "top_probabilities": {"SCREEN_VISION": 0.98},
            }

        # 0.27 Windows System Maintenance & Quick Folders
        recycle_empty_pat = r'\b(?:empty\s+recycle\s*bin|recycle\s*bin\s+saaf|recycle\s*bin\s+khali|empty\s+trash|trash\s+saaf|kachra\s+saaf|clean\s+recycle\s*bin)\b'
        folder_open_pat = r'\b(?:open|kholo|launch)\s+(?:my\s+)?(downloads?|documents?|desktop|pictures?|photos?|videos?|project|workspace|recycle\s*bin)(?:\s+folder)?\b|\b(downloads?|documents?|desktop|pictures?|photos?|videos?|project|workspace|recycle\s*bin)(?:\s+folder)?\s+(?:kholo|open|chalao)\b'
        proc_pat = r'\b(?:top\s+processes|top\s+ram|ram\s+kaun|cpu\s+kaun|highest\s+memory|resource\s+usage|heavy\s+apps)\b'
        net_pat = r'\b(?:internet\s+check|check\s+internet|network\s+status|ping\s+check|internet\s+chal\s+raha)\b'
        disk_pat = r'\b(?:all\s+drives\s+status|drives\s+breakdown|drives\s+check|hard\s+drive\s+space)\b'

        if re.search(recycle_empty_pat, clean):
            return {
                "query": text,
                "intent": "SYSTEM_MAINTENANCE",
                "raw_intent": "SYSTEM_MAINTENANCE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "empty_recycle_bin", "target": "recycle bin"},
                "model_name": "RulePriority-SystemMaintenance",
                "top_probabilities": {"SYSTEM_MAINTENANCE": 0.98},
            }

        folder_m = re.search(folder_open_pat, clean)
        if folder_m:
            raw_folder = (folder_m.group(1) or folder_m.group(2)).lower().strip()
            folder_canonical = {
                "download": "downloads",
                "downloads": "downloads",
                "document": "documents",
                "documents": "documents",
                "desktop": "desktop",
                "picture": "pictures",
                "pictures": "pictures",
                "photo": "pictures",
                "photos": "pictures",
                "video": "videos",
                "videos": "videos",
                "project": "project",
                "workspace": "project",
                "recycle bin": "recycle bin",
                "recyclebin": "recycle bin",
            }.get(raw_folder, raw_folder)
            return {
                "query": text,
                "intent": "SYSTEM_MAINTENANCE",
                "raw_intent": "SYSTEM_MAINTENANCE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "open_folder", "target": folder_canonical},
                "model_name": "RulePriority-SystemMaintenance",
                "top_probabilities": {"SYSTEM_MAINTENANCE": 0.98},
            }

        if re.search(proc_pat, clean):
            return {
                "query": text,
                "intent": "SYSTEM_MAINTENANCE",
                "raw_intent": "SYSTEM_MAINTENANCE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "process_diagnostics", "target": "processes"},
                "model_name": "RulePriority-SystemMaintenance",
                "top_probabilities": {"SYSTEM_MAINTENANCE": 0.98},
            }

        if re.search(net_pat, clean):
            return {
                "query": text,
                "intent": "SYSTEM_MAINTENANCE",
                "raw_intent": "SYSTEM_MAINTENANCE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "network_status", "target": "network"},
                "model_name": "RulePriority-SystemMaintenance",
                "top_probabilities": {"SYSTEM_MAINTENANCE": 0.98},
            }

        if re.search(disk_pat, clean):
            return {
                "query": text,
                "intent": "SYSTEM_MAINTENANCE",
                "raw_intent": "SYSTEM_MAINTENANCE",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": "disk_breakdown", "target": "drives"},
                "model_name": "RulePriority-SystemMaintenance",
                "top_probabilities": {"SYSTEM_MAINTENANCE": 0.98},
            }

        # 0.28 Hands-Free Voice Keyboard & Desktop Shortcuts
        hotkey_patterns = [
            (r'\b(?:new\s+tab|open\s+new\s+tab|naya\s+tab)\b', 'new_tab'),
            (r'\b(?:close\s+tab|tab\s+band|tab\s+close)\b', 'close_tab'),
            (r'\b(?:reopen\s+tab|closed\s+tab|pichla\s+tab\s+kholo)\b', 'reopen_tab'),
            (r'\b(?:next\s+tab|tab\s+switch|agla\s+tab)\b', 'next_tab'),
            (r'\b(?:prev\s+tab|previous\s+tab)\b', 'prev_tab'),
            (r'\b(?:copy\s+karo|copy\s+this|copy\s+kar\s+lo)\b', 'copy'),
            (r'\b(?:paste\s+karo|paste\s+here|paste\s+kar\s+do)\b', 'paste'),
            (r'\b(?:cut\s+karo|cut\s+this)\b', 'cut'),
            (r'\b(?:select\s+all|sab\s+select|poora\s+select)\b', 'select_all'),
            (r'\b(?:save\s+karo|save\s+file|document\s+save)\b', 'save'),
            (r'\b(?:undo\s+karo|undo\s+this)\b', 'undo'),
            (r'\b(?:redo\s+karo)\b', 'redo'),
            (r'\b(?:refresh\s+karo|reload\s+karo|reload\s+page|page\s+refresh)\b', 'refresh'),
            (r'\b(?:full\s*screen|exit\s+fullscreen)\b', 'fullscreen'),
            (r'\b(?:zoom\s+in|zoom\s+badhao)\b', 'zoom_in'),
            (r'\b(?:zoom\s+out|zoom\s+kam\s+karo)\b', 'zoom_out'),
            (r'\b(?:zoom\s+reset|zoom\s+normal)\b', 'zoom_reset'),
            (r'\b(?:show\s+desktop|desktop\s+dikhao)\b', 'show_desktop'),
            (r'\b(?:switch\s+window|alt\s+tab|window\s+switch)\b', 'switch_window'),
        ]
        for pat, act in hotkey_patterns:
            if re.search(pat, clean):
                return {
                    "query": text,
                    "intent": "KEYBOARD_ACTION",
                    "raw_intent": "KEYBOARD_ACTION",
                    "confidence": 0.98,
                    "confidence_percent": 98.0,
                    "threshold": self.confidence_threshold,
                    "needs_clarification": False,
                    "entities": {"action": act},
                    "model_name": "RulePriority-KeyboardShortcut",
                    "top_probabilities": {"KEYBOARD_ACTION": 0.98},
                }

        # 0.29 Deep Multi-Engine Web Search (YouTube, GitHub, Wikipedia, Amazon, StackOverflow, etc.)
        deep_search_m = (
            re.search(r'\b(?:search\s+on|search|dhoondo|khojo)\s+(youtube|github|wikipedia|amazon|stackoverflow|reddit|twitter|google|bing|duckduckgo)\s+(?:for|pe|par|me)?\s*(.+)', clean)
            or re.search(r'\b(youtube|github|wikipedia|amazon|stackoverflow|reddit|twitter)\s+(?:par|pe|me)\s+(?:search\s+karo|khojo|dhoondo)\s*(.+)', clean)
        )
        if deep_search_m:
            engine = deep_search_m.group(1).lower().strip()
            search_query = deep_search_m.group(2).strip()
            search_query = re.sub(r'^(?:for|pe|par|me|about)\s+', '', search_query, flags=re.IGNORECASE)
            search_query = re.sub(r'\s+(?:karo|khojo|dhoondo)$', '', search_query, flags=re.IGNORECASE).strip()
            return {
                "query": text,
                "intent": "BROWSER_ACTION",
                "raw_intent": "BROWSER_ACTION",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"search_query": search_query, "engine": engine},
                "model_name": "RulePriority-DeepSearch",
                "top_probabilities": {"BROWSER_ACTION": 0.98},
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
        has_hw = any(w in clean for w in ["volume", "sound", "aawaz", "brightness", "light", "screenshot", "lock", "pc", "kholo", "open", "gana", "song", "reminder", "alarm", "battery", "ram", "cpu", "disk", "memory", "storage", "spec", "hardware", "wifi", "network", "process", "task", "recycle", "trash", "downloads", "documents", "internet", "ping", "tab", "copy", "paste", "cut", "select", "undo", "redo", "zoom", "fullscreen", "refresh"])
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
            bool(re.search(r"\b(?:screenshot|screen\s*shot|screen\s*clip|screencapture|screen\s*capture|sc)\b", clean))
            or any(p in clean or p in stripped for p in [
                "screenshot lo", "screenshot le lo", "sc le lo", "take screenshot", "take a screenshot",
                "ek screenshot", "screen capture karo", "kheencho", "screen capture", "capture screen",
                "screen shot lo", "screen shot le lo", "screenshot nikal lo", "screenshot lelo",
                "sc lo", "sc kheencho", "sc lelo", "screen ka photo", "screen photo", "screen ki pic",
                "screen capture", "desktop photo", "display photo", "photo lo", "pic lo", "snap lo"
            ])
            or (("screen" in clean or "desktop" in clean) and any(w in clean for w in ["photo", "pic", "tasveer", "snap", "snip", "kheencho"]))
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
            re.search(r"\b(?:open|launch|kholo|chalao|start|shuru|chala)\s+(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint|telegram|discord|whatsapp|brave|edge|task\s*manager|taskmgr|word|excel|vlc)\b", clean)
            or re.search(r"\b(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint|telegram|discord|whatsapp|brave|edge|task\s*manager|taskmgr|word|excel|vlc)\s+(?:kholo|open|launch|chalao|start|chala\s*do|chala\s*de|kholna\s*hai)\b", clean)
        )
        if app_open_match:
            raw_app = app_open_match.group(1).lower().strip()
            canonical_map = {
                "calc": "calculator",
                "browser": "chrome",
                "code": "vscode",
                "terminal": "cmd",
                "task manager": "task manager",
                "taskmanager": "task manager",
                "taskmgr": "task manager",
                "edge": "edge",
                "brave": "brave",
                "telegram": "telegram",
                "discord": "discord",
                "whatsapp": "whatsapp",
                "word": "word",
                "excel": "excel",
                "vlc": "vlc",
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

        # 0.51 App Termination & Close Rules (e.g., 'close notepad', 'notepad band karo', 'exit chrome', 'isko band karo')
        app_close_match = (
            re.search(r'\b(?:close|quit|exit|terminate|kill|band\s+karo|band\s+kar\s+do|hatao|band)\s+(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint|telegram|discord|whatsapp|brave|edge|task\s*manager|taskmgr|word|excel|vlc|isko|ise|isey|use|usey|usko|it|this)\b', clean)
            or re.search(r'\b(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|explorer|settings|camera|paint|telegram|discord|whatsapp|brave|edge|task\s*manager|taskmgr|word|excel|vlc|isko|ise|isey|use|usey|usko|it|this)\s+(?:close|quit|exit|terminate|kill|band\s+karo|band\s+kar\s+do|hatao|band)\b', clean)
        )
        if app_close_match:
            raw_app = app_close_match.group(1).lower().strip()
            if raw_app in ('isko', 'ise', 'isey', 'use', 'usey', 'usko', 'it', 'this'):
                raw_app = context_manager.last_app or raw_app
            canonical_map = {
                'calc': 'calculator',
                'browser': 'chrome',
                'code': 'vscode',
                'terminal': 'cmd',
                'task manager': 'task manager',
                'taskmanager': 'task manager',
                'taskmgr': 'task manager',
                'edge': 'edge',
                'brave': 'brave',
                'telegram': 'telegram',
                'discord': 'discord',
                'whatsapp': 'whatsapp',
                'word': 'word',
                'excel': 'excel',
                'vlc': 'vlc',
            }
            app_id = canonical_map.get(raw_app, raw_app)
            return {
                'query': text,
                'intent': 'CLOSE_APP',
                'raw_intent': 'CLOSE_APP',
                'confidence': 0.98,
                'confidence_percent': 98.0,
                'threshold': self.confidence_threshold,
                'needs_clarification': False,
                'entities': {'app_name': app_id},
                'model_name': 'RulePriority-AppClose',
                'top_probabilities': {'CLOSE_APP': 0.98},
            }

        # 0.52 Window Management Rules (e.g., 'minimize chrome', 'maximize notepad', 'focus vscode', 'isko minimize karo')
        win_match = (
            re.search(r'\b(minimize|maximize|focus|restore)\s+(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|window|telegram|discord|whatsapp|brave|edge|word|excel|isko|ise|isey|use|usey|usko|it|this)\b', clean)
            or re.search(r'\b(notepad|calculator|calc|chrome|browser|spotify|code|vscode|terminal|cmd|powershell|window|telegram|discord|whatsapp|brave|edge|word|excel|isko|ise|isey|use|usey|usko|it|this)\s+(?:ko\s+)?(minimize|maximize|focus|restore)\b', clean)
        )
        if win_match:
            g1, g2 = win_match.group(1).lower().strip(), win_match.group(2).lower().strip()
            actions = {'minimize', 'maximize', 'focus', 'restore'}
            action = g1 if g1 in actions else g2
            target = g2 if g1 in actions else g1
            if target in ('isko', 'ise', 'isey', 'use', 'usey', 'usko', 'it', 'this'):
                target = context_manager.last_app or target
            return {
                'query': text,
                'intent': 'WINDOW_ACTION',
                'raw_intent': 'WINDOW_ACTION',
                'confidence': 0.98,
                'confidence_percent': 98.0,
                'threshold': self.confidence_threshold,
                'needs_clarification': False,
                'entities': {'action': action, 'window_title': target},
                'model_name': 'RulePriority-WindowManage',
                'top_probabilities': {'WINDOW_ACTION': 0.98},
            }

        # 0.53 Clipboard AI Assistant Rules (e.g., 'read clipboard', 'clipboard me kya hai', 'summarize clipboard', 'clear clipboard')
        if 'clipboard' in clean or 'copied text' in clean:
            action = 'read'
            if any(w in clean for w in ['clear', 'saaf', 'empty', 'delete', 'hatao']):
                action = 'clear'
            elif any(w in clean for w in ['summarize', 'summary', 'explain', 'samjhao', 'meaning', 'batao', 'bata do']):
                action = 'summarize'
            return {
                'query': text,
                'intent': 'CLIPBOARD_ACTION',
                'raw_intent': 'CLIPBOARD_ACTION',
                'confidence': 0.98,
                'confidence_percent': 98.0,
                'threshold': self.confidence_threshold,
                'needs_clarification': False,
                'entities': {'action': action},
                'model_name': 'RulePriority-Clipboard',
                'top_probabilities': {'CLIPBOARD_ACTION': 0.98},
            }

        # 0.54 Smart Voice Notes & Scratchpad Rules (e.g., 'note likho: ...', 'take a note ...', 'show notes')
        has_note_keyword = bool(re.search(r'\b(?:notes?|scratchpad)\b', clean))
        if has_note_keyword:
            action = "list"
            content_text = ""

            # Check notepad export
            if any(w in clean for w in ["notepad", "file me", "editor me"]):
                action = "open_notepad"
            # Check clear/delete all
            elif any(w in clean for w in ["clear", "saaf", "empty", "delete all", "hatao"]):
                action = "clear"
            # Check read latest
            elif any(w in clean for w in ["latest", "last", "aakhri", "recent"]):
                action = "read_latest"
            # Check list / read notes
            elif any(w in clean for w in ["read", "show", "dikhao", "batao", "padho", "kya hai", "list", "view"]):
                action = "list"
            # Check create note
            else:
                create_match = re.search(
                    r'(?:take\s+a\s+note|add\s+a\s+note|write\s+a\s+note|make\s+a\s+note|note\s+down|note\s+likho|ek\s+note\s+likho|note\s+banao|note\s+karo|note\s+save\s+karo|note)\s*(?:ki|that|:)?\s*(.+)',
                    clean,
                    flags=re.IGNORECASE
                )
                if create_match and create_match.group(1).strip():
                    action = "create"
                    content_text = create_match.group(1).strip()
                elif any(w in clean for w in ["likho", "banao", "save", "add", "take", "write"]):
                    rem = re.sub(r'\b(?:take|add|write|make|note|notes|likho|banao|karo|save|down|ek|zara|please)\b', '', clean, flags=re.IGNORECASE).strip(' :-,')
                    if rem:
                        action = "create"
                        content_text = rem

            return {
                'query': text,
                'intent': 'NOTE_ACTION',
                'raw_intent': 'NOTE_ACTION',
                'confidence': 0.98,
                'confidence_percent': 98.0,
                'threshold': self.confidence_threshold,
                'needs_clarification': False,
                'entities': {'action': action, 'content': content_text},
                'model_name': 'RulePriority-Notes',
                'top_probabilities': {'NOTE_ACTION': 0.98},
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
            r"\b(?:volume|sound|aawaz)\s+(?:ko\s+)?(\d{1,3})\s*(?:%|percent)?(?:\s+(?:pe|par|karo|set|kar\s*do|pe\s*karo|par\s*karo))*\b",
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

        if any(p in clean for p in ["mute system", "mute audio", "system mute", "mute sound", "volume mute", "mute kar do", "mute karo", "aawaz band karo", "aawaz band kar do", "sound band karo", "sound band kar do", "aawaz band"]):
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
            r"\b(?:brightness|screen\s+light|screen\s+brightness|light)\s+(?:ko\s+)?(\d{1,3})\s*(?:%|percent)?(?:\s+(?:pe|par|karo|set|kar\s*do|pe\s*karo|par\s*karo))*\b",
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
            clean in ["lock", "lock it", "screen lock", "pc lock", "system lock"]
            or stripped in ["lock", "lock it", "screen lock", "pc lock", "system lock"]
            or (
                ("lock" in clean or "lock" in stripped)
                and any(w in clean or w in stripped for w in ["pc", "screen", "computer", "laptop", "system", "workstation", "windows", "desktop"])
            ) or any(p in clean or p in stripped for p in [
                "lock pc", "pc lock", "lock karo", "lock kar do", "screen lock", "lock screen", "laptop lock", "computer lock", "lock computer"
            ])
        )
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
        stop_pats = [
            "stop", "pause", "chup", "chup ho", "chup ho jao", "chup kar", "chup raho",
            "ruk", "ruk jao", "ruk ja", "shant", "band karo", "band kar do", "roko",
            "pause the song", "pause music", "stop music", "stop the song", "gana roko",
            "gaana roko", "gana band karo", "gaana band karo", "music band", "music roko"
        ]
        has_media_stop = (
            any(re.search(r"\b" + re.escape(p) + r"\b", clean) or re.search(r"\b" + re.escape(p) + r"\b", stripped) for p in stop_pats)
            or (
                any(w in clean or w in stripped for w in ["gana", "gaana", "music", "song"]) and
                any(w in clean or w in stripped for w in ["band", "roko", "rok", "pause", "stop"])
            )
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

        if clean in ["next", "skip"] or stripped in ["next", "skip"] or any(p in clean or p in stripped for p in ["next song", "agla gana", "skip song", "next track", "skip track", "track skip"]):
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

        if clean in ["previous", "prev"] or stripped in ["previous", "prev"] or any(p in clean or p in stripped for p in ["previous song", "pichla gana", "prev song", "previous track"]):
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

        has_music_indicator = any(re.search(r"\b" + re.escape(w) + r"\b", clean) for w in ["gana", "gaana", "gaane", "gane", "music", "song", "songs", "geet", "track", "spotify"])
        has_play_verb = any(re.search(r"\b" + re.escape(w) + r"\b", clean) for w in ["play", "chala", "chalao", "bajao", "baja", "sunao", "suna", "lagao", "laga", "resume"])
        is_generic_play = (
            clean in ["play", "resume", "continue", "wapas bajao", "fir se bajao", "dobara bajao", "fir se chalao"]
            or stripped in ["play", "resume", "continue", "wapas bajao", "fir se bajao", "dobara bajao", "fir se chalao"]
            or any(p in clean for p in ["wapas bajao", "fir se chalao", "dobara chalao", "fir se bajao"])
        )

        if (has_music_indicator or is_generic_play or (has_play_verb and not is_search_query)):
            t = clean
            filler_patterns = [
                r"\b(?:bhai|hey|ok|kripya|please|suno|nova|chal|beta|yaar|dost|wapas|fir\s+se|dobara|again)\b",
                r"\b(?:play\s+karo|play\s+kar\s+do|play|resume|continue)\b",
                r"\b(?:chala\s+de|chala\s+do|chalao|chala|chalaye)\b",
                r"\b(?:baja\s+de|baja\s+do|bajao|baja|bajaye)\b",
                r"\b(?:suna\s+de|suna\s+do|sunao|suna|sunaye)\b",
                r"\b(?:laga\s+de|laga\s+do|lagao|laga|lagaye)\b",
                r"\b(?:gaana|gaane|gana|gane|geet|music|song|songs|track)\b",
                r"\b(?:koi|ek|achha|accha|badhiya|mast|famous|hit)\b",
                r"\b(?:ka|ke|ki|ko|me|par|pe|on\s+spotify|on\s+youtube)\b",
            ]
            for pat in filler_patterns:
                t = re.sub(pat, " ", t, flags=re.IGNORECASE)
            track = re.sub(r"\s+", " ", t).strip(" ,.?!-:")
            action = "play" if track else "resume"
            return {
                "query": text,
                "intent": "PLAY_MUSIC",
                "raw_intent": "PLAY_MUSIC",
                "confidence": 0.98,
                "confidence_percent": 98.0,
                "threshold": self.confidence_threshold,
                "needs_clarification": False,
                "entities": {"action": action, "track_or_query": track},
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
