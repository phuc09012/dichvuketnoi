# A2 1-Minute Checklist

## Trước khi lên lớp

- [ ] Có `peers.json` từ `peers.example.json`
- [ ] Điền IP thật của các nhóm khác vào `peers.json`
- [ ] Kiểm tra `CAMERA_STREAM_URL` trong `.env`
- [ ] Chạy thử `.\check_peers.ps1`
- [ ] Chạy thử `.\start_demo.ps1`

## Khi lên lớp

- [ ] Bật hotspot
- [ ] Xác nhận máy đang có IP `172.20.10.x`
- [ ] Chạy lại `.\check_peers.ps1`
- [ ] Mở service ở `http://<ip-cua-ban>:8000`
- [ ] Test với nhóm khác qua `GET /health`
- [ ] Nếu lỗi, kiểm tra port, firewall, và `.env`

## Endpoint cần nhớ

- `GET /health`
- `HEAD /health`
- `GET /camera/check`
- `GET /camera/motion`
- `GET /camera/trigger`
- `POST /detect`
