import asyncio
import json
import os
from pathlib import Path
import platform
import time
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel, Field
import psutil

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.services.intent_service import intent_service
from backend.app.services.gemini_service import gemini_service
from backend.app.services.dispatcher import dispatch_intent
from backend.app.tools import default_registry
from backend.app.system.hardware_controller import hardware_controller
from backend.app.reminders.scheduler import reminder_scheduler
from backend.app.reminders.reminder_model import ReminderCreate

router = APIRouter()
START_TIME = time.time()


class GeminiSettingsRequest(BaseModel):
    api_key: str = Field(..., description="Google Gemini API Key", min_length=1)


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

    # Direct match for Screenshot / SC keywords
    is_sc_query = any(k in clean_text for k in ["sc", "screenshot", "screen shot", "screen clip", "snipping", "snip"])
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
    if intent in ("AI_CHAT", "UNKNOWN_INTENT"):
        loop = asyncio.get_event_loop()
        live_response = await loop.run_in_executor(None, gemini_service.ask, request.text)
        prediction["live_response"] = live_response
        prediction["executed_tool"] = "gemini_service"
        prediction["tool_result"] = {"status": "success", "answer": live_response}
        prediction["needs_clarification"] = False
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
        "model": "gemini-2.5-flash",
        "has_key": bool(gemini_service.api_key),
    }


@router.post("/api/settings/gemini")
async def update_gemini_settings(payload: GeminiSettingsRequest) -> Dict[str, Any]:
    """Updates and saves Gemini API Key."""
    success = gemini_service.set_api_key(payload.api_key)
    return {
        "status": "success" if success else "error",
        "is_configured": gemini_service.is_configured(),
        "message": "Gemini API Key saved successfully!" if success else "Failed to save API key.",
    }

