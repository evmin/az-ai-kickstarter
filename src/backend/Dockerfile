###############
# Build stage #
###############

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.12 \
    UV_PROJECT_ENVIRONMENT=/app/.venv

## install depdencies first as they change less often

COPY uv.lock pyproject.toml .python-version /app/
COPY src/hello-ai-world-core/.python-version /app/src/hello-ai-world-core/
COPY src/hello-ai-world-core/pyproject.toml /app/src/hello-ai-world-core/
COPY src/backend/pyproject.toml /app/src/backend/
COPY src/backend/.python-version /app/src/backend/
RUN --mount=type=cache,target=/root/.cache/uv <<EOT
uv sync \
    --frozen \
    --no-dev \
    --no-install-workspace \
    --no-editable \
    --all-packages
EOT

## install the backend last as it changes most often

COPY src/hello-ai-world-core /app/src/hello-ai-world-core
COPY src/backend /app/src/backend
RUN --mount=type=cache,target=/root/.cache/uv <<EOT
uv sync \
    --frozen \
    --no-dev \
    --no-editable \
    --project src/backend    
EOT

###############
# Final image #
###############

FROM python:3.12-slim

SHELL ["sh", "-exc"]

RUN <<EOT
groupadd -r app
useradd -r -d /app -g app -N app
EOT

EXPOSE 8000
STOPSIGNAL SIGINT

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src/backend /app/src/backend

WORKDIR /app/src/backend
ENTRYPOINT ["/app/.venv/bin/uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]