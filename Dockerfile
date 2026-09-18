# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Stage 1: build the CyberHero React/Vite bundle
# ---------------------------------------------------------------------------
FROM node:22-bookworm-slim AS cyberhero-build
WORKDIR /build/cyberhero
COPY cyberhero/package.json cyberhero/package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY cyberhero/ ./
# Vite writes into ../app/static/cyberhero (see vite.config.js)
RUN mkdir -p /build/app/static && npm run build

# ---------------------------------------------------------------------------
# Stage 2: build Python wheels (compilers live only here)
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS python-build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---------------------------------------------------------------------------
# Stage 3: slim runtime (no Node, no compilers, non-root)
# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    APP_ENV=production UPLOAD_PATH=/var/lib/elearning/uploads
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1001 elearning \
    && useradd --system --uid 1001 --gid elearning --create-home --home-dir /app elearning \
    && mkdir -p /var/lib/elearning/uploads && chown -R elearning:elearning /var/lib/elearning
WORKDIR /app
COPY --from=python-build /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels
COPY --chown=elearning:elearning app ./app
COPY --chown=elearning:elearning migrations ./migrations
COPY --chown=elearning:elearning seeds ./seeds
COPY --chown=elearning:elearning docker/gunicorn.conf.py docker/entrypoint.sh wsgi.py babel.cfg ./
COPY --from=cyberhero-build --chown=elearning:elearning /build/app/static/cyberhero ./app/static/cyberhero
RUN pybabel compile -d app/translations -f 2>/dev/null || true \
    && chmod +x /app/entrypoint.sh
USER elearning
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
