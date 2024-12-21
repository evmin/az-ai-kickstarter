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

COPY pyproject.toml /app/
COPY uv.lock /app/
COPY src/backend /app/src/backend/

RUN --mount=type=cache,target=/root/.cache <<EOT
uv sync \
    --frozen \
    --no-dev \
    --no-install-workspace \
    --no-editable \
    --project src/backend
EOT

###############
# Final image #
###############

FROM python:3.12-slim

SHELL ["sh", "-exc"]

# Optional: add the application virtualenv to search path.
ENV PATH=/app/.venv/bin:$PATH

RUN <<EOT
groupadd -r app
useradd -r -d /app -g app -N app
EOT

EXPOSE 8000
STOPSIGNAL SIGINT

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src/backend /app/src/backend

WORKDIR /app/src/backend
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]