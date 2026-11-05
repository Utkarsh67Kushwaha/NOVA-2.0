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
from backend.app.tools import default_registry
from backend.app.system.hardware_controller import hardware_controller

router = APIRouter()
START_TIME = time.time()


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
    entities = prediction.get("entities", {})
    live_response = None
    executed_tool = None
    tool_result = None

    if intent == "SYSTEM_CONTROL":
        action = entities.get("action", "status")
        value = entities.get("value")
        t_res = default_registry.execute("system_control", {"action": action, "value": value})
        executed_tool = "system_control"
        tool_result = t_res.model_dump()
        live_response = t_res.output

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
        executed_tool = "system_status"
        tool_result = t_res.model_dump()
        live_response = t_res.output

    elif intent == "OPEN_APP":
        app_name = entities.get("app_name")
        if app_name in ("sc", "screenshot", "snippingtool"):
            t_res = default_registry.execute("take_screenshot", {})
            executed_tool = "take_screenshot"
            tool_result = t_res.model_dump()
            live_response = t_res.output
        elif app_name:
            t_res = default_registry.execute("launch_app", {"app_name": app_name})
            executed_tool = "launch_app"
            tool_result = t_res.model_dump()
            live_response = t_res.output
        else:
            live_response = "App launch intent detected, but no specific app name recognized."

    elif intent == "BROWSER_ACTION":
        search_query = entities.get("search_query", request.text)
        t_res = default_registry.execute("web_search", {"query": search_query})
        executed_tool = "web_search"
        tool_result = t_res.model_dump()
        live_response = t_res.output

    elif intent == "FILE_SEARCH":
        target = entities.get("file_name", entities.get("file_query", ""))
        if target:
            t_res = default_registry.execute("search_files", {"query": target})
            executed_tool = "search_files"
            tool_result = t_res.model_dump()
            live_response = t_res.output
        else:
            live_response = "File search intent detected. Please specify a file name or extension."

    elif intent == "PLAY_MUSIC":
        track = entities.get("track_or_query", "music")
        t_res = default_registry.execute("play_music", {"track": track})
        executed_tool = "play_music"
        tool_result = t_res.model_dump()
        live_response = f"Opening '{track}' in Google Chrome."

    elif intent == "REMINDER":
        time_exp = entities.get("time_expression", "")
        live_response = f"Reminder logged: '{request.text}' (Time: {time_exp or 'unspecified'})."

    prediction["live_response"] = live_response
    prediction["executed_tool"] = executed_tool
    prediction["tool_result"] = tool_result

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
