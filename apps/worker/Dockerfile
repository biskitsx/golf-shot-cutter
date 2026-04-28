# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    curl ca-certificates ffmpeg libsndfile1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml

RUN uv sync --frozen --no-dev --all-packages || uv sync --no-dev --all-packages

COPY apps/api ./apps/api
COPY apps/worker ./apps/worker

CMD ["uv", "run", "--package", "golf-worker", "celery", "-A", "worker_app.main:celery_app", "worker", "--loglevel=INFO", "--queues", "video,export"]
