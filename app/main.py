from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
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
)

settings = get_settings()
settings.snapshot_dir.mkdir(parents=True, exist_ok=True)
app = FastAPI(title=settings.app_name)
app.mount("/snapshots", StaticFiles(directory=str(settings.snapshot_dir)), name="snapshots")


def utc_now() -> datetime:
    return datetime.now(timezone.utc).astimezone()


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


@app.get("/camera/check")
async def camera_check() -> JSONResponse:
    return JSONResponse(content=probe_camera(settings))


@app.get("/camera/motion")
async def camera_motion() -> JSONResponse:
    return JSONResponse(content=motion_probe_camera(settings))


@app.get("/camera/trigger")
async def camera_trigger() -> JSONResponse:
    return JSONResponse(content=build_trigger_payload(settings))


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
            )
            return forwarded
        except Exception:
            pass
    return mock_detect(payload)
