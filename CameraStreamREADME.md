# Camera Stream Service - Yêu cầu xử lý trước khi gửi frame sang AI Vision

## 1. Mục tiêu của nhóm Camera

Nhóm **Camera Stream** xây dựng service trung gian nhận luồng video từ camera Pi, xử lý frame đầu vào, phát hiện điều kiện cần gọi AI Vision, sau đó gửi frame/snapshot phù hợp sang nhóm **AI Vision**.

Luồng tổng thể:

```text
Pi Camera Stream
→ Camera Stream Service
→ Kiểm tra stream
→ Lấy frame
→ Tiền xử lý frame
→ Phát hiện motion hoặc trigger condition
→ Gửi snapshot/frame sang AI Vision
→ Nhận kết quả detect
→ Gửi kết quả sang Core Business nếu cần
```

Nhóm Camera **không gửi toàn bộ video liên tục sang AI Vision**. Nhóm phải chọn frame phù hợp, tránh gây quá tải cho service AI.

---

## 2. Camera stream đầu vào

Link camera do giảng viên cung cấp, dùng chung cho cả lớp:

```text
URL stream:
https://camera.labaiotdnu.app/video?key=matkhau_cua_ban
```

Đây là luồng video dạng MJPEG stream. Key `matkhau_cua_ban` đã embed sẵn trong URL — sinh viên dùng nguyên URL này, **không cần xin key riêng** cho từng nhóm.

Nhóm Camera có thể dùng:

```text
OpenCV VideoCapture
requests stream
hoặc thư viện xử lý video phù hợp
```

> **Lưu ý bảo mật:** URL public cho lớp học, không phải bí mật. Tuy vậy khi nộp bài vẫn nên đẩy URL vào `.env` để code không lệ thuộc vào URL cứng — sau này đổi camera khác cũng dễ.

---

## 3. Nguồn sinh data

Camera stream do **giảng viên vận hành, chạy liên tục 24/7**.

```text
- Sinh viên KHÔNG cần tự cài Pi hay setup camera.
- Sinh viên chỉ connect tới URL stream, đọc frame và xử lý tiếp.
- Nếu không đọc được frame trong 1-2 phút, kiểm tra:
  1. Kết nối Internet.
  2. URL đã đúng (gồm cả phần ?key=matkhau_cua_ban).
  3. Thư viện xử lý MJPEG (OpenCV/requests) đã cài đúng.
  4. Nếu vẫn không kết nối được, liên hệ giảng viên kiểm tra stream.
```

Trong stream sẽ có các tình huống: không có chuyển động, có người đi qua, có vật thể lạ. Sinh viên cần tự phát hiện motion để quyết định khi nào gọi AI Vision.

---

## 4. Nhiệm vụ chính của nhóm Camera

Nhóm Camera cần thực hiện các nhiệm vụ sau:

```text
1. Kết nối được tới camera stream.
2. Đọc được frame từ stream.
3. Kiểm tra frame hợp lệ.
4. Không gửi mọi frame sang AI Vision.
5. Phát hiện điều kiện cần trigger AI Vision.
6. Tiền xử lý frame trước khi gửi.
7. Đóng gói request đúng schema đã thống nhất với nhóm AI Vision.
8. Xử lý lỗi khi AI Vision timeout hoặc trả lỗi.
9. Ghi log toàn bộ quá trình xử lý.
```

---

## 5. Dữ liệu nhóm Camera nhận được

Camera stream trả về chuỗi frame ảnh liên tục.

Mỗi frame đọc được có thể hiểu là:

```text
frame_id
timestamp
camera_id
location
image/frame
width
height
```

Nhóm Camera cần tự gắn metadata cho frame vì camera stream gốc chỉ cung cấp hình ảnh.

Ví dụ metadata nội bộ:

```json
{
  "frame_id": "frame-001",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:10+07:00",
  "location": "Main Gate A",
  "width": 640,
  "height": 480
}
```

---

## 6. Những việc phải làm trước khi gửi frame sang AI Vision

### 6.1. Kiểm tra kết nối stream

Trước khi xử lý, service phải kiểm tra:

```text
- URL camera có truy cập được không
- Có đọc được frame không
- Frame có bị rỗng không
- Kích thước frame có hợp lệ không
- Stream có bị timeout không
```

Nếu không đọc được camera, service phải log lỗi rõ ràng:

```json
{
  "error": "camera_stream_unavailable",
  "camera_id": "cam-gate-a",
  "message": "Cannot read frame from camera stream"
}
```

---

### 6.2. Gắn metadata cho frame

Mỗi frame được chọn để xử lý cần có metadata:

```text
camera_id
frame_id
timestamp
location
frame_width
frame_height
```

Ví dụ:

```json
{
  "camera_id": "cam-gate-a",
  "frame_id": "frame-20260607-143010",
  "timestamp": "2026-06-07T14:30:10+07:00",
  "location": "Main Gate A",
  "frame_width": 640,
  "frame_height": 480
}
```

---

### 6.3. Giảm tần suất xử lý frame

Không gửi 30 frame/giây sang AI Vision.

Gợi ý:

```text
- Chỉ lấy 1 frame mỗi 1–3 giây
- Hoặc chỉ gửi khi phát hiện motion
- Hoặc dùng cooldown 5–10 giây sau mỗi lần trigger AI
```

Ví dụ rule:

```text
Nếu không có motion:
  không gửi sang AI Vision

Nếu có motion:
  gửi 1 snapshot sang AI Vision
  chờ cooldown 5 giây trước khi gửi tiếp
```

---

### 6.4. Phát hiện motion trước khi gọi AI Vision

