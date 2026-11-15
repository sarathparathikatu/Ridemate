# RideMate API image. Built by docker-compose.yml (repo root) and by CI.
FROM python:3.13-slim

# uv, the same installer used in development, copied from its official image.
COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# Dependencies first, in their own layer: Docker reuses this cached layer until
# pyproject.toml or uv.lock change, so code edits rebuild in seconds.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Never run the app as root inside the container.
RUN useradd --create-home ridemate
USER ridemate

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# --proxy-headers: trust X-Forwarded-For from the reverse proxy (nginx), so rate limits
# see each visitor's real IP instead of the proxy's.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
