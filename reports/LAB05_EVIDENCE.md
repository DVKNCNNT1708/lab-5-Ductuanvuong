# Lab 05 Evidence

Evidence collected on 2026-06-09 while running the Docker Compose stack locally.

## Commands verified

- `docker compose config --quiet`
- `docker compose up -d --build --wait`
- `curl http://localhost:8000/health`
- `curl http://localhost:9000/health`
- `curl -X POST http://localhost:9000/predict`
- `docker compose exec -T db pg_isready -U lab05`
- `docker compose exec -T api python -c "... requests.get(os.environ['AI_SERVICE_URL'] + '/health') ..."`
- `npm run test:compose`

## Generated files

- `reports/compose-ps.log`
- `reports/api-health.json`
- `reports/ai-health.json`
- `reports/ai-predict.json`
- `reports/db-ready.log`
- `reports/api-to-ai.log`
- `reports/db-readings.log`
- `reports/image-tags.log`
- `reports/compose-tail.log`
- `reports/newman-lab05-compose.xml`
- `reports/newman-lab05-compose.html`

## Notes

- `POSTGRES_PUBLISHED_PORT` was set to `15432` in local `.env` because port `5432` was already used by a local PostgreSQL process.
- The committed `.env.example` keeps `POSTGRES_PUBLISHED_PORT=5432` as required by the lab checklist.
- Compose builds versioned local image tags:
  - `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/iot-ingestion:v0.1.0-team-iot`
  - `ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-service:v0.1.0-team-iot`
- `.github/workflows/lab05-check.yml` pushes those tags to GHCR on `main` pushes after Compose and Newman checks pass.
