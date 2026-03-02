.PHONY: install dev dev-backend dev-frontend test lint clean

# Install all dependencies
install: install-backend install-frontend

install-backend:
	cd backend && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

# Development servers
dev: dev-backend dev-frontend

dev-backend:
	cd backend && ./venv/bin/python -m uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

# Testing
test: test-backend

test-backend:
	cd backend && ./venv/bin/python -m pytest tests/ -v

# Linting
lint: lint-backend lint-frontend

lint-backend:
	cd backend && ./venv/bin/python -m ruff check app/ tests/

lint-frontend:
	cd frontend && npx tsc --noEmit

# Type checking
type-check:
	cd frontend && npx tsc --noEmit

# Clean build artifacts
clean:
	rm -rf backend/__pycache__ backend/app/__pycache__
	rm -rf backend/.pytest_cache backend/.ruff_cache
	rm -rf backend/.cache
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
