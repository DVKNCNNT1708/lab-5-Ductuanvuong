.PHONY: install lint build run compose-up compose-down logs test-compose

# Install Node dependencies for Prism/Spectral/Newman
install:
	npm install

# Lint OpenAPI contracts with Spectral
lint:
	npx spectral lint contracts/*.yaml

# Build Docker image for API only
build:
	docker build -t ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-vision-api:v0.1.0-team-vision .

# Run API container standalone (not via compose)
run:
	docker run --rm --name fit4110-ai-vision-lab05 -p 8000:8000 --env-file .env.example ghcr.io/dvkncnnt1708/lab-5-ductuanvuong/ai-vision-api:v0.1.0-team-vision

# Compose commands
compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

logs:
	docker compose logs -f

# Run Newman tests on compose stack
test-compose:
	npm run test:compose
