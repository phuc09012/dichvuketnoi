# Nghiệp vụ camera - Team Camera

## Mục tiêu

Module camera của nhóm mình chịu trách nhiệm:

- Lấy hình từ camera live
- Phát hiện chuyển động
- Tạo snapshot khi có sự kiện
- Gửi dữ liệu sang nhóm AI Vision / A4 để xác nhận
- Phát bản tin sự kiện lên MQTT cho Core Business nếu cần
- Cung cấp dashboard web để demo và kiểm tra nhanh

## Luồng nghiệp vụ chính

### 1. Camera live

- Dashboard hiển thị stream live từ camera thật.
- Nếu stream chậm hoặc lỗi, hệ thống tự fallback sang snapshot gần nhất để trang vẫn dùng được.

### 2. Phát hiện chuyển động

- Hệ thống quét motion theo chu kỳ.
- Motion được tính từ độ khác nhau giữa các frame / snapshot.
- Nếu motion score vượt ngưỡng `MOTION_THRESHOLD`, hệ thống xem là có chuyển động.
- Hiện tại ngưỡng được đặt thấp để dễ bắt sự kiện hơn trong demo.

### 3. Gửi sang AI Vision / A4

- Khi có motion, hệ thống sẽ gửi ảnh và thông tin camera sang nhóm AI Vision / A4.
- Dashboard cũng có nút gửi thủ công để test nhanh.
- Nếu A4 phản hồi chậm, dashboard báo timeout rõ ràng.

### 4. MQTT event

- Khi có motion, camera có thể publish event lên MQTT topic:
  - `smart-campus/events/camera`
- Payload dùng cho Core Business có các trường chính:
  - `event_type`
  - `source_service`
  - `request_id`
  - `camera_id`
  - `timestamp`
  - `location`
  - `motion_detected`
  - `motion_score`
  - `snapshot_url`

## Endpoint nội bộ

### Health

- `GET /health`

### Runtime

- `GET /api/runtime`

### Snapshot

- `GET /api/snapshots`

### Camera

- `GET /camera/live`
- `GET /camera/check`
- `GET /camera/motion`
- `GET /camera/trigger`

### Gửi sang A4

- `POST /api/a4/detect`

## Tham số cấu hình quan trọng

- `CAMERA_STREAM_URL`
  - Link stream thật của camera
- `MOTION_THRESHOLD`
  - Ngưỡng phát hiện motion
- `PUBLIC_BASE_URL`
  - Base URL public để nhóm khác truy cập snapshot
- `A4_SERVICE_URL`
  - Địa chỉ nhóm AI Vision / A4
- `A4_DETECT_PATH`
  - Route nhận ảnh của nhóm A4
- `MQTT_BROKER_HOST`, `MQTT_BROKER_PORT`
  - Broker dùng chung cho lớp

## Quy ước gửi ảnh

- Ưu tiên gửi `snapshot_url` nếu có.
- Nếu không có snapshot sẵn thì mới chụp lại từ camera.
- Ảnh gửi sang nhóm AI cần truy cập được từ trong Docker network hoặc từ môi trường của nhóm nhận.

## Trạng thái trên dashboard

- `Phát hiện chuyển động`
- `Đang gửi đến A4`
- `Gửi thành công đến AI Vision`
- `Không phát hiện chuyển động`
- `Request timeout`

## Ghi chú thực tế

- Hệ thống đang ưu tiên demo dễ dùng hơn độ chính xác tuyệt đối.
- Motion có thể báo giả nhiều hơn để AI Vision xác nhận phía sau.
- Nếu camera ít thay đổi hình, motion score có thể thấp dù trong khung có người.
- Dashboard đã được chỉnh để khởi động nhanh hơn, nạp dữ liệu nền sau.

## Mục tiêu bàn giao

- Team Camera cung cấp dữ liệu sự kiện camera ổn định
- Team AI Vision xác nhận người / bất thường từ ảnh
- Team Core Business nhận event qua MQTT hoặc luồng nghiệp vụ chung

