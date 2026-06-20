from __future__ import annotations

from fastapi import FastAPI

from app.schemas import DetectRequest
from app.services.ai_client import mock_detect

app = FastAPI(title="ai-mock")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "ai-mock"}


@app.post("/detect")
async def detect(payload: DetectRequest):
    return mock_detect(payload)

