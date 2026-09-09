.PHONY: install install-backend install-frontend \
        dev backend frontend \
        kill kill-backend kill-frontend \
        test test-backend \
        clean

BACKEND_PORT := 8091
FRONTEND_PORT := 5173

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

clean:
	find backend -type d -name '__pycache__' -not -path '*/.venv/*' -exec rm -rf {} +
	rm -rf backend/.pytest_cache
