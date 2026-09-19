.PHONY: install install-backend install-frontend \
        dev backend frontend \
        kill kill-backend kill-frontend \
        test test-backend test-integration \
        postgres docker-build docker-run \
        up down \
        clean

BACKEND_PORT := 8091
FRONTEND_PORT := 5173

# --- Docker ---------------------------------------------------------------
IMAGE := linewarmer
APP_PORT := 8100
NETWORK := linewarmer-net

PG_CONTAINER := interview-canvas-db
PG_VOLUME := interview-canvas-pgdata
PG_IMAGE := postgres:16-alpine
PG_PORT := 5432
PG_USER := sdip
PG_PASSWORD := sdip
PG_DB := sdip

# URL used by the app container, which reaches Postgres by container name over
# $(NETWORK). From the host (e.g. `make backend`) use localhost:$(PG_PORT)
# instead. The +psycopg suffix is required — a plain postgresql:// URL makes
# SQLAlchemy look for psycopg2, which isn't installed.
PG_URL := postgresql+psycopg://$(PG_USER):$(PG_PASSWORD)@$(PG_CONTAINER):$(PG_PORT)/$(PG_DB)

# docker-compose.yaml defaults every one of these to the same value, but passing
# them keeps the settings above the single source of truth for both paths.
COMPOSE_ENV := APP_PORT=$(APP_PORT) \
               PG_PORT=$(PG_PORT) \
               POSTGRES_USER=$(PG_USER) \
               POSTGRES_PASSWORD=$(PG_PASSWORD) \
               POSTGRES_DB=$(PG_DB)

install: install-backend install-frontend

install-backend:
	cd backend && uv sync

install-frontend:
	cd frontend && npm i

# Run backend (reload) and frontend dev server together; Ctrl+C stops both.
dev:
	$(MAKE) -j2 backend frontend

backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8091

frontend:
	cd frontend && npm run dev

# Free up the dev ports if a previous run was left dangling (e.g. after a
# crash or a terminal closed without Ctrl+C).
kill: kill-backend kill-frontend

kill-backend:
	-lsof -ti tcp:$(BACKEND_PORT) | xargs kill -9

kill-frontend:
	-lsof -ti tcp:$(FRONTEND_PORT) | xargs kill -9

test: test-backend

test-backend:
	cd backend && uv run pytest

# Integration tests: build the image, bring the compose stack up, and drive it
# over HTTP/WebSockets on localhost:$(APP_PORT). Slow (a cold `npm ci` + Vite
# build) and excluded from `make test` for that reason.
#
# Runs under an overlay that renames the containers and the data volume, so the
# suite's teardown (`down -v`) cannot touch $(PG_VOLUME). The app port is not
# remapped, so stop the dev stack (`make down`) first or pass APP_PORT=<other>.
test-integration:
	uv run --project backend pytest integration -v

# Start Postgres, reusing the existing container and volume if they're already
# there so data survives. Idempotent: safe to run when it's already up.
postgres:
	@docker network create $(NETWORK) >/dev/null 2>&1 || true
	@if [ -n "$$(docker ps -aq -f name='^$(PG_CONTAINER)$$')" ]; then \
		docker start $(PG_CONTAINER); \
	else \
		docker run -d \
			--name $(PG_CONTAINER) \
			--network $(NETWORK) \
			-e POSTGRES_USER=$(PG_USER) \
			-e POSTGRES_PASSWORD=$(PG_PASSWORD) \
			-e POSTGRES_DB=$(PG_DB) \
			-p $(PG_PORT):5432 \
			-v $(PG_VOLUME):/var/lib/postgresql/data \
			$(PG_IMAGE); \
	fi
	@# No-op when the container is already attached (e.g. created before the
	@# network existed), so this stays safe to re-run.
	-@docker network connect $(NETWORK) $(PG_CONTAINER) 2>/dev/null || true
	@echo "Postgres ready on localhost:$(PG_PORT) ($(PG_USER)/$(PG_DB))"

# Build the single-image app: frontend bundle + FastAPI backend that serves it.
docker-build:
	docker build -t $(IMAGE) .

# Run the built image against Postgres; brings the database up first.
docker-run: postgres
	docker run --rm \
		--network $(NETWORK) \
		-p $(APP_PORT):8000 \
		-e DATABASE_URL="$(PG_URL)" \
		$(IMAGE)

# Bring up Postgres + app together, rebuilding the app image first. Detached,
# so the shell comes back; use `make down` to stop it.
#
# Mutually exclusive with `make postgres` / `make docker-run`: both paths use
# the container name $(PG_CONTAINER) and host port $(PG_PORT), so compose fails
# on a name conflict if the standalone container is still up. `make down` then
# `make up` (or vice versa) to switch. The Postgres volume $(PG_VOLUME) is
# shared between them, so the data is the same either way.
up:
	$(COMPOSE_ENV) docker compose up --build -d
	@echo "App on http://localhost:$(APP_PORT) — logs: docker compose logs -f"

down:
	$(COMPOSE_ENV) docker compose down

clean:
	find backend -type d -name '__pycache__' -not -path '*/.venv/*' -exec rm -rf {} +
	rm -rf backend/.pytest_cache
