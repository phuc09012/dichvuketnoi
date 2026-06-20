# README - A2 Camera Stream Demo Day

## 1. Vai Trò Của Nhóm

Nhóm A2 phụ trách **Camera Stream Service** trong hệ thống Smart Campus.

- Nhận luồng camera từ nguồn cloud.
- Chụp snapshot từ frame hiện tại.
- Phát hiện chuyển động cơ bản bằng cách so sánh 2 frame liên tiếp.
- Tạo payload để gửi sang nhóm AI Vision phía sau.
- Cung cấp endpoint để nhóm khác kiểm tra và tích hợp qua mạng LAN/hotspot.

## 2. Input

Service A2 nhận các loại input sau:

- Luồng camera MJPEG từ URL của trường.
- Thông tin cấu hình như `camera_id`, `camera_location`, `timestamp`.
- Khi gọi sang nhóm khác, payload có thể gồm:
  - `image_url`
  - `timestamp`
  - `request_id`
  - `motion_detected`
  - `motion_score`

## 3. Xử Lý Nghiệp Vụ

Luồng xử lý của A2:

1. Đọc frame từ camera stream.
2. Kiểm tra camera còn hoạt động hay không.
3. Nếu có 2 frame, tính `motion_score`.
4. Lưu snapshot vào thư mục `snapshots/`.
5. Tạo `snapshot_url` để nhóm khác xem được ảnh.
6. Gửi request sang nhóm AI Vision qua REST API.
7. Dùng timeout và header xác thực khi gọi dịch vụ đối tác.

## 4. Output

Service A2 trả ra các output chính:

- `GET /health`
- `GET /camera/check`
- `GET /camera/motion`
- `GET /camera/trigger`
- `POST /detect`

Các field output quan trọng:

- `snapshot_url`
- `motion_detected`
- `motion_score`
- `detection_id`
- `label`
- `confidence`

## 5. Output Gửi Cho Ai

Nhóm A2 gửi dữ liệu sang **nhóm A4 - AI Vision**.

- Endpoint: `POST /api/v1/vision/detect`
- Header xác thực:
  - `Authorization: Bearer smart-campus-secret-token`
- Trước khi gửi, kiểm tra:
  - `GET /health`

Hiện tại contract hoạt động tốt nhất là gửi theo `image_url`, tức là dùng `snapshot_url` public của A2.

## 6. Minh Chứng Demo

Khi demo buổi 6, có thể dùng các minh chứng sau:

- `docker compose ps`
- `GET /health` trả `200 OK`
- `GET /camera/trigger` trả được snapshot và payload
- Log request gửi sang A4 thành công
- Screenshot ảnh mở được từ `snapshot_url`
- Kết quả response từ A4 với `label: person`

## 7. Trả Lời Nhanh Theo Rubric

### A. Nghiệp vụ rõ ràng

Nhóm A2 làm service camera stream, nhận ảnh từ camera cloud, chụp snapshot, phát hiện chuyển động và chuyển dữ liệu sang nhóm AI Vision.

### B. Service chạy ổn bằng Docker Compose

Repo có:

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- non-root user trong container
- healthcheck cho API

### C. Endpoint `/health` hoạt động

Service hỗ trợ:

- `GET /health`
- `HEAD /health`

Nhóm khác chỉ cần gọi `http://<ip-hotspot>:8000/health` để kiểm tra service còn sống.

### D. Tích hợp đúng contract với nhóm khác

Nhóm A2 đã chuẩn bị:

- check peer theo IP hotspot
- script `check_peers.ps1`
- cấu hình peer qua `PEER_ENDPOINTS`
- auth header cho A4

### E. Payload / request đúng schema

Service đã có schema validation cho request camera và request gửi sang AI Vision.

- Thiếu field sẽ bị báo lỗi rõ ràng.
- Sai kiểu dữ liệu sẽ trả `400`.
- Payload đã dùng đúng field mà nhóm A4 chấp nhận.

### F. Có xử lý lỗi / timeout

Đã có:

- timeout khi đọc camera stream
- timeout khi gọi peer
- thông báo lỗi rõ ràng
- handler tránh crash khi payload không hợp lệ

### G. Minh chứng đầy đủ

Nên chuẩn bị:

- screenshot `GET /health`
- screenshot `GET /camera/trigger`
- log gọi sang A4 thành công
- screenshot ảnh mở từ `snapshot_url`
- file báo cáo trong `reports/`

### H. Trình bày demo rõ ràng

Kịch bản nói ngắn gọn:

1. Service làm gì.
2. Input lấy từ đâu.
3. Xử lý như thế nào.
4. Output là gì.
5. Gửi cho nhóm nào và bằng cách nào.

## 8. Luồng Demo Thực Tế

### Trước khi lên lớp

1. Copy `.env.example` thành `.env`.
2. Cập nhật IP thật của nhóm đối tác.
3. Kiểm tra camera stream.
4. Chạy thử `.\check_peers.ps1`.

### Khi lên lớp

1. Bật hotspot.
2. Xác nhận máy mình có IP LAN hợp lệ.
3. Chạy `.\start_demo.ps1`.
4. Cho nhóm khác gọi `GET /health`.
5. Dùng `GET /camera/trigger` để lấy ảnh và gửi sang A4.

## 9. Endpoint Quan Trọng

- `GET /health`
- `HEAD /health`
- `GET /camera/check`
- `GET /camera/motion`
- `GET /camera/trigger`
- `POST /detect`
- `GET /peers`
- `POST /peer-check`

## 10. Quy Tắc Kết Nối

- Không dùng tên service Docker để gọi chéo giữa các máy khác nhau.
- Dùng **IP hotspot + port**.
- Không hardcode IP trong source code.
- Lưu IP trong `.env` hoặc `peers.json`.
- Dùng timeout 3-5 giây khi gọi peer.

## 11. Camera Stream Của Trường

URL camera đang dùng:

```text
https://camera.labaiotdnu.app/video?key=matkhau_cua_ban
```

Ghi chú:

- URL này đã probe được.
- Service đọc được frame thật.
- Snapshot được lưu trong `snapshots/<camera_id>/`.

## 12. Kết Luận Ngắn

Nhóm A2 làm service Camera Stream. Service nhận luồng camera từ cloud, đọc frame, kiểm tra kết nối, phát hiện motion cơ bản, lưu snapshot và gửi ảnh sang nhóm A4 qua API. Khi demo, chỉ cần chạy service, mở `/health`, lấy `snapshot_url` và gọi sang IP của nhóm A4 là có thể chứng minh tích hợp thành công.
