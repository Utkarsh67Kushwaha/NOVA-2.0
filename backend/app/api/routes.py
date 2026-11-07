import asyncio
import json
import os
from pathlib import Path
import platform
import re
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
import psutil

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.services.intent_service import intent_service
from backend.app.services.gemini_service import gemini_service, AVAILABLE_MODELS
from backend.app.services.context_manager import context_manager
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry
from backend.app.system.hardware_controller import hardware_controller
from backend.app.reminders.scheduler import reminder_scheduler
from backend.app.reminders.reminder_model import ReminderCreate

router = APIRouter()
START_TIME = time.time()


class GeminiSettingsRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="Google Gemini API Key")
    model: Optional[str] = Field(None, description="Active Gemini model name")


class CommandRequest(BaseModel):
    """Text command request schema."""

    text: str = Field(..., description="User voice or text command", min_length=1)


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for quick uptime and status probe."""
    uptime_seconds = round(time.time() - START_TIME, 2)
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.NOVA_ENV,
        "uptime_seconds": uptime_seconds,
        "ml_ready": intent_service.is_ready(),
    }


@router.get("/api/status")
async def system_status() -> Dict[str, Any]:
    """Detailed system and resource status report."""
    uptime_seconds = round(time.time() - START_TIME, 2)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(os.path.abspath(os.sep))

    return {
        "status": "online",
        "uptime_seconds": uptime_seconds,
        "system": {
            "os": f"{platform.system()} {platform.release()}",
            "os_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
        },
        "hardware": hardware_controller.get_hardware_status(),
        "resources": {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_total_gb": round(memory.total / (1024**3), 2),
            "ram_used_gb": round(memory.used / (1024**3), 2),
            "ram_percent": memory.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_percent": disk.percent,
        },
        "app": {
            "name": settings.APP_NAME,
            "version": settings.VERSION,
            "environment": settings.NOVA_ENV,
            "port": settings.NOVA_PORT,
            "ml_model": intent_service.model_name if intent_service.is_ready() else "Not loaded",
        },
    }


@router.post("/api/command")
async def process_command(request: CommandRequest) -> Dict[str, Any]:
    """Processes a text command via the custom ML Intent Classifier and routes to safe tools."""
    logger.info("Received command for intent classification: '%s'", request.text)
    start_time = time.perf_counter()

    clean_text = request.text.lower().strip()

    # Direct match for Screenshot / SC keywords (using strict word boundaries to avoid hijacking 'screen' words)
    is_sc_query = (
        bool(re.search(r"\b(?:sc|screenshot|screen\s*shot|screen\s*clip|snipping|snip)\b", clean_text))
        and not any(w in clean_text for w in ["kya", "what", "look", "explain", "summarize", "describe", "light", "brightness", "lock", "pe", "par"])
    )
    if is_sc_query and len(clean_text.split()) <= 4:
        t_res = default_registry.execute("take_screenshot", {})
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "query": request.text,
            "intent": "OPEN_APP",
            "raw_intent": "OPEN_APP",
            "confidence": 0.95,
            "confidence_percent": 95.0,
            "threshold": 0.65,
            "needs_clarification": False,
            "entities": {"app_name": "screenshot"},
            "model_name": intent_service.model_name if intent_service.is_ready() else "Rule Engine",
            "top_probabilities": {"OPEN_APP": 0.95},
            "latency_ms": latency_ms,
            "live_response": t_res.output,
            "executed_tool": "take_screenshot",
            "tool_result": t_res.model_dump(),
        }

    prediction = intent_service.predict(request.text)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    prediction["latency_ms"] = latency_ms

    intent = prediction.get("intent")

    # AI_CHAT / UNKNOWN_INTENT: run Gemini in a thread-pool executor so the
    # async FastAPI event loop is never blocked (fixes 6-second async stall bug).
    if intent in ("AI_CHAT", "UNKNOWN_INTENT", "DOCUMENT_ANALYSIS", "CODE_ANALYSIS"):
        loop = asyncio.get_event_loop()
        live_response = await loop.run_in_executor(None, gemini_service.ask, request.text)
        prediction["live_response"] = live_response
        prediction["executed_tool"] = "gemini_service"
        prediction["tool_result"] = {"status": "success", "answer": live_response}
        prediction["needs_clarification"] = False
    elif intent == "SCREEN_VISION":
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, dispatch_intent, prediction, request.text)
    else:
        # All other intents: synchronous dispatch via the shared dispatcher module.
        # This eliminates the DRY violation between routes.py and voice_manager.py.
        dispatch_intent(prediction, request.text)

    executed_tool = prediction.get("executed_tool")
    logger.info(
        "Intent: %s (Confidence: %s%%, Latency: %sms, ExecutedTool: %s)",
        intent,
        prediction.get("confidence_percent"),
        latency_ms,
        executed_tool,
    )
    return prediction


@router.get("/api/ml/report")
async def get_ml_report() -> Dict[str, Any]:
    """Returns the ML benchmark comparison and evaluation report."""
    report_file = Path(__file__).resolve().parent.parent.parent / "models" / "evaluation_report.json"
    if not report_file.exists():
        return {"error": "Evaluation report not found. Train model first."}

    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/api/reminders")
async def get_reminders(active_only: bool = False) -> Dict[str, Any]:
    """Returns active and recent reminders."""
    if active_only:
        items = reminder_scheduler.get_active_reminders()
    else:
        items = reminder_scheduler.get_all_reminders()
    return {
        "status": "success",
        "reminders": [r.model_dump() for r in items],
        "count": len(items),
    }


@router.post("/api/reminders")
async def create_reminder_endpoint(payload: ReminderCreate) -> Dict[str, Any]:
    """Creates a new scheduled reminder."""
    item = reminder_scheduler.create_reminder(
        title=payload.title,
        due_seconds=payload.due_seconds,
        time_expression=payload.time_expression,
        due_at_iso=payload.due_at_iso,
        source="REST_API",
    )
    return {
        "status": "success",
        "reminder": item.model_dump(),
        "message": f"Reminder scheduled for '{item.title}'",
    }


@router.delete("/api/reminders/{reminder_id}")
async def delete_reminder_endpoint(reminder_id: str) -> Dict[str, Any]:
    """Cancels or deletes a reminder by ID."""
    deleted = reminder_scheduler.delete_reminder(reminder_id)
    return {
        "status": "success" if deleted else "not_found",
        "deleted": deleted,
        "reminder_id": reminder_id,
    }

@router.get("/api/settings/gemini")
async def get_gemini_settings() -> Dict[str, Any]:
    """Returns Gemini AI Brain status and model configuration."""
    return {
        "status": "success",
        "is_configured": gemini_service.is_configured(),
        "model": gemini_service.model,
        "available_models": AVAILABLE_MODELS,
        "has_key": bool(gemini_service.api_key),
    }


@router.post("/api/settings/gemini")
async def update_gemini_settings(payload: GeminiSettingsRequest) -> Dict[str, Any]:
    """Updates and saves Gemini API Key and Model."""
    msg_parts = []
    success = True
    if payload.api_key is not None and payload.api_key.strip():
        k_res = gemini_service.set_api_key(payload.api_key)
        if k_res:
            msg_parts.append("Gemini API Key saved.")
        else:
            success = False
            msg_parts.append("Failed to save API key.")
    if payload.model:
        m_res = gemini_service.set_model(payload.model)
        if m_res:
            msg_parts.append(f"Model updated to {gemini_service.model}.")
    return {
        "status": "success" if success else "error",
        "is_configured": gemini_service.is_configured(),
        "model": gemini_service.model,
        "message": " ".join(msg_parts) if msg_parts else "No changes submitted.",
    }


@router.get("/api/context")
async def get_session_context() -> Dict[str, Any]:
    """Returns the current multi-turn conversation context state."""
    return {
        "status": "success",
        "context": context_manager.get_state(),
    }


@router.post("/api/context/clear")
async def clear_session_context() -> Dict[str, Any]:
    """Resets multi-turn conversation context state."""
    context_manager.clear()
    return {
        "status": "success",
        "message": "Conversation context cleared successfully.",
    }



@router.get("/api/notes")
async def get_notes() -> Dict[str, Any]:
    """Returns all saved voice notes and scratchpad entries."""
    from backend.app.notes.note_manager import note_manager
    notes = note_manager.list_notes()
    return {
        "status": "success",
        "notes": [n.model_dump() for n in notes],
        "count": len(notes),
    }


@router.post("/api/notes")
async def create_note_endpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new note via API."""
    from backend.app.notes.note_manager import note_manager
    content = payload.get("content", "").strip()
    title = payload.get("title")
    if not content:
        return {"status": "error", "message": "Content cannot be empty."}
    note = note_manager.create_note(content=content, title=title)
    return {
        "status": "success",
        "note": note.model_dump(),
        "message": f"Note '{note.title}' created successfully.",
    }


