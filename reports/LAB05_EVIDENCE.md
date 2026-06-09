# Lab 05 AI Vision Evidence

Evidence collected on 2026-06-09 while running the AI Vision Docker Compose stack locally.

## Commands verified

- `docker compose config --quiet`
- `docker compose up -d --build --wait`
- `curl http://localhost:8000/health`
- `curl http://localhost:9000/health`
- `curl -X POST http://localhost:9000/predict`
- `docker compose exec -T db pg_isready -U vision`
- `docker compose exec -T api python -c "... requests.get(os.environ['MODEL_SERVICE_URL'] + '/health') ..."`
- `npm run lint:openapi`
- `npm run test:compose`

## Generated files

- `reports/compose-ps.log`
- `reports/api-health.json`
- `reports/model-health.json`
- `reports/model-predict.json`
- `reports/db-ready.log`
- `reports/api-to-model.log`
- `reports/db-detections.log`
- `reports/image-tags.log`
- `reports/compose-tail.log`
- `reports/newman-lab05-compose.xml`
- `reports/newman-lab05-compose.html`

## Notes

- `POSTGRES_PUBLISHED_PORT` was set to `15432` in local `.env` because port `5432` was already used by a local PostgreSQL process.
- The committed `.env.example` keeps `POSTGRES_PUBLISHED_PORT=5432` as required by the lab checklist.
- Compose builds versioned local image tags:
  - `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-vision-api:v0.1.0-team-vision`
  - `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/vision-model:v0.1.0-team-vision`
- Newman pass: 8 requests, 14 assertions, 0 failures.
- `.github/workflows/lab05-check.yml` pushes those tags to GHCR on `main` pushes after Compose and Newman checks pass.
