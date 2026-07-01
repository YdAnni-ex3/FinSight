# FinSight developer shortcuts.
# On Windows, run these from Git Bash / WSL, or run the underlying commands directly.

.PHONY: help install dev test lint fmt up down gen-data clean

help:
	@echo "install   - install all deps (uv) incl. data/ai/pii/dev extras"
	@echo "dev       - run the gateway API with autoreload on :8000"
	@echo "test      - run pytest"
	@echo "lint      - ruff check"
	@echo "fmt       - ruff format"
	@echo "up        - start local stack (postgres, azurite, redpanda)"
	@echo "down      - stop local stack"
	@echo "gen-data  - generate synthetic statements into data/synthetic/"

install:
	uv sync --extra dev --extra data --extra ai --extra pii --extra snowflake

dev:
	uv run uvicorn services.gateway.app:app --reload --port 8000

test:
	uv run pytest

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

up:
	docker compose up -d

down:
	docker compose down

gen-data:
	uv run python scripts/generate_synthetic_statements.py --count 5

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__
