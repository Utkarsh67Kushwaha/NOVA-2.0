import os
import platform
import time
from typing import Any, Dict
from fastapi import APIRouter
import psutil

from backend.app.core.config import settings
from backend.app.core.logger import logger

router = APIRouter()
START_TIME = time.time()


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
        },
    }
