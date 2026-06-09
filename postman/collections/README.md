# Postman Collections

Collection `FIT4110_lab05_ai_vision_compose.postman_collection.json` kiểm thử stack Docker Compose của Lab 05 cho AI Vision:

- API `/health`
- thông tin model `/vision/models/info`
- tạo/lấy detection với bearer token
- auth negative cases
- validation negative cases

Chạy bằng:

```bash
npm run test:compose
```

Environment sử dụng `postman/environments/FIT4110_lab05_ai_vision_local.postman_environment.json` với `baseUrl=http://localhost:8000`.
