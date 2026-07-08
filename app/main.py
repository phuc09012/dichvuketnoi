from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import asyncio
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.schemas import DetectRequest, HealthResponse, PeerCheckRequest
from app.services.ai_client import forward_detect_request, mock_detect
from app.services.camera import (
    build_trigger_payload,
    get_local_ipv4,
    http_get,
    motion_probe_camera,
    parse_peer_endpoints,
    probe_camera,
    mark_ai_called,
    stream_mjpeg_bytes,
    should_call_ai,
)

settings = get_settings()
settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=settings.app_name)
web_dir = Path(__file__).resolve().parent / "web"
app.mount("/web", StaticFiles(directory=str(web_dir)), name="web")
app.mount("/snapshots", StaticFiles(directory=str(settings.snapshot_dir)), name="snapshots")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


def list_recent_snapshots(limit: int = 12) -> list[dict[str, Any]]:
    camera_dir = settings.snapshot_dir / settings.camera_id
    if not camera_dir.exists():
        return []

    snapshots: list[dict[str, Any]] = []
    for path in sorted(camera_dir.glob("*.jpg"), key=lambda item: item.stat().st_mtime, reverse=True):
        stat = path.stat()
        relative_path = path.relative_to(settings.snapshot_dir).as_posix()
        snapshot_url = f"/snapshots/{relative_path}"
        snapshots.append(
            {
                "name": path.name,
                "path": relative_path,
                "url": snapshot_url,
                "public_url": f"{settings.public_base_url.rstrip('/')}{snapshot_url}" if settings.public_base_url else None,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone().isoformat(),
            }
        )
        if len(snapshots) >= limit:
            break
    return snapshots


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(web_dir / "index.html")


@app.api_route("/health", methods=["GET", "HEAD"], response_model=HealthResponse)
async def health(request: Request) -> Response | HealthResponse:
    if request.method == "HEAD":
        return Response(status_code=200)
    return HealthResponse(status="ok", service=settings.app_name, timestamp=utc_now())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": jsonable_encoder(exc.errors())})


@app.get("/peers")
async def peers() -> dict[str, Any]:
    return {
        "status": "ok",
        "local_ip": get_local_ipv4(),
        "peers": parse_peer_endpoints(settings.peer_endpoints),
        "timestamp": utc_now(),
    }


@app.get("/api/runtime")
async def runtime() -> dict[str, Any]:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "local_ip": get_local_ipv4(),
        "host": settings.host,
        "port": settings.port,
        "camera": {
            "id": settings.camera_id,
            "location": settings.camera_location,
            "stream_url_set": bool(settings.camera_stream_url),
            "stream_url": settings.camera_stream_url or None,
            "live_url": "/camera/live",
            "motion_threshold": settings.motion_threshold,
            "timeout": settings.camera_timeout,
        },
        "ai": {
            "service_url": settings.ai_service_url,
            "detect_path": settings.ai_detect_path,
            "payload_mode": settings.ai_payload_mode,
            "auth_enabled": bool(settings.ai_auth_header_name and settings.ai_auth_header_value),
            "cooldown_seconds": settings.camera_cooldown_seconds,
        },
        "a4": {
            "service_url": settings.a4_service_url,
            "detect_path": settings.a4_detect_path,
            "auth_enabled": bool(settings.ai_auth_header_name and settings.ai_auth_header_value),
        },
        "mqtt": {
            "enabled": settings.mqtt_enabled,
            "broker_host": settings.mqtt_broker_host,
            "broker_port": settings.mqtt_broker_port,
            "topic": settings.mqtt_topic_camera_events,
            "username_set": bool(settings.mqtt_username),
        },
        "network": {
            "public_base_url": settings.public_base_url,
            "peer_endpoints": parse_peer_endpoints(settings.peer_endpoints),
        },
        "snapshots": {
            "count": len(list_recent_snapshots(limit=100)),
            "recent": list_recent_snapshots(limit=12),
        },
        "timestamp": utc_now(),
    }


