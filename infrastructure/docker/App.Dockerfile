FROM node:24.14.1-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM ghcr.io/astral-sh/uv:0.12.13 AS uv
FROM docker:29.9.2-cli AS docker
FROM python:3.13.15-slim-bookworm
COPY --from=uv /uv /usr/local/bin/uv
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /kyro/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
COPY --from=frontend /build/frontend/dist /kyro/frontend/dist
COPY tests/fixtures/ /kyro/tests/fixtures/
RUN useradd --uid 1000 --create-home kyro && mkdir /data && chown -R 1000:1000 /data /kyro
USER 1000:1000
ENV PATH="/kyro/backend/.venv/bin:${PATH}" KYRO_DATA_DIR=/data KYRO_DATABASE_URL=sqlite:////data/kyro.db PYTHONDONTWRITEBYTECODE=1
EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health',timeout=4)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8787", "--no-access-log"]
