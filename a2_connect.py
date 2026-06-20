from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class PeerEndpoint:
    name: str
    url: str


@dataclass(frozen=True)
class CameraConfig:
    camera_id: str
    stream_url: str
    location: str
    snapshot_dir: Path
    request_timeout: float = 5.0
    motion_threshold: float = 0.08


def iso_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def get_local_ipv4() -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def load_peers_from_env(raw_value: str | None) -> list[PeerEndpoint]:
    if not raw_value:
        return []

    peers: list[PeerEndpoint] = []
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid peer entry: {item!r}. Expected name=url.")
        name, url = item.split("=", 1)
        peers.append(PeerEndpoint(name=name.strip(), url=url.strip()))
    return peers


def load_peers_from_json(path: Path) -> list[PeerEndpoint]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    peers: list[PeerEndpoint] = []
    for item in payload:
        peers.append(PeerEndpoint(name=item["name"], url=item["url"]))
    return peers


def load_camera_config_from_env() -> CameraConfig:
    stream_url = os.getenv("CAMERA_STREAM_URL", "").strip()
    camera_id = os.getenv("CAMERA_ID", "cam-gate-a").strip()
    location = os.getenv("CAMERA_LOCATION", "Main Gate A").strip()
    snapshot_dir = Path(os.getenv("SNAPSHOT_DIR", "snapshots")).expanduser()
    timeout = float(os.getenv("CAMERA_TIMEOUT", "5"))
    motion_threshold = float(os.getenv("MOTION_THRESHOLD", "0.08"))
    return CameraConfig(
        camera_id=camera_id,
        stream_url=stream_url,
        location=location,
        snapshot_dir=snapshot_dir,
        request_timeout=timeout,
        motion_threshold=motion_threshold,
    )


