"""FastAPI application entry-point for LingBot-Map reconstruction API."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .inference_worker import InferenceWorker
from .routers import health as health_router
from .routers import jobs as jobs_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_path: str = os.environ.get("MODEL_PATH", "")
    use_sdpa: bool = os.environ.get("USE_SDPA", "false").lower() in ("1", "true")

    worker = InferenceWorker(model_path=model_path, use_sdpa=use_sdpa)
    worker.start()
    app.state.worker = worker
    logger.info("Inference worker iniciado (model_path=%s)", model_path or "<não configurado>")

    yield

    worker.stop()
    logger.info("Inference worker encerrado.")


app = FastAPI(
    title="LingBot-Map API",
    description="API REST para reconstrução 3D em streaming via Geometric Context Transformer.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — restrict origins in production via CORS_ORIGINS env var
_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs_router.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(health_router.router, prefix="/api", tags=["health"])