@app.get("/api/snapshots")
async def snapshots(limit: int = 12) -> dict[str, Any]:
    limit = max(1, min(limit, 48))
    return {
        "status": "ok",
        "camera_id": settings.camera_id,
        "items": list_recent_snapshots(limit=limit),
        "timestamp": utc_now(),
    }


@app.get("/camera/check")
async def camera_check() -> JSONResponse:
    result = await asyncio.to_thread(probe_camera, settings)
    return JSONResponse(content=result)


@app.get("/camera/live")
async def camera_live() -> StreamingResponse:
    if not settings.camera_stream_url:
        return StreamingResponse(iter([b"CAMERA_STREAM_URL is not set"]), media_type="text/plain", status_code=503)
    return StreamingResponse(
        stream_mjpeg_bytes(settings.camera_stream_url),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/camera/motion")
async def camera_motion() -> JSONResponse:
    result = await asyncio.to_thread(motion_probe_camera, settings)
    return JSONResponse(content=result)


@app.get("/camera/trigger")
async def camera_trigger() -> JSONResponse:
    result = await asyncio.to_thread(build_trigger_payload, settings)
    return JSONResponse(content=result)


@app.post("/peer-check")
async def peer_check(payload: PeerCheckRequest) -> dict[str, Any]:
    results = []
    for peer in payload.peers:
        status, message = http_get(str(peer.url), timeout=settings.http_timeout)
        results.append(
            {
                "name": peer.name,
                "url": str(peer.url),
                "ok": status is not None,
                "status": status,
                "message": message,
            }
        )
    return {"ok": True, "local_ip": get_local_ipv4(), "results": results, "timestamp": utc_now()}


@app.post("/detect")
async def detect(payload: DetectRequest) -> Any:
    if not payload.motion_detected:
        return mock_detect(payload)

    if not should_call_ai(payload.camera_id, settings.camera_cooldown_seconds):
        return {
            "request_id": payload.request_id,
            "camera_id": payload.camera_id,
            "status": "throttled",
            "reason": "camera_cooldown_active",
            "cooldown_seconds": settings.camera_cooldown_seconds,
            "timestamp": utc_now(),
        }

    if settings.ai_service_url:
        try:
            forwarded = await forward_detect_request(
                settings.ai_service_url,
                settings.ai_detect_path,
                payload,
                timeout=settings.http_timeout,
                payload_mode=settings.ai_payload_mode,
                auth_header_name=settings.ai_auth_header_name,
                auth_header_value=settings.ai_auth_header_value,
                public_base_url=settings.public_base_url,
            )
            return forwarded
        except Exception:
            pass
        finally:
            mark_ai_called(payload.camera_id)
    return mock_detect(payload)


@app.post("/api/a4/detect")
async def a4_detect(payload: DetectRequest) -> Any:
    if not settings.a4_service_url:
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": "A4_SERVICE_URL is not configured",
                "timestamp": utc_now(),
            },
        )

    try:
        a4_timeout = max(settings.http_timeout, 45.0)
        forwarded = await asyncio.wait_for(
            forward_detect_request(
                settings.a4_service_url,
                settings.a4_detect_path,
                payload,
                timeout=a4_timeout,
                payload_mode="url",
                auth_header_name=settings.ai_auth_header_name,
                auth_header_value=settings.ai_auth_header_value,
                public_base_url=settings.public_base_url,
            ),
            timeout=a4_timeout + 5.0,
        )
        return forwarded
    except (TimeoutError, httpx.TimeoutException, httpx.RequestError):
        return JSONResponse(
            status_code=504,
            content={
                "status": "error",
                "message": "A4 request timed out",
                "camera_id": payload.camera_id,
                "request_id": payload.request_id,
                "timestamp": utc_now().isoformat(),
            },
        )