def http_get(url: str, timeout: float) -> tuple[int | None, str]:
    request = Request(url, method="GET", headers={"User-Agent": "A2Camera/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, response.read(200).decode("utf-8", errors="replace")
    except URLError as error:
        return None, str(error.reason if hasattr(error, "reason") else error)
    except OSError as error:
        return None, str(error)


def _extract_jpegs_from_buffer(buffer: bytearray) -> list[bytes]:
    frames: list[bytes] = []
    search_start = 0
    while True:
        start = buffer.find(b"\xff\xd8", search_start)
        if start == -1:
            break
        end = buffer.find(b"\xff\xd9", start + 2)
        if end == -1:
            break
        frames.append(bytes(buffer[start : end + 2]))
        search_start = end + 2
    return frames


def read_mjpeg_frames(url: str, timeout: float, count: int = 2, max_bytes: int = 5_000_000) -> list[bytes]:
    request = Request(url, method="GET", headers={"User-Agent": "A2Camera/1.0"})
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


def read_mjpeg_first_frame(url: str, timeout: float, max_bytes: int = 5_000_000) -> bytes:
    frames = read_mjpeg_frames(url, timeout=timeout, count=1, max_bytes=max_bytes)
    return frames[0]


def extract_image_size(jpeg_bytes: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image  # type: ignore
    except Exception:
        return None, None

    with Image.open(BytesIO(jpeg_bytes)) as image:
        return image.width, image.height


def image_signature(jpeg_bytes: bytes, size: tuple[int, int] = (64, 64)) -> list[int]:
    from PIL import Image  # type: ignore

    with Image.open(BytesIO(jpeg_bytes)) as image:
        grayscale = image.convert("L").resize(size)
        return list(grayscale.getdata())


def compute_motion_score(previous_jpeg: bytes, current_jpeg: bytes) -> float:
    from PIL import Image, ImageChops, ImageStat  # type: ignore

    with Image.open(BytesIO(previous_jpeg)) as previous_image:
        with Image.open(BytesIO(current_jpeg)) as current_image:
            previous_gray = previous_image.convert("L").resize((64, 64))
            current_gray = current_image.convert("L").resize((64, 64))
            diff = ImageChops.difference(previous_gray, current_gray)
            stat = ImageStat.Stat(diff)
            return float(stat.mean[0] / 255.0)


def save_snapshot(snapshot_dir: Path, camera_id: str, jpeg_bytes: bytes) -> Path:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    camera_dir = snapshot_dir / camera_id
    camera_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = camera_dir / f"{stamp}.jpg"
    snapshot_path.write_bytes(jpeg_bytes)
    return snapshot_path


def probe_camera(config: CameraConfig) -> dict[str, Any]:
    if not config.stream_url:
        return {
            "ok": False,
            "error": "camera_stream_missing",
            "message": "CAMERA_STREAM_URL is not set",
            "camera_id": config.camera_id,
            "timestamp": iso_now(),
        }

    try:
        jpeg_bytes = read_mjpeg_first_frame(config.stream_url, timeout=config.request_timeout)
    except Exception as exc:
        return {
            "ok": False,
            "error": "camera_stream_unavailable",
            "camera_id": config.camera_id,
            "message": str(exc),
            "timestamp": iso_now(),
        }

    width, height = extract_image_size(jpeg_bytes)
    snapshot_path = save_snapshot(config.snapshot_dir, config.camera_id, jpeg_bytes)
    return {
        "ok": True,
        "camera_id": config.camera_id,
        "location": config.location,
        "timestamp": iso_now(),
        "frame_bytes": len(jpeg_bytes),
        "frame_width": width,
        "frame_height": height,
        "snapshot_path": str(snapshot_path),
    }


def motion_probe_camera(config: CameraConfig) -> dict[str, Any]:
    if not config.stream_url:
        return {
            "ok": False,
            "error": "camera_stream_missing",
            "message": "CAMERA_STREAM_URL is not set",
            "camera_id": config.camera_id,
            "timestamp": iso_now(),
        }

    try:
        frames = read_mjpeg_frames(config.stream_url, timeout=config.request_timeout, count=2)
    except Exception as exc:
        return {
            "ok": False,
            "error": "camera_stream_unavailable",
            "camera_id": config.camera_id,
            "message": str(exc),
            "timestamp": iso_now(),
        }

    if len(frames) < 2:
        return {
            "ok": False,
            "error": "insufficient_frames",
            "camera_id": config.camera_id,
            "message": "Need at least two frames for motion detection",
            "timestamp": iso_now(),
        }

    previous_frame, current_frame = frames[0], frames[1]
    width, height = extract_image_size(current_frame)
    motion_score = compute_motion_score(previous_frame, current_frame)
    motion_detected = motion_score >= config.motion_threshold
    snapshot_path = save_snapshot(config.snapshot_dir, config.camera_id, current_frame)
    return {
        "ok": True,
        "camera_id": config.camera_id,
        "location": config.location,
        "timestamp": iso_now(),
        "frame_bytes": len(current_frame),
        "frame_width": width,
        "frame_height": height,
        "snapshot_path": str(snapshot_path),
        "motion_detected": motion_detected,
        "motion_score": round(motion_score, 4),
        "motion_threshold": config.motion_threshold,
        "next_action": "send_to_ai_vision" if motion_detected else "skip_ai_vision",
    }


def build_metadata(config: CameraConfig, frame_width: int | None, frame_height: int | None) -> dict[str, Any]:
    return {
        "camera_id": config.camera_id,
        "frame_id": f"frame-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "timestamp": iso_now(),
        "location": config.location,
        "frame_width": frame_width,
        "frame_height": frame_height,
    }


def print_report(local_ip: str, peers: Iterable[PeerEndpoint], timeout: float) -> bool:
    print(f"Local IP: {local_ip}")
    ok = True
    for peer in peers:
        status, message = http_get(peer.url, timeout=timeout)
        if status is None:
            ok = False
            print(f"[FAIL] {peer.name}: {peer.url} -> {message}")
        else:
            print(f"[OK]   {peer.name}: {peer.url} -> HTTP {status}")
    return ok


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(content_length) if content_length else b"{}"
    return json.loads(raw.decode("utf-8"))


def send_json(handler: BaseHTTPRequestHandler, status_code: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


class A2Handler(BaseHTTPRequestHandler):
    server_version = "A2Camera/1.0"

    def _config(self) -> "A2Runtime":
        return self.server.runtime  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        runtime = self._config()
        if self.path == "/health":
            send_json(
                self,
                200,
                {
                    "status": "ok",
                    "service": "a2-camera",
                    "local_ip": get_local_ipv4(),
                    "camera_id": runtime.camera.camera_id,
                    "timestamp": iso_now(),
                },
            )
            return

        if self.path == "/peers":
            send_json(
                self,
                200,
                {
                    "status": "ok",
                    "peers": [peer.__dict__ for peer in runtime.peers],
                    "timestamp": iso_now(),
                },
            )
            return

        if self.path == "/camera/check":
            send_json(self, 200, probe_camera(runtime.camera))
            return

        if self.path == "/camera/motion":
            send_json(self, 200, motion_probe_camera(runtime.camera))
            return

        if self.path == "/camera/metadata":
            probe = probe_camera(runtime.camera) if runtime.camera.stream_url else {}
            send_json(
                self,
                200,
                {
                    "status": "ok" if probe.get("ok") else "warning",
                    "metadata": build_metadata(
                        runtime.camera,
                        probe.get("frame_width"),
                        probe.get("frame_height"),
                    ),
                    "probe": probe,
                    "timestamp": iso_now(),
                },
            )
            return

        if self.path == "/camera/trigger":
            probe = motion_probe_camera(runtime.camera)
            response = {
                "status": "ok" if probe.get("ok") else "warning",
                "event_type": "camera.motion.triggered" if probe.get("motion_detected") else "camera.motion.skipped",
                "request_id": f"vision-request-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "source_service": "team-camera",
                "camera_id": runtime.camera.camera_id,
                "timestamp": iso_now(),
                "location": runtime.camera.location,
                "probe": probe,
            }
            send_json(self, 200, response)
            return

        self.send_error(404, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        runtime = self._config()
        if self.path == "/peer-check":
            try:
                payload = read_json_body(self)
                peers = [
                    PeerEndpoint(name=item["name"], url=item["url"])
                    for item in payload.get("peers", [])
                ]
            except Exception as exc:
                send_json(
                    self,
                    400,
                    {
                        "ok": False,
                        "error": "invalid_payload",
                        "message": str(exc),
                        "timestamp": iso_now(),
                    },
                )
                return

            result = {
                "ok": True,
                "local_ip": get_local_ipv4(),
                "results": [],
                "timestamp": iso_now(),
            }
            for peer in peers:
                status, message = http_get(peer.url, timeout=runtime.peer_timeout)
                result["results"].append(
                    {
                        "name": peer.name,
                        "url": peer.url,
                        "ok": status is not None,
                        "status": status,
                        "message": message,
                    }
                )
            send_json(self, 200, result)
            return

        self.send_error(404, "Not Found")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


@dataclass
class A2Runtime:
    camera: CameraConfig
    peers: list[PeerEndpoint]
    peer_timeout: float = 3.0


def serve(runtime: A2Runtime, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), A2Handler)
    server.runtime = runtime  # type: ignore[attr-defined]
    print(f"Serving on http://{host}:{port}")
    print(f"Local IP: {get_local_ipv4()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser(description="A2 camera connection helper")
    parser.add_argument("--peers-file", type=Path, help="JSON file with peer endpoints")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--serve", action="store_true", help="Run local HTTP server")
    parser.add_argument("--host", default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--motion-threshold", type=float, default=float(os.getenv("MOTION_THRESHOLD", "0.08")))
    args = parser.parse_args()

    try:
        peers = (
            load_peers_from_json(args.peers_file)
            if args.peers_file
            else load_peers_from_env(os.getenv("PEER_ENDPOINTS"))
        )
    except Exception as exc:
        print(f"Failed to load peers: {exc}")
        return 1

    camera = load_camera_config_from_env()
    camera = CameraConfig(
        camera_id=camera.camera_id,
        stream_url=camera.stream_url,
        location=camera.location,
        snapshot_dir=camera.snapshot_dir,
        request_timeout=camera.request_timeout,
        motion_threshold=args.motion_threshold,
    )
    runtime = A2Runtime(camera=camera, peers=peers, peer_timeout=args.timeout)

    if args.serve:
        serve(runtime, host=args.host, port=args.port)
        return 0

    if runtime.camera.stream_url:
        probe = probe_camera(runtime.camera)
        print(json.dumps(probe, ensure_ascii=False, indent=2))
        if probe.get("ok"):
            metadata = build_metadata(
                runtime.camera,
                probe.get("frame_width"),
                probe.get("frame_height"),
            )
            print(json.dumps({"metadata": metadata}, ensure_ascii=False, indent=2))
    else:
        print("CAMERA_STREAM_URL is not set; skipping camera probe.")

    if not peers:
        print("No peers configured.")
        print("Set PEER_ENDPOINTS=name=http://ip:port/health,name2=http://ip:port/health")
        return 1

    success = print_report(get_local_ipv4(), peers, timeout=args.timeout)
    return 0 if success else 2


if __name__ == "__main__":
    raise SystemExit(main())
