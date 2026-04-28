# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update -y && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

# Copy workspace metadata first for better layer caching
COPY pyproject.toml uv.lock ./
COPY libs/domain/pyproject.toml libs/domain/pyproject.toml
COPY libs/application/pyproject.toml libs/application/pyproject.toml
COPY libs/infrastructure/pyproject.toml libs/infrastructure/pyproject.toml
COPY libs/contracts/generated/python/pyproject.toml libs/contracts/generated/python/pyproject.toml
COPY apps/api/pyproject.toml apps/api/pyproject.toml

# Lock-respecting install of full workspace
RUN uv sync --frozen --no-dev --all-packages || uv sync --no-dev --all-packages

# Copy source
COPY libs ./libs
COPY apps/api ./apps/api

EXPOSE 8000
CMD ["uv", "run", "--package", "golf-api", "uvicorn", "golf_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
