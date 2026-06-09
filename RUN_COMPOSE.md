# RUN_COMPOSE.md – Hướng dẫn chạy Lab 05

Tài liệu này hướng dẫn người khác clone repo sạch và chạy lại stack Compose của Lab 05.

---

## 1. Clone repo

```bash
git clone <repo-url>
cd FIT4110_lab05_docker_compose_readiness
```

---

## 2. Cài dependencies cho Newman/Prism/Spectral (tuỳ chọn)

```bash
npm install
```

---

## 3. Build & chạy stack Docker Compose

```bash
# Copy .env.example sang .env và chỉnh sửa nếu cần
cp .env.example .env

# Build images (nếu chưa có) và khởi động các container trong nền
docker compose up -d --build --wait
```

Lệnh trên sẽ tạo các container:

- `fit4110-vision-db-lab05` (PostgreSQL)
- `fit4110-vision-model-lab05` (model runtime mẫu chạy port 9000)
- `fit4110-ai-vision-lab05` (AI Vision API FastAPI trên port 8000)

API và AI image được tag theo quy ước:

```text
ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-vision-api:v0.1.0-team-vision
ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/vision-model:v0.1.0-team-vision
```

Theo dõi log:

```bash
docker compose logs -f
```

Sau vài giây, kiểm tra health của mỗi service:

```bash
# API
curl http://localhost:8000/health

# Model service
curl http://localhost:9000/health

# DB readiness
docker exec -it fit4110-vision-db-lab05 pg_isready -U $POSTGRES_USER
```

Nếu máy đang có PostgreSQL local chiếm port `5432`, đổi `POSTGRES_PUBLISHED_PORT` trong `.env` sang port trống, ví dụ `15432`. Port nội bộ container vẫn là `5432`.

Bạn cũng có thể truy cập endpoint `/predict` của model service để xem kết quả mẫu:

```bash
curl -X POST http://localhost:9000/predict \
  -H "Content-Type: application/json" \
  -d '{"requestId":"REQ-CAM-20260512-0001","cameraId":"CAM-ER-01","motionLevel":0.92}'
```

---

## 4. Chạy Newman test trên stack Compose (tuỳ chọn)

```bash
npm run test:compose
```

Report sinh tại:

```text
reports/newman-lab05-compose.xml
reports/newman-lab05-compose.html
```

Evidence local bổ sung được lưu trong `reports/LAB05_EVIDENCE.md`.

---

## 5. Dừng stack

Khi không cần nữa, dừng và xoá các container bằng:

```bash
docker compose down
```

Nếu muốn xoá volume dữ liệu của DB, thêm tuỳ chọn `-v`:

```bash
docker compose down -v
```

---

## 6. Lệnh nhanh

Bạn có thể dùng Makefile:

```bash
make compose-up
make compose-down
make logs
```

---

## 7. Mẹo gỡ lỗi

- Sử dụng `docker compose ps` để xem trạng thái container.
- Nếu API trả lỗi kết nối DB, hãy kiểm tra biến môi trường `POSTGRES_*` trong `.env` và đảm bảo DB đã sẵn sàng (`pg_isready`).
- Nếu API không gọi được model service, kiểm tra `MODEL_SERVICE_URL=http://vision-model:9000` trong `.env` và network `team-internal`.
- Nếu model service cần tải mô hình lớn, tăng `start_period` của healthcheck trong `docker-compose.yml`.