Nhóm Camera nên xử lý đơn giản bằng frame difference:

```text
1. Chuyển frame hiện tại sang grayscale.
2. So sánh với frame trước đó.
3. Tính độ khác biệt.
4. Nếu khác biệt vượt ngưỡng thì coi là có motion.
```

Gợi ý output nội bộ:

```json
{
  "motion_detected": true,
  "motion_score": 0.82,
  "motion_threshold": 0.50
}
```

Nếu `motion_detected = false`, không cần gọi AI Vision.

---

### 6.5. Tiền xử lý frame

Trước khi gửi sang AI Vision, nhóm Camera cần:

```text
- Resize frame về kích thước hợp lý, ví dụ 640x480 hoặc 416x416
- Encode ảnh sang JPEG hoặc base64
- Kiểm tra dung lượng ảnh
- Không gửi ảnh quá lớn
- Không gửi frame bị lỗi, đen toàn bộ hoặc rỗng
```

Gợi ý:

```text
JPEG quality: 70–85
Max width: 640 hoặc 800
```

---

### 6.6. Tạo snapshot

Khi có motion, nhóm Camera nên tạo snapshot đại diện.

Tên file gợi ý:

```text
snapshots/cam-gate-a/20260607_143010.jpg
```

Metadata snapshot:

```json
{
  "snapshot_id": "snapshot-001",
  "camera_id": "cam-gate-a",
  "snapshot_path": "snapshots/cam-gate-a/20260607_143010.jpg",
  "timestamp": "2026-06-07T14:30:10+07:00"
}
```

---

### 6.7. Đóng gói request gửi sang AI Vision

Nhóm Camera cần thống nhất contract với nhóm AI Vision.

Có thể chọn một trong hai cách:

```text
Cách 1: Gửi image_base64 trực tiếp
Cách 2: Gửi snapshot_url hoặc snapshot_path
```

#### Cách 1: Gửi image_base64

```json
{
  "request_id": "vision-request-001",
  "event_type": "camera.motion.triggered",
  "source_service": "team-camera",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:10+07:00",
  "location": "Main Gate A",
  "motion_detected": true,
  "motion_score": 0.82,
  "image_format": "jpg",
  "image_base64": "BASE64_IMAGE_CONTENT"
}
```

#### Cách 2: Gửi snapshot URL/path

```json
{
  "request_id": "vision-request-001",
  "event_type": "camera.motion.triggered",
  "source_service": "team-camera",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:10+07:00",
  "location": "Main Gate A",
  "motion_detected": true,
  "motion_score": 0.82,
  "snapshot_url": "http://team-camera/snapshots/cam-gate-a/20260607_143010.jpg"
}
```

Khuyến nghị: nếu chạy Docker Compose nội bộ, nên dùng `snapshot_url` hoặc `snapshot_path` để tránh payload quá lớn.

---

## 7. API gợi ý giữa Camera và AI Vision

Nhóm Camera gọi AI Vision qua REST API:

```http
POST /api/v1/detect
```

Request:

```json
{
  "request_id": "vision-request-001",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:10+07:00",
  "location": "Main Gate A",
  "motion_score": 0.82,
  "snapshot_url": "http://team-camera/snapshots/cam-gate-a/20260607_143010.jpg"
}
```

Response mong đợi từ AI Vision:

```json
{
  "request_id": "vision-request-001",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:11+07:00",
  "detections": [
    {
      "label": "person",
      "confidence": 0.92,
      "bbox": {
        "x": 120,
        "y": 80,
        "width": 210,
        "height": 430
      }
    }
  ],
  "unknown_person": true,
  "risk_level": "warning"
}
```

---

## 8. Xử lý lỗi khi gọi AI Vision

Nhóm Camera phải xử lý các lỗi sau:

| Lỗi | Cách xử lý |
|---|---|
| AI Vision timeout | Log lỗi, retry tối đa 2 lần |
| AI Vision trả 500 | Không crash service, ghi log |
| AI Vision không reachable | Ghi trạng thái `ai_unavailable` |
| Payload quá lớn | Resize/compress lại frame |
| Snapshot không tồn tại | Không gọi AI, log `snapshot_missing` |

Ví dụ log lỗi:

```json
{
  "event_type": "camera.ai_call_failed",
  "camera_id": "cam-gate-a",
  "request_id": "vision-request-001",
  "error": "ai_timeout",
  "retry_count": 2
}
```

---

## 9. Dữ liệu gửi sang Core Business sau khi có kết quả AI

Sau khi AI Vision trả kết quả, nhóm Camera hoặc nhóm AI Vision có thể gửi event sang Core Business tùy contract liên nhóm.

Topic gợi ý nếu dùng MQTT:

```text
smart-campus/events/camera
```

Payload mẫu:

```json
{
  "event_id": "camera-event-001",
  "event_type": "camera.vision.processed",
  "source_service": "team-camera",
  "camera_id": "cam-gate-a",
  "timestamp": "2026-06-07T14:30:12+07:00",
  "location": "Main Gate A",
  "motion_detected": true,
  "motion_score": 0.82,
  "detections": [
    {
      "label": "person",
      "confidence": 0.92
    }
  ],
  "unknown_person": true,
  "risk_level": "warning"
}
```

---

## 10. Yêu cầu không được làm

```text
- Không gửi toàn bộ video stream sang AI Vision.
- Không gọi AI Vision liên tục 30 lần/giây.
- Không bỏ qua bước kiểm tra frame rỗng.
- Không hard-code URL/password trong repo public.
- Không để service crash khi camera mất kết nối.
- Không gửi field thiếu timestamp, camera_id hoặc request_id.
```
