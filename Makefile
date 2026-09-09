.PHONY: install install-backend install-frontend \
        dev backend frontend \
        test test-backend \
        clean

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

test: test-backend

test-backend:
	cd backend && uv run pytest

clean:
	find backend -type d -name '__pycache__' -not -path '*/.venv/*' -exec rm -rf {} +
	rm -rf backend/.pytest_cache
