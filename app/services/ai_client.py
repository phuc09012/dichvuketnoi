from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx

from app.schemas import DetectRequest, DetectResponse
from app.services.camera import build_snapshot_url


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def mock_detect(payload: DetectRequest) -> DetectResponse:
    detections = []
    if payload.motion_detected:
        detections.append(
            {
                "label": "person",
                "confidence": 0.92,
            }
        )

    risk_level = "warning" if payload.motion_detected else "info"
    return DetectResponse(
        request_id=payload.request_id,
        camera_id=payload.camera_id,
        timestamp=datetime.now(timezone.utc).astimezone(),
        detections=detections,
        unknown_person=payload.motion_detected,
        risk_level=risk_level,
    )


def build_detect_url(service_url: str, detect_path: str) -> str:
    parsed = urlparse(service_url)
    if parsed.path and parsed.path != "/":
        return service_url

    path = detect_path if detect_path.startswith("/") else f"/{detect_path}"
    return urlunparse(parsed._replace(path=path, params="", query="", fragment=""))


async def forward_detect_request(
    service_url: str,
    detect_path: str,
    payload: DetectRequest,
    timeout: float,
    payload_mode: str = "url",
    auth_header_name: str = "",
    auth_header_value: str = "",
    public_base_url: str = "",
) -> dict[str, Any]:
    detect_url = build_detect_url(service_url, detect_path)
    headers = {}
    if auth_header_name and auth_header_value:
        headers[auth_header_name] = auth_header_value
    request_body: dict[str, Any] = {"timestamp": payload.timestamp.isoformat()}
    if payload_mode.lower() == "base64":
        image_base64 = payload.image_base64
        if not image_base64 and payload.snapshot_path:
            image_base64 = base64.b64encode(Path(payload.snapshot_path).read_bytes()).decode("ascii")
        request_body["image_base64"] = image_base64 or ""
    else:
        snapshot_url = str(payload.snapshot_url) if payload.snapshot_url else ""
        if not snapshot_url and payload.snapshot_path:
            snapshot_url = build_snapshot_url(public_base_url, payload.snapshot_path) or ""
        request_body["image_url"] = snapshot_url
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(detect_url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
