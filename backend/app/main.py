from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.app.api.routes import router
from backend.app.api.voice_routes import router as voice_router
from backend.app.core.config import settings
from backend.app.core.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan event handler for controlled startup and shutdown."""
    logger.info("Initializing %s v%s in %s mode...", settings.APP_NAME, settings.VERSION, settings.NOVA_ENV)
    yield
    logger.info("Shutting down %s cleanly.", settings.APP_NAME)


def create_app() -> FastAPI:
    """Application factory for FastAPI backend."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    # CORS middleware for local frontend communication
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(voice_router)

    # Serve built frontend static files if available
    dist_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
    if dist_dir.exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")

    return app


app = create_app()


def start() -> None:
    """Server entrypoint."""
    uvicorn.run(
        "backend.app.main:app",
        host=settings.NOVA_HOST,
        port=settings.NOVA_PORT,
        reload=False,
        log_level=settings.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    start()
