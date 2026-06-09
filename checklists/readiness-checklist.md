# Readiness Checklist – Lab 05

Đây là danh sách kiểm tra (checklist) để đảm bảo stack Docker Compose của bạn đã sẵn sàng trước khi gửi bài. Hãy tick vào mỗi mục sau khi hoàn thành.

- [x] **Database ready:** container DB đã chạy và phản hồi `pg_isready`. Kiểm tra bằng `docker exec -it fit4110-db-lab05 pg_isready -U $POSTGRES_USER`.
- [x] **AI service ready:** container AI service trả về `200` cho endpoint `/health` và `/predict` hoạt động.
- [x] **API ready:** container API trả `200` cho `/health` và có thể tạo/lấy readings khi token hợp lệ.
- [x] **Environment variables:** `.env` đã được thiết lập đúng (APP_PORT, POSTGRES_USER, AUTH_TOKEN,…). Không sử dụng secret thật; lưu secret vào `.env` cục bộ, commit `.env.example`.
- [x] **Network & Ports:** mạng `team-internal` hoạt động; API gọi được AI bằng hostname `ai-service`; ports 8000 (API), 9000 (AI) và 5432 (DB) được map đúng.
- [x] **Image tags:** bạn đã build image với tag `v0.1.0-<team>` và push lên registry (ghcr.io hoặc Docker Hub). Xác nhận rằng tag xuất hiện trong registry.

Ghi chú thêm những vấn đề gặp phải hoặc điều chỉnh tại đây:

```
- Evidence lưu trong `reports/LAB05_EVIDENCE.md` và các file log/report trong `reports/`.
- Newman pass: 11 requests, 19 assertions, 0 failures.
- Image tags: `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/iot-ingestion:v0.1.0-team-iot` và `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-service:v0.1.0-team-iot`.
- GitHub Actions workflow `.github/workflows/lab05-check.yml` push image tags lên GHCR sau khi Compose/Newman pass trên `main`.
- Khi test local ngày 2026-06-09, DB publish port dùng `15432` vì máy đang có PostgreSQL chiếm `5432`; `.env.example` vẫn để mặc định `5432`.
```
