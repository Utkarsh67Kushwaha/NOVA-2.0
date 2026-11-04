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
    """Processes a text command via the custom ML Intent Classifier."""
    logger.info("Received command for intent classification: '%s'", request.text)
    start_time = time.perf_counter()

    prediction = intent_service.predict(request.text)
    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    prediction["latency_ms"] = latency_ms

    intent = prediction.get("intent")
    entities = prediction.get("entities", {})
    live_response = None

    if intent == "SYSTEM_INFO":
        targets = entities.get("metric_targets", [])
        if "battery" in targets:
            bat = psutil.sensors_battery()
            if bat:
                plugged_str = "Plugged in (Charging)" if bat.power_plugged else "Running on Battery"
                live_response = f"Aapke laptop ki battery {bat.percent}% hai ({plugged_str})."
            else:
                live_response = "Battery sensor data not available."
        elif "ram" in targets:
            mem = psutil.virtual_memory()
            used_gb = round(mem.used / (1024**3), 2)
            total_gb = round(mem.total / (1024**3), 2)
            live_response = f"RAM Usage: {mem.percent}% ({used_gb} GB used out of {total_gb} GB)."
        elif "cpu" in targets:
            live_response = f"CPU Usage abhi {psutil.cpu_percent(interval=None)}% chal raha hai."
        elif "disk" in targets or "storage" in targets:
            disk = psutil.disk_usage(os.path.abspath(os.sep))
            free_gb = round(disk.free / (1024**3), 2)
            total_gb = round(disk.total / (1024**3), 2)
            live_response = f"Drive C: me {free_gb} GB free storage bacha hai ({total_gb} GB me se)."
        else:
            live_response = f"System Overview: CPU {psutil.cpu_percent(interval=None)}%, RAM {psutil.virtual_memory().percent}%."

    elif intent == "OPEN_APP":
        app_name = entities.get("app_name", "application")
        live_response = f"Intent identified: '{app_name}' open karne ki command hai (Phase 4 Tools me direct launch hoga)."

    elif intent == "PLAY_MUSIC":
        track = entities.get("track_or_query", "music")
        live_response = f"Music command detected: '{track}' play karne ki request hai."

    elif intent == "FILE_SEARCH":
        file_target = entities.get("file_name", entities.get("file_query", "file"))
        live_response = f"File search target: '{file_target}' dhoondne ki request hai."

    elif intent == "REMINDER":
        time_exp = entities.get("time_expression", "")
        live_response = f"Reminder request: '{request.text}' (Time: {time_exp or 'specified time'})."

    prediction["live_response"] = live_response

    logger.info(
        "Intent: %s (Confidence: %s%%, Latency: %sms)",
        intent,
        prediction.get("confidence_percent"),
        latency_ms,
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
