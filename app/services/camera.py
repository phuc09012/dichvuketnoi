from __future__ import annotations

import base64
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageStat

from app.config import Settings


@dataclass(frozen=True)
class PeerStatus:
    name: str
    url: str
    ok: bool
    status: int | None
    message: str


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_local_ipv4() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def http_get(url: str, timeout: float) -> tuple[int | None, str]:
    request = Request(url, method="GET", headers={"User-Agent": "CameraA2/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(200).decode("utf-8", errors="replace")
    except URLError as error:
        return None, str(error.reason if hasattr(error, "reason") else error)
    except OSError as error:
        return None, str(error)


def parse_peer_endpoints(raw_value: str) -> list[dict[str, str]]:
    if not raw_value:
        return []
    result: list[dict[str, str]] = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        name, url = item.split("=", 1)
        result.append({"name": name.strip(), "url": url.strip()})
    return result


def _extract_jpegs_from_buffer(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    cursor = 0
    while True:
        start = buffer.find(b"\xff\xd8", cursor)
        if start == -1:
            break
        end = buffer.find(b"\xff\xd9", start + 2)
        if end == -1:
            break
        frames.append(bytes(buffer[start : end + 2]))
        cursor = end + 2
    return frames


def read_mjpeg_frames(url: str, timeout: float, count: int = 2, max_bytes: int = 5_000_000) -> list[bytes]:
    request = Request(url, method="GET", headers={"User-Agent": "CameraA2/1.0"})
    with urlopen(request, timeout=timeout) as response:
        buffer = bytearray()
        while len(buffer) < max_bytes:
            chunk = response.read(8192)
            if not chunk:
                break
            buffer.extend(chunk)
            frames = _extract_jpegs_from_buffer(buffer)
            if len(frames) >= count:
                return frames[:count]
    raise RuntimeError("Unable to extract enough JPEG frames from stream")


def extract_image_size(jpeg_bytes: bytes) -> tuple[int | None, int | None]:
    with Image.open(BytesIO(jpeg_bytes)) as image:
        return image.width, image.height


def save_snapshot(snapshot_dir: Path, camera_id: str, jpeg_bytes: bytes) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    camera_dir = snapshot_dir / camera_id
    camera_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = camera_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    snapshot_path.write_bytes(jpeg_bytes)
    return snapshot_path


def build_snapshot_url(public_base_url: str, snapshot_path: str | Path) -> str | None:
    if not public_base_url:
        return None
    relative_path = str(snapshot_path).replace("\\", "/")
    if not relative_path.startswith("/"):
        relative_path = "/" + relative_path
    return f"{public_base_url.rstrip('/')}{relative_path}"


def encode_image_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("ascii")


def compute_motion_score(previous_jpeg: bytes, current_jpeg: bytes) -> float:
    with Image.open(BytesIO(previous_jpeg)) as previous_image:
        with Image.open(BytesIO(current_jpeg)) as current_image:
            previous_gray = previous_image.convert("L").resize((64, 64))
            current_gray = current_image.convert("L").resize((64, 64))
            diff = ImageChops.difference(previous_gray, current_gray)
            stat = ImageStat.Stat(diff)
            return float(stat.mean[0] / 255.0)


def probe_camera(settings: Settings) -> dict[str, Any]:
    if not settings.camera_stream_url:
        return {
            "ok": False,
            "error": "camera_stream_missing",
            "message": "CAMERA_STREAM_URL is not set",
            "camera_id": settings.camera_id,
            "timestamp": iso_now(),
        }

    try:
        jpeg_bytes = read_mjpeg_frames(settings.camera_stream_url, timeout=settings.camera_timeout, count=1)[0]
    except Exception as exc:
        return {
            "ok": False,
            "error": "camera_stream_unavailable",
            "camera_id": settings.camera_id,
            "message": str(exc),
            "timestamp": iso_now(),
        }

    width, height = extract_image_size(jpeg_bytes)
    snapshot_path = save_snapshot(settings.snapshot_dir, settings.camera_id, jpeg_bytes)
    return {
        "ok": True,
        "camera_id": settings.camera_id,
        "location": settings.camera_location,
        "timestamp": iso_now(),
        "frame_bytes": len(jpeg_bytes),
        "frame_width": width,
        "frame_height": height,
        "snapshot_path": str(snapshot_path),
    }


def motion_probe_camera(settings: Settings) -> dict[str, Any]:
    if not settings.camera_stream_url:
        return {
            "ok": False,
            "error": "camera_stream_missing",
            "message": "CAMERA_STREAM_URL is not set",
            "camera_id": settings.camera_id,
            "timestamp": iso_now(),
        }

    try:
        frames = read_mjpeg_frames(settings.camera_stream_url, timeout=settings.camera_timeout, count=2)
    except Exception as exc:
        return {
            "ok": False,
            "error": "camera_stream_unavailable",
            "camera_id": settings.camera_id,
            "message": str(exc),
            "timestamp": iso_now(),
        }

    if len(frames) < 2:
        return {
            "ok": False,
            "error": "insufficient_frames",
            "camera_id": settings.camera_id,
            "message": "Need at least two frames for motion detection",
            "timestamp": iso_now(),
        }

    previous_frame, current_frame = frames[0], frames[1]
    width, height = extract_image_size(current_frame)
    motion_score = compute_motion_score(previous_frame, current_frame)
    motion_detected = motion_score >= settings.motion_threshold
    snapshot_path = save_snapshot(settings.snapshot_dir, settings.camera_id, current_frame)
    return {
        "ok": True,
        "camera_id": settings.camera_id,
        "location": settings.camera_location,
        "timestamp": iso_now(),
        "frame_bytes": len(current_frame),
        "frame_width": width,
        "frame_height": height,
        "snapshot_path": str(snapshot_path),
        "motion_detected": motion_detected,
        "motion_score": round(motion_score, 4),
        "motion_threshold": settings.motion_threshold,
        "next_action": "send_to_ai_vision" if motion_detected else "skip_ai_vision",
    }


def build_trigger_payload(settings: Settings) -> dict[str, Any]:
    probe = motion_probe_camera(settings)
    snapshot_url = build_snapshot_url(settings.public_base_url, probe.get("snapshot_path")) if probe.get("ok") else None
    image_base64 = None
    if probe.get("ok") and settings.ai_payload_mode.lower() == "base64":
        snapshot_path_value = probe.get("snapshot_path")
        if snapshot_path_value:
            image_base64 = encode_image_base64(Path(snapshot_path_value).read_bytes())
    return {
        "status": "ok" if probe.get("ok") else "warning",
        "event_type": "camera.motion.triggered" if probe.get("motion_detected") else "camera.motion.skipped",
        "request_id": f"vision-request-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "source_service": "team-camera",
        "camera_id": settings.camera_id,
        "timestamp": iso_now(),
        "location": settings.camera_location,
        "snapshot_url": snapshot_url,
        "image_base64": image_base64,
        "probe": probe,
    }
