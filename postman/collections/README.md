# Postman Collections

Collection `FIT4110_lab05_iot_compose.postman_collection.json` kiểm thử stack Docker Compose của Lab 05:

- API `/health`
- tạo/lấy readings với bearer token
- auth negative cases
- validation negative cases
- boundary temperature cases

Chạy bằng:

```bash
npm run test:compose
```

Environment sử dụng `postman/environments/FIT4110_lab05_local.postman_environment.json` với `baseUrl=http://localhost:8000`.
