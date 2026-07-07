# Hợp Đồng Camera Stream - A4 AI Vision

Tài liệu này mô tả contract giữa nhóm Camera Stream và nhóm A4 AI Vision để tích hợp gửi ảnh qua REST.

## 1. Mục tiêu

- Nhóm Camera Stream chụp snapshot khi phát hiện chuyển động.
- Nhóm Camera Stream gửi snapshot sang A4 để phân tích ảnh.
- A4 trả kết quả detect đồng bộ trong response.

## 2. Endpoint

### Health check

```http
GET /health
```

Mục đích:
- kiểm tra service A4 còn sống
- dùng trước khi gửi ảnh

### Detect ảnh

```http
POST /api/v1/vision/detect
```

## 3. Request contract

Nhóm Camera Stream gửi `application/json` theo schema sau:

```json
{
  "request_id": "vision-request-001",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-07-08T00:05:00Z",
  "location": "Main Gate A",
  "motion_detected": true,
  "motion_score": 0.82,
  "image_url": "http://<ip-camera>:8000/snapshots/cam-gate-a/20260708_000500.jpg"
}
```

### Field bắt buộc

- `camera_id`
- `timestamp`
- `image_url`

### Field khuyến nghị

- `request_id`
- `location`
- `motion_detected`
- `motion_score`

## 4. Quy ước ảnh

- `image_url` phải truy cập được từ phía A4.
- Ảnh là snapshot một thời điểm, không gửi video stream liên tục.
- A4 có thể tải ảnh từ URL này để chạy model hoặc mock.

## 5. Cách xử lý phía Camera Stream

- Camera Stream chỉ gửi khi:
  - phát hiện motion
  - hoặc được trigger thủ công để test
- Nếu `motion_detected = false`, Camera Stream không cần gọi A4.
- Camera Stream không gửi toàn bộ luồng video.

## 6. Response contract

Khi xử lý thành công, A4 trả response JSON:

```json
{
  "detection_id": "DET-1773BF5E",
  "camera_id": "cam-gate-a",
  "label": "person",
  "confidence": 0.92,
  "risk_level": "warning"
}
```

### Field mong đợi

- `detection_id`
- `camera_id`
- `label`
- `confidence`
- `risk_level`

### Gợi ý mức rủi ro

- `info`
- `warning`
- `high`
- `critical`

## 7. Mã trạng thái

- `200` hoặc `201`: xử lý thành công
- `400`: payload thiếu field hoặc sai kiểu dữ liệu
- `401` / `403`: sai auth
- `500`: lỗi nội bộ

## 8. Authentication

Nếu A4 yêu cầu auth, nhóm Camera Stream gửi header:

```http
Authorization: Bearer smart-campus-secret-token
```

Nếu A4 đổi token, hai nhóm phải chốt lại cùng một giá trị trước khi demo.

## 9. Ví dụ gọi từ PowerShell

```powershell
$trigger = Invoke-RestMethod http://127.0.0.1:8000/camera/trigger

$body = @{
  request_id = $trigger.request_id
  camera_id = $trigger.camera_id
  timestamp = $trigger.timestamp
  location = $trigger.location
  motion_detected = $true
  motion_score = 0.82
  image_url = $trigger.snapshot_url
} | ConvertTo-Json -Depth 4

Invoke-RestMethod `
  -Method Post `
  -Uri "http://<ip-a4>:8000/api/v1/vision/detect" `
  -ContentType "application/json" `
  -Headers @{ Authorization = "Bearer smart-campus-secret-token" } `
  -Body $body
```

## 10. Trách nhiệm mỗi bên

### Nhóm Camera Stream

- chụp snapshot khi có motion
- tạo `snapshot_url` public
- gửi request đúng schema
- retry nếu A4 lỗi tạm thời

### Nhóm A4 AI Vision

- nhận và validate payload
- tải ảnh từ `image_url`
- trả kết quả detect có cấu trúc
- không yêu cầu upload file nếu đã chốt contract `image_url`

## 11. Chốt hợp đồng

Hai nhóm thống nhất contract cuối cùng là:

- `POST /api/v1/vision/detect`
- JSON payload
- dùng `image_url`
- response trả kết quả detect đồng bộ

Nếu A4 đang nhận `file` thay vì `image_url`, đó là contract khác và phải sửa lại trước khi demo.
