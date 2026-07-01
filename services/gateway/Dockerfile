# FinSight gateway image. Built in the cloud via `az acr build` (no local Docker needed).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the shared library + runtime extras (parsing + cloud), not dev tools.
COPY pyproject.toml README.md ./
COPY libs ./libs
COPY services ./services
RUN pip install ".[data,ai,snowflake]"

# Run as a non-root user.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
# `python -m` puts the working dir on sys.path so `services.gateway.app` resolves.
CMD ["python", "-m", "uvicorn", "services.gateway.app:app", "--host", "0.0.0.0", "--port", "8000"]
