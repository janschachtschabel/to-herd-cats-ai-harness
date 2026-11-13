# to-herd-cats-ai: one image for every role (HERD_ROLE=api|migrate|all).
#
# Stages: the frontend is built with node (node stays in that stage: no node runtime
# in the image until collab arrives in M2), the Python environment with uv, and the
# runtime is python:3.13-slim with the SPA as static files. Base images are pinned by
# digest; Renovate keeps them current.
#
# Runs as 10001, works with a read-only root filesystem (only /tmp writable), tini as
# PID 1 forwards SIGTERM to the launcher, which stops both servers in order.

ARG PYTHON_IMAGE=python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ARG NODE_IMAGE=node:22-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee

# --- frontend: the SPA as static files --------------------------------------------
FROM ${NODE_IMAGE} AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The live editor imports the collab process's editor schema (one schema for both).
COPY collab/schema.mjs /src/collab/schema.mjs
RUN npm run build

# --- python: the locked dependencies in /app/.venv ----------------------------------
FROM ${PYTHON_IMAGE} AS python
ARG UV_VERSION=0.11.32
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
# The project itself is not installed: its code is copied to /app and run from there.
RUN uv sync --locked --no-dev --no-install-project
COPY backend/app ./app
COPY backend/alembic ./alembic
RUN python -m compileall -q app alembic

# --- tini, checked against the release's published checksums ------------------------
FROM scratch AS tini
ADD --checksum=sha256:c5b0666b4cb676901f90dfcb37106783c5fe2077b04590973b885950611b30ee \
    https://github.com/krallin/tini/releases/download/v0.19.0/tini-static-amd64 /tini-amd64
ADD --checksum=sha256:eae1d3aa50c48fb23b8cbdf4e369d0910dfc538566bfd09df89a774aa84a48b9 \
    https://github.com/krallin/tini/releases/download/v0.19.0/tini-static-arm64 /tini-arm64

# --- runtime -------------------------------------------------------------------------
FROM ${PYTHON_IMAGE}
ARG TARGETARCH
ARG VERSION=0.1.0
LABEL org.opencontainers.image.title="to-herd-cats-ai" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0"
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    HERD_ENVIRONMENT=production \
    HERD_STATIC_DIR=/app/static \
    HERD_PUBLIC_PORT=8080 \
    HERD_INTERNAL_PORT=9090 \
    OTEL_SERVICE_NAME=to-herd-cats-ai
# The app runs from /app/.venv. The base image's own pip (with its vendored libraries)
# and setuptools are never used at runtime, so they are removed instead of patched.
RUN rm -rf /usr/local/lib/python3.13/site-packages/* /usr/local/bin/pip*
# Debian security updates published after the pinned base image was built.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/log/apt /var/log/dpkg.log
WORKDIR /app
COPY --from=tini --chmod=0755 /tini-${TARGETARCH} /usr/bin/tini
COPY --from=python /app /app
COPY --from=frontend /src/frontend/dist /app/static
USER 10001:10001
EXPOSE 8080 9090
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('HERD_INTERNAL_PORT', '9090'), timeout=2)"]
ENTRYPOINT ["/usr/bin/tini", "--", "python", "-m", "app.launch"]
