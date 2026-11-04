from enum import Enum
import logging
import queue
import threading
import time
from typing import Any, Dict, Optional

import numpy as np

from backend.app.services.intent_service import intent_service
from backend.app.tools import default_registry
from backend.app.voice.audio_capture import audio_capture
from backend.app.voice.stt import stt_service
from backend.app.voice.tts import tts_service
from backend.app.voice.vad import VoiceActivityDetector
from backend.app.voice.wake_word import wake_word_detector

logger = logging.getLogger("nova.voice.manager")


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    MUTED = "MUTED"


class VoiceAssistantManager:
    """Orchestrates audio capture, VAD, wake phrase detection, STT, intent classification, action execution, and TTS."""

    def __init__(self):
        self.state: VoiceState = VoiceState.IDLE
        self.vad = VoiceActivityDetector(energy_threshold=0.002, silence_timeout_sec=1.4)
        self.last_transcript: str = ""
        self.last_response: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    def get_status(self) -> Dict[str, Any]:
        """Returns current state and subsystem status."""
        return {
            "state": self.state.value,
            "is_muted": audio_capture.is_muted,
            "is_audio_running": audio_capture.is_running,
            "last_transcript": self.last_transcript,
            "volume_level": audio_capture.current_rms,
        }

    def interrupt(self) -> None:
        """Interrupts ongoing speech or processing."""
        tts_service.stop()
        self.vad.reset()
        self.state = VoiceState.IDLE
        logger.info("Voice Assistant interrupted.")

    def toggle_mute(self) -> bool:
        """Toggles microphone mute."""
        muted = audio_capture.toggle_mute()
        self.state = VoiceState.MUTED if muted else VoiceState.IDLE
        if muted:
            tts_service.stop()
        return muted

    def _execute_voice_action(self, prediction: Dict[str, Any], command: str) -> str:
        """Dispatches recognized intent to Safe Tools registry and returns spoken response."""
        intent = prediction.get("intent")
        entities = prediction.get("entities", {})

        try:
            if intent == "PLAY_MUSIC":
                track = entities.get("track_or_query", "music")
                t_res = default_registry.execute("play_music", {"track": track})
                prediction["executed_tool"] = "play_music"
                prediction["tool_result"] = t_res.model_dump()
                return f"Opening {track} in Google Chrome."

            elif intent == "OPEN_APP":
                app_name = entities.get("app_name")
                if app_name in ("sc", "screenshot", "snippingtool"):
                    t_res = default_registry.execute("take_screenshot", {})
                    prediction["executed_tool"] = "take_screenshot"
                    prediction["tool_result"] = t_res.model_dump()
                    return "Screenshot captured successfully."
                elif app_name:
                    t_res = default_registry.execute("launch_app", {"app_name": app_name})
                    prediction["executed_tool"] = "launch_app"
                    prediction["tool_result"] = t_res.model_dump()
                    return t_res.output
                return "Application name samajh nahi aaya."

            elif intent == "BROWSER_ACTION":
                search_query = entities.get("search_query", command)
                t_res = default_registry.execute("web_search", {"query": search_query})
                prediction["executed_tool"] = "web_search"
                prediction["tool_result"] = t_res.model_dump()
                return f"Searching for {search_query}."

            elif intent == "SYSTEM_INFO":
                targets = entities.get("metric_targets", [])
                filter_name = "all"
                if "battery" in targets:
                    filter_name = "battery"
                elif "ram" in targets or "memory" in targets:
                    filter_name = "memory"
                elif "cpu" in targets:
                    filter_name = "cpu"
                elif "disk" in targets or "storage" in targets:
                    filter_name = "disk"
                t_res = default_registry.execute("system_status", {"metric_filter": filter_name})
                prediction["executed_tool"] = "system_status"
                prediction["tool_result"] = t_res.model_dump()
                return t_res.output

            elif intent == "FILE_SEARCH":
                target = entities.get("file_name", entities.get("file_query", ""))
                if target:
                    t_res = default_registry.execute("search_files", {"query": target})
                    prediction["executed_tool"] = "search_files"
                    prediction["tool_result"] = t_res.model_dump()
                    return t_res.output
                return "File search ke liye naam specify karein."

            elif intent == "REMINDER":
                time_exp = entities.get("time_expression", "")
                return f"Reminder note kiya: {command} ({time_exp or 'samay specify nahi kiya'})."

            else:
                intent_name = prediction.get("intent")
                return f"Command samajh gaya: {intent_name}."

        except Exception as ex:
            logger.error("Error executing voice action for intent '%s': %s", intent, ex)
            return f"{intent} command process karte waqt issue aaya."

    def record_and_process_once(self, max_duration_sec: float = 6.0) -> Dict[str, Any]:
        """Records a single voice command from mic, transcribes, classifies, executes, speaks result, and returns data."""
        with self._lock:
            self.state = VoiceState.LISTENING
            logger.info("Listening for voice command (Max duration: %.1fs)...", max_duration_sec)

            if not audio_capture.is_running:
                audio_capture.start()

            # Flush any stale chunks in queue
            while not audio_capture.audio_queue.empty():
                try:
                    audio_capture.audio_queue.get_nowait()
                except Exception:
                    break

            collected_audio = []
            start_time = time.time()
            self.vad.reset()

            try:
                # Capture loop
                while time.time() - start_time < max_duration_sec:
                    try:
                        chunk = audio_capture.audio_queue.get(timeout=0.1)
                        speech_result = self.vad.process_chunk(chunk)
                        collected_audio.append(chunk)

                        # If VAD detected complete utterance followed by silence
                        if speech_result is not None:
                            logger.info("VAD detected end of speech command.")
                            break
                    except Exception:
                        continue

                self.state = VoiceState.PROCESSING

                if not collected_audio:
                    self.state = VoiceState.IDLE
                    return {
                        "error": "Microphone se audio capture nahi ho saka.",
                        "status": "failed",
                    }

                full_audio = np.concatenate(collected_audio)

                # Step 1: Speech-to-Text Transcription via Faster-Whisper
                transcript = stt_service.transcribe(full_audio)
                self.last_transcript = transcript

                if not transcript or not transcript.strip():
                    self.state = VoiceState.IDLE
                    return {
                        "transcript": "",
                        "status": "no_speech",
                        "message": "Koi speech detect nahi hui. Kripya microphone ke paas bolen.",
                    }

                # Step 2: Wake Word Detection / Strip
                is_wake, clean_command = wake_word_detector.detect_and_strip(transcript)
                command_to_classify = clean_command if clean_command else transcript

                # Step 3: Intent Classification
                prediction = intent_service.predict(command_to_classify)
                self.last_response = prediction

                # Step 4: Tool Execution & Text-to-Speech Response
                response_text = ""
                if prediction.get("needs_clarification"):
                    response_text = prediction.get(
                        "clarification_message",
                        "Mujhe theek se samajh nahi aaya, kripya dobara bolein.",
                    )
                else:
                    response_text = self._execute_voice_action(prediction, command_to_classify)
                    prediction["live_response"] = response_text

                self.state = VoiceState.SPEAKING
                tts_service.speak(response_text, blocking=False)
                self.state = VoiceState.IDLE

                return {
                    "transcript": transcript,
                    "clean_command": command_to_classify,
                    "wake_word_detected": is_wake,
                    "prediction": prediction,
                    "spoken_response": response_text,
                    "status": "success",
                }

            finally:
                self.state = VoiceState.IDLE


# Singleton instance
voice_manager = VoiceAssistantManager()
