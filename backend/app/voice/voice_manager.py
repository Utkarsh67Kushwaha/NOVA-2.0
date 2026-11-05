from enum import Enum
import logging
import queue
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np

from backend.app.services.intent_service import intent_service
from backend.app.tools import default_registry
from backend.app.voice.audio_capture import audio_capture
from backend.app.voice.media_controller import media_controller
from backend.app.voice.stt import stt_service
from backend.app.voice.tts import tts_service
from backend.app.voice.vad import VoiceActivityDetector
from backend.app.voice.wake_word import wake_word_detector

logger = logging.getLogger("nova.voice.manager")


def play_wake_chime() -> None:
    """Non-blocking audio cue played when 'Hey NOVA' wake phrase is recognized."""
    def _chime():
        try:
            import winsound
            winsound.Beep(988, 55)   # B5 tone
            winsound.Beep(1318, 85)  # E6 tone
        except Exception:
            pass

    threading.Thread(target=_chime, daemon=True, name="WakeChimeWorker").start()


class VoiceState(str, Enum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    MUTED = "MUTED"


class VoiceAssistantManager:
    """Orchestrates audio capture, VAD, continuous hands-free wake word detection, STT, intent classification, action execution, and TTS."""

    def __init__(self):
        self.state: VoiceState = VoiceState.IDLE
        # Human-optimized VAD: 0.0014 energy threshold, 1.1s natural pause, 0.22s min speech
        self.vad = VoiceActivityDetector(
            energy_threshold=0.0014,
            silence_timeout_sec=1.1,
            min_speech_duration_sec=0.22,
        )
        self.last_transcript: str = ""
        self.last_response: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

        # Hands-free continuous wake-word mode state
        self.is_hands_free: bool = False
        self.followup_active_until: float = 0.0
        self._continuous_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.last_event: Optional[Dict[str, Any]] = None
        self.event_history: List[Dict[str, Any]] = []

    def get_status(self) -> Dict[str, Any]:
        """Returns current state and subsystem status."""
        return {
            "state": self.state.value,
            "is_muted": audio_capture.is_muted,
            "is_audio_running": audio_capture.is_running,
            "last_transcript": self.last_transcript,
            "volume_level": audio_capture.current_rms,
            "hands_free_active": self.is_hands_free,
            "last_event": self.last_event,
            "media_paused_for_voice": media_controller.is_paused_for_voice,
        }

    def interrupt(self) -> None:
        """Interrupts ongoing speech or processing."""
        tts_service.stop()
        self.vad.reset()
        self.followup_active_until = 0.0
        media_controller.clear_paused_state()
        self._flush_audio_queue()
        self.state = VoiceState.IDLE
        logger.info("Voice Assistant interrupted.")

    def toggle_mute(self) -> bool:
        """Toggles microphone mute."""
        muted = audio_capture.toggle_mute()
        self.state = VoiceState.MUTED if muted else VoiceState.IDLE
        if muted:
            tts_service.stop()
            self.followup_active_until = 0.0
            media_controller.clear_paused_state()
            self._flush_audio_queue()
        return muted

    def _flush_audio_queue(self) -> None:
        """Flushes stale audio buffers from queue to prevent delayed processing."""
        while not audio_capture.audio_queue.empty():
            try:
                audio_capture.audio_queue.get_nowait()
            except Exception:
                break

    def _execute_voice_action(self, prediction: Dict[str, Any], command: str) -> str:
        """Dispatches recognized intent to Safe Tools registry and returns spoken response."""
        intent = prediction.get("intent")
        entities = prediction.get("entities", {})

        try:
            if intent == "PLAY_MUSIC":
                action = entities.get("action", "play")
                if action in ("pause", "stop"):
                    t_res = default_registry.execute("media_control", {"action": "pause"})
                    prediction["executed_tool"] = "media_control"
                    prediction["tool_result"] = t_res.model_dump()
                    media_controller.clear_paused_state()
                    return "Media playback paused."
                elif action in ("resume", "continue"):
                    t_res = default_registry.execute("media_control", {"action": "resume"})
                    prediction["executed_tool"] = "media_control"
                    prediction["tool_result"] = t_res.model_dump()
                    media_controller.clear_paused_state()
                    return "Media playback resumed."
                elif action == "next":
                    t_res = default_registry.execute("media_control", {"action": "next"})
                    prediction["executed_tool"] = "media_control"
                    prediction["tool_result"] = t_res.model_dump()
                    media_controller.clear_paused_state()
                    return "Skipped to next track."
                elif action == "previous":
                    t_res = default_registry.execute("media_control", {"action": "previous"})
                    prediction["executed_tool"] = "media_control"
                    prediction["tool_result"] = t_res.model_dump()
                    media_controller.clear_paused_state()
                    return "Returned to previous track."
                else:
                    track = entities.get("track_or_query", "music")
                    t_res = default_registry.execute("play_music", {"track": track})
                    prediction["executed_tool"] = "play_music"
                    prediction["tool_result"] = t_res.model_dump()
                    media_controller.clear_paused_state()
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

    def start_hands_free(self) -> bool:
        """Starts the continuous hands-free wake word listening loop."""
        with self._lock:
            if self.is_hands_free and self._continuous_thread and self._continuous_thread.is_alive():
                return True

            self.is_hands_free = True
            self._stop_event.clear()
            self._flush_audio_queue()
            self.vad.reset()

            if not audio_capture.is_running:
                audio_capture.start()

            self._continuous_thread = threading.Thread(
                target=self._continuous_listen_loop,
                name="NOVA-HandsFree-Worker",
                daemon=True,
            )
            self._continuous_thread.start()
            logger.info("Hands-free 'Hey NOVA' wake-word engine STARTED.")
            return True

    def stop_hands_free(self) -> bool:
        """Stops the continuous hands-free listening loop."""
        with self._lock:
            self.is_hands_free = False
            self._stop_event.set()
            self.followup_active_until = 0.0
            media_controller.clear_paused_state()
            self._flush_audio_queue()
            logger.info("Hands-free 'Hey NOVA' wake-word engine STOPPED.")
            return False

    def toggle_hands_free(self) -> bool:
        """Toggles continuous hands-free wake word listening state."""
        if self.is_hands_free:
            return self.stop_hands_free()
        else:
            return self.start_hands_free()

    def _continuous_listen_loop(self) -> None:
        """Background thread for continuous VAD and wake-word monitoring."""
        logger.info("Continuous listen loop active and waiting for 'Hey NOVA'...")
        while not self._stop_event.is_set():
            if audio_capture.is_muted or not audio_capture.is_running:
                time.sleep(0.2)
                continue

            # Auto-resume paused media if followup window timed out without user command
            if self.followup_active_until > 0 and time.time() >= self.followup_active_until:
                self.followup_active_until = 0.0
                if media_controller.is_paused_for_voice:
                    logger.info("Followup window timed out without speech. Resuming paused media.")
                    media_controller.resume_if_paused_by_voice()

            try:
                # Retrieve next audio chunk
                chunk = audio_capture.audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            except Exception:
                continue

            # Don't listen to self while TTS is actively speaking
            if self.state == VoiceState.SPEAKING:
                time.sleep(0.05)
                continue

            # Feed to VAD
            speech_audio = self.vad.process_chunk(chunk)
            if speech_audio is None:
                continue

            # Speech utterance completed! Transcribe with Faster-Whisper
            try:
                self.state = VoiceState.PROCESSING
                transcript = stt_service.transcribe(speech_audio)
                if not transcript or not transcript.strip():
                    self.state = VoiceState.LISTENING if time.time() < self.followup_active_until else VoiceState.IDLE
                    continue

                # Filter out self-echo if mic overheard NOVA's prompt
                norm_t = transcript.lower().strip()
                if norm_t in (
                    "yes, i am listening", "yes i am listening", "i am listening",
                    "listening", "yes i'm listening", "i'm listening"
                ):
                    logger.debug("Ignoring self-echo utterance: '%s'", transcript)
                    self._flush_audio_queue()
                    self.vad.reset()
                    self.state = VoiceState.LISTENING if time.time() < self.followup_active_until else VoiceState.IDLE
                    continue

                self.last_transcript = transcript
                logger.info("Hands-free overheard: '%s'", transcript)

                # Check wake word
                is_wake, clean_command = wake_word_detector.detect_and_strip(transcript)
                is_in_followup = time.time() < self.followup_active_until

                if not is_wake and not is_in_followup:
                    # Ignore ambient room conversation not addressed to NOVA
                    self.state = VoiceState.IDLE
                    continue

                # When 'Hey NOVA' is spoken: immediately interrupt TTS, pause external media, and play chime
                if is_wake:
                    tts_service.stop()
                    # Trigger instant media pause via Windows SMTC & hardware keys
                    media_controller.pause_media()
                    self._flush_audio_queue()
                    self.vad.reset()
                    play_wake_chime()

                command_to_run = clean_command if is_wake else transcript
                command_to_run = command_to_run.strip()

                event_data: Dict[str, Any] = {
                    "timestamp": time.time(),
                    "transcript": transcript,
                    "clean_command": command_to_run,
                    "wake_word_detected": is_wake,
                    "status": "success",
                    "media_paused": media_controller.is_paused_for_voice,
                }

                if not command_to_run:
                    # User simply said "Hey NOVA" without command
                    response_text = "Yes, I am listening."
                    event_data["spoken_response"] = response_text
                    self.state = VoiceState.SPEAKING
                    # SPEAK SYNCHRONOUSLY so mic does NOT record self
                    tts_service.speak(response_text, blocking=True)

                    # After speaking finishes: flush queue, reset VAD, and open followup window
                    time.sleep(0.1)
                    self._flush_audio_queue()
                    self.vad.reset()
                    self.followup_active_until = time.time() + 8.5
                    self.state = VoiceState.LISTENING
                    logger.info("Followup window open for 8.5s. Ready for user's command.")

                else:
                    # User spoke full command
                    self.followup_active_until = 0.0
                    prediction = intent_service.predict(command_to_run)
                    event_data["prediction"] = prediction

                    if prediction.get("needs_clarification"):
                        response_text = prediction.get(
                            "clarification_message",
                            "Mujhe theek se samajh nahi aaya, kripya dobara bolein.",
                        )
                    else:
                        response_text = self._execute_voice_action(prediction, command_to_run)
                        prediction["live_response"] = response_text

                    event_data["spoken_response"] = response_text
                    self.state = VoiceState.SPEAKING
                    tts_service.speak(response_text, blocking=True)
                    self.state = VoiceState.IDLE

                    # Auto-resume media logic:
                    # If this was not a new song request or explicit stop/pause, resume whatever was playing
                    action = (
                        prediction.get("entities", {}).get("action")
                        if prediction.get("intent") == "PLAY_MUSIC"
                        else None
                    )
                    if prediction.get("intent") != "PLAY_MUSIC":
                        # Resumes media after response
                        time.sleep(0.3)
                        media_controller.resume_if_paused_by_voice()
                    elif action in ("pause", "stop", "play", "resume", "continue"):
                        media_controller.clear_paused_state()

                self.last_event = event_data
                self.event_history.append(event_data)
                if len(self.event_history) > 50:
                    self.event_history.pop(0)

                # Flush audio queue after response so self-echo doesn't loop
                self._flush_audio_queue()

            except Exception as e:
                logger.error("Error in continuous listen processing: %s", e)
            finally:
                if time.time() < self.followup_active_until:
                    self.state = VoiceState.LISTENING
                else:
                    self.state = VoiceState.IDLE

    def record_and_process_once(self, max_duration_sec: float = 6.0) -> Dict[str, Any]:
        """Records a single voice command from mic, transcribes, classifies, executes, speaks result, and returns data."""
        with self._lock:
            self.state = VoiceState.LISTENING
            logger.info("Listening for voice command (Max duration: %.1fs)...", max_duration_sec)

            if not audio_capture.is_running:
                audio_capture.start()

            # Pause media via SMTC so background sound does not interfere
            tts_service.stop()
            media_controller.pause_media()
            self._flush_audio_queue()

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
                    media_controller.resume_if_paused_by_voice()
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
                    media_controller.resume_if_paused_by_voice()
                    return {
                        "transcript": "",
                        "status": "no_speech",
                        "message": "Koi speech detect nahi hui. Kripya microphone ke paas bolen.",
                    }

                # Step 2: Wake Word Detection / Strip
                is_wake, clean_command = wake_word_detector.detect_and_strip(transcript)
                if is_wake:
                    play_wake_chime()

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
                tts_service.speak(response_text, blocking=True)
                self.state = VoiceState.IDLE

                # Auto-resume media if non-music command
                action = (
                    prediction.get("entities", {}).get("action")
                    if prediction.get("intent") == "PLAY_MUSIC"
                    else None
                )
                if prediction.get("intent") != "PLAY_MUSIC":
                    time.sleep(0.3)
                    media_controller.resume_if_paused_by_voice()
                elif action in ("pause", "stop", "play", "resume", "continue"):
                    media_controller.clear_paused_state()

                result_data = {
                    "transcript": transcript,
                    "clean_command": command_to_classify,
                    "wake_word_detected": is_wake,
                    "prediction": prediction,
                    "spoken_response": response_text,
                    "status": "success",
                    "media_paused": media_controller.is_paused_for_voice,
                }
                self.last_event = result_data
                self._flush_audio_queue()
                return result_data

            finally:
                self.state = VoiceState.IDLE


# Singleton instance
voice_manager = VoiceAssistantManager()
