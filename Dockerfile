# syntax=docker/dockerfile:1
ARG PYTHON_IMAGE=python:3.13.9-slim

FROM ${PYTHON_IMAGE} AS builder

ARG POETRY_VERSION=2.3.2

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_CACHE_DIR=/tmp/poetry-cache \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

COPY pyproject.toml poetry.lock ./

RUN --mount=type=cache,target=/tmp/poetry-cache \
    poetry install --only main --no-root --no-directory

COPY README.md ./
COPY src ./src

RUN --mount=type=cache,target=/tmp/poetry-cache \
    poetry install --only main

FROM ${PYTHON_IMAGE} AS runtime

LABEL org.opencontainers.image.title="ai-blogger" \
      org.opencontainers.image.description="AI-блогер: генерация, модерация и публикация постов в Telegram" \
      org.opencontainers.image.source="https://github.com/firstConsole/ai-blogger-backend-test"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    PATH="/app/.venv/bin:${PATH}"

ARG UID=1000
ARG GID=1000

RUN groupadd --system --gid ${GID} app \
    && useradd --system --uid ${UID} --gid app \
       --home-dir /home/app --create-home --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /app/.venv ./.venv
COPY src ./src

RUN install -d -o app -g app /app/data

RUN find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

USER app
