# Camera Stream A2

Đây là bản A2 của đề tài `Camera Stream`, đóng gói theo hướng:

- FastAPI service cho camera
- kiểm tra kết nối peer theo IP lớp học
- motion detection tối thiểu
- `/health` hỗ trợ `GET` và `HEAD`
- Docker + Docker Compose
- Postman/Newman cho kiểm thử contract

## Chạy nhanh

```powershell
copy .env.example .env
copy peers.example.json peers.json
.\check_peers.ps1
.\start_demo.ps1
```

## API chính

- `GET /health`
- `HEAD /health`
- `GET /camera/check`
- `GET /camera/motion`
- `GET /camera/trigger`
- `POST /detect`
- `GET /peers`
- `POST /peer-check`

## Demo ở lớp

1. Lấy IP máy demo bằng `ipconfig`.
2. Điền IP của các nhóm khác vào `peers.json`.
3. Chạy `.\check_peers.ps1` để test kết nối.
4. Chạy `.\start_demo.ps1` để mở service.
5. Chia sẻ `http://<ip-cua-ban>:8000` cho các nhóm khác.

## Cấu hình

File mẫu:

- `.env.example`
- `peers.example.json`

Biến quan trọng:

- `CAMERA_STREAM_URL`
- `CAMERA_ID`
- `CAMERA_LOCATION`
- `MOTION_THRESHOLD`
- `AI_SERVICE_URL`
- `PEER_ENDPOINTS`

## Docker

Build:

```powershell
docker build -t camera-a2-api:latest .
```

Compose:

```powershell
docker compose up -d --build
```

## Newman

```powershell
newman run postman/camera-api.postman_collection.json -e postman/local.postman_environment.json -r cli,html,junit --reporter-html-export reports/newman.html --reporter-junit-export reports/newman.xml
```

## Ghi chú

- `POST /detect` trả `400` nếu payload thiếu field bắt buộc.
- `GET /camera/motion` dùng 2 frame liên tiếp để tính motion.
- Khi có motion, snapshot được lưu trong `snapshots/<camera_id>/`.
