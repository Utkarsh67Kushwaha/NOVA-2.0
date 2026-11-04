import logging
import sys
from pathlib import Path
from backend.app.core.config import settings


def setup_logger(name: str = "nova") -> logging.Logger:
    """Configures and returns a structured logger with console and file handlers."""
    logger = logging.getLogger(name)

    if logger.hasHandlers():
        return logger

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Ensure log directory exists
    try:
        settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = settings.LOGS_DIR / "nova_backend.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as exc:
        logger.warning("Could not initialize file logger: %s", exc)

    logger.propagate = False
    return logger


logger = setup_logger("nova")
