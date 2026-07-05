# FinSight developer shortcuts.
# On Windows, run these from Git Bash / WSL, or run the underlying commands directly.

.PHONY: help install dev test lint fmt up down gen-data train mlflow-ui obs-up obs-down grafana-cloud clean

help:
	@echo "install   - install all deps (uv) incl. data/ai/pii/ml/obs/dev extras"
	@echo "dev       - run the gateway API with autoreload on :8000"
	@echo "test      - run pytest"
	@echo "lint      - ruff check"
	@echo "fmt       - ruff format"
	@echo "up        - start local stack (postgres, azurite, redpanda)"
	@echo "down      - stop local stack"
	@echo "gen-data  - generate synthetic statements into data/synthetic/"
	@echo "train     - train the anomaly model + log to MLflow (./mlruns)"
	@echo "mlflow-ui - open the MLflow experiment UI on :5000"
	@echo "obs-up    - start Prometheus (:9090) + Grafana (:3001)"
	@echo "obs-down  - stop Prometheus + Grafana"
	@echo "grafana-cloud - ship live gateway metrics to Grafana Cloud (needs GRAFANA_CLOUD_* in .env)"

install:
	uv sync --extra dev --extra data --extra ai --extra snowflake --extra aws --extra ml --extra mlops --extra obs

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

train:
	uv run python scripts/train_anomaly_model.py

mlflow-ui:
	uv run mlflow ui --backend-store-uri sqlite:///mlflow.db

obs-up:
	docker compose up -d prometheus grafana

obs-down:
	docker compose stop prometheus grafana

grafana-cloud:
	docker compose --profile cloud up alloy

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache **/__pycache__