@router.delete("/api/notes/{note_id}")
async def delete_note_endpoint(note_id: str) -> Dict[str, Any]:
    """Deletes a note by ID."""
    from backend.app.notes.note_manager import note_manager
    deleted = note_manager.delete_note(note_id)
    return {
        "status": "success" if deleted else "not_found",
        "deleted": deleted,
        "note_id": note_id,
    }


@router.delete("/api/notes")
async def clear_notes_endpoint() -> Dict[str, Any]:
    """Clears all saved notes."""
    from backend.app.notes.note_manager import note_manager
    count = note_manager.clear_all_notes()
    return {
        "status": "success",
        "cleared_count": count,
        "message": f"Cleared all {count} notes.",
    }



@router.post("/api/screen/analyze")
async def analyze_screen_endpoint(request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Captures desktop screen and performs multimodal visual analysis via Gemini / offline intelligence."""
    req = request or {}
    prompt = str(req.get("prompt", "What is on my screen?")).strip()
    loop = asyncio.get_event_loop()
    t_res = await loop.run_in_executor(None, default_registry.execute, "screen_vision", {"prompt": prompt})
    return {
        "status": "success" if t_res.success else "error",
        "output": t_res.output,
        "data": t_res.data,
    }



@router.post("/api/maintenance")
async def maintenance_endpoint(request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Performs system maintenance action (open_folder, empty_recycle_bin, process_diagnostics, network_status, disk_breakdown)."""
    req = request or {}
    action = str(req.get("action", "open_folder")).strip().lower()
    target = str(req.get("target", "downloads")).strip().lower()
    loop = asyncio.get_event_loop()
    t_res = await loop.run_in_executor(
        None, default_registry.execute, "system_maintenance", {"action": action, "target": target}
    )
    return {
        "status": "success" if t_res.success else "error",
        "output": t_res.output,
        "data": t_res.data,
    }



@router.post("/api/shortcut")
async def shortcut_endpoint(request: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes a hands-free keyboard shortcut action."""
    req = request or {}
    action = str(req.get("action", "refresh")).strip().lower()
    t_res = default_registry.execute("keyboard_shortcut", {"action": action})
    return {
        "status": "success" if t_res.success else "error",
        "output": t_res.output,
        "data": t_res.data,
    }
