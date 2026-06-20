from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    timestamp: datetime


class PeerEndpoint(BaseModel):
    name: str = Field(min_length=1)
    url: HttpUrl


class PeerCheckRequest(BaseModel):
    peers: list[PeerEndpoint]


class DetectRequest(BaseModel):
    request_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp: datetime
    location: str = Field(min_length=1)
    motion_detected: bool = False
    motion_score: float = Field(ge=0.0, le=1.0, default=0.0)
    image_base64: str | None = None
    snapshot_url: HttpUrl | None = None
    snapshot_path: str | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "DetectRequest":
        if not any([self.image_base64, self.snapshot_url, self.snapshot_path]):
            raise ValueError("One of image_base64, snapshot_url, snapshot_path is required")
        return self


class DetectResponse(BaseModel):
    request_id: str
    camera_id: str
    timestamp: datetime
    detections: list[dict[str, Any]]
    unknown_person: bool = False
    risk_level: Literal["info", "warning", "danger"] = "info"


class CameraProbeResponse(BaseModel):
    ok: bool
    camera_id: str
    location: str
    timestamp: datetime
    frame_bytes: int | None = None
    frame_width: int | None = None
    frame_height: int | None = None
    snapshot_path: str | None = None
    error: str | None = None
    message: str | None = None
    motion_detected: bool | None = None
    motion_score: float | None = None
    motion_threshold: float | None = None
    next_action: str | None = None

