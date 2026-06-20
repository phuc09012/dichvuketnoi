# A2 Quickstart

Mục tiêu của bước này: lấy IP máy demo của nhóm A2, kiểm tra kết nối tới các máy nhóm khác trong cùng hotspot, và chạy service camera bằng FastAPI.

## 1. Lấy IP máy hiện tại

PowerShell:

```powershell
ipconfig
```

Hoặc:

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '172.20.10.*' }
```

## 2. Ghi IP nhóm khác vào file cấu hình

Copy `peers.example.json` thành `peers.json` và thay IP thật của các máy khác.

Ví dụ:

```json
[
  { "name": "ai-vision", "url": "http://172.20.10.10:8000/health" },
  { "name": "core-business", "url": "http://172.20.10.11:8000/health" }
]
```

## 3. Kiểm tra kết nối

```powershell
python a2_connect.py --peers-file peers.json
```

Nếu muốn dùng biến môi trường:

```powershell
$env:AI_SERVICE_URL="http://26.15.57.238:8000"
$env:AI_DETECT_PATH="/api/v1/vision/detect"
$env:AI_PAYLOAD_MODE="url"
$env:AI_AUTH_HEADER_NAME="Authorization"
$env:AI_AUTH_HEADER_VALUE="Bearer smart-campus-secret-token"
$env:PUBLIC_BASE_URL="http://26.195.153.35:8000"
$env:PEER_ENDPOINTS="a4=http://26.15.57.238:8000/health,a3=http://26.144.83.132:8000/health"
python a2_connect.py
```

Nếu A4 yêu cầu token khác, đổi lại `AI_AUTH_HEADER_NAME` và `AI_AUTH_HEADER_VALUE` theo đúng tên header mà nhóm A4 cung cấp.

Nếu A4 chấp nhận ảnh base64, đổi:

```powershell
$env:AI_PAYLOAD_MODE="base64"
```

## 4. Chạy service local

Thiết lập camera stream:

```powershell
$env:CAMERA_STREAM_URL="https://camera.labaiotdnu.app/video?key=matkhau_cua_ban"
$env:CAMERA_ID="cam-gate-a"
$env:CAMERA_LOCATION="Main Gate A"
$env:MOTION_THRESHOLD="0.08"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Mở trình duyệt hoặc curl:

```powershell
curl http://localhost:8000/health
curl http://localhost:8000/camera/check
curl http://localhost:8000/camera/metadata
curl http://localhost:8000/camera/motion
curl http://localhost:8000/camera/trigger
```

## 5. Kết quả mong đợi

- `GET /health` trả JSON trạng thái service.
- `HEAD /health` trả `200` để hợp với bộ kiểm tra ngầm.
- `GET /camera/check` thử đọc 1 frame và lưu snapshot vào `snapshots/<camera_id>/`.
- `GET /camera/motion` đọc 2 frame liên tiếp, tính `motion_score`, rồi lưu snapshot.
- `GET /camera/trigger` trả payload gần với request sẽ gửi sang AI Vision.
- `GET /camera/metadata` trả metadata khung hình và probe status.
- Báo `OK` nếu truy cập được `/health` của nhóm khác, `FAIL` nếu chưa mở port, chưa bind `0.0.0.0`, hoặc sai IP.

## 6. Phạm vi hiện tại

Đã có:

- lấy IP máy demo,
- kiểm tra peer theo IP,
- probe camera stream,
- lưu snapshot đầu tiên,
- health server local,
- motion detection,
- trigger payload cho AI Vision.

## 7. Ghi chú triển khai

- Motion detection hiện dùng so sánh 2 frame liên tiếp ở ảnh thu nhỏ grayscale.
- Nếu stream chậm hoặc frame đầu vào rỗng, endpoint `/camera/motion` sẽ báo lỗi rõ ràng.
- Khi có motion, snapshot được lưu trong `snapshots/<camera_id>/`.
