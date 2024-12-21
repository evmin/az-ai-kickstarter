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

# We won't ship those
COPY pyproject.toml /app/
COPY uv.lock /app/
COPY src/backend/ /app/src/backend/

RUN --mount=type=cache,target=/root/.cache <<EOT
cd /app/src/backend
uv sync \
    --frozen \
    --no-dev \
    --no-install-workspace \
    --no-editable
EOT


SHELL ["sh", "-exc"]

# Optional: add the application virtualenv to search path.
ENV PATH=/app/.venv/bin:$PATH

RUN <<EOT
groupadd -r app
useradd -r -d /app -g app -N app
EOT

ENTRYPOINT ["/docker-entrypoint.sh"]

STOPSIGNAL SIGINT

COPY src/backend/docker-entrypoint.sh /

# Copy the environment, but not the source code

# Expose the port
EXPOSE 8000