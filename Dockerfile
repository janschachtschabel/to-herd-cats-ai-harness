# to-herd-cats-ai: one image for every role (HERD_ROLE=api|migrate|all|worker|collab).
#
# Stages: the frontend is built with node, the collab process (live editing) gets its
# production node_modules, the Python environment is built with uv, and the runtime is
# python:3.13-slim with the SPA as static files, the collab process and the node
# binary of the node stage (nothing else of node: no npm, no corepack). Base images
# are pinned by digest; Renovate keeps them current.
#
# Runs as 10001, works with a read-only root filesystem (writable: /tmp, the files
# volume on /data, the backups volume on /backups and the Hostinger stack's secret
# volumes on /secrets and /db-secret), tini as PID 1 forwards SIGTERM
# to the launcher, which stops both
# servers (and the collab child) in order.

ARG PYTHON_IMAGE=python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90
ARG NODE_IMAGE=node:22-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee
ARG GO_IMAGE=golang:1.27.4-trixie@sha256:f18c3d73a184fb0582828510722e723b63a93f7188d11dd223d9be6f6880e65d

# --- frontend: the SPA as static files --------------------------------------------
FROM ${NODE_IMAGE} AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The live editor and the page view import the collab process's editor (schema, Y.Doc
# binding, load guard), its serializer and its wiki-link finder (one rule for both sides).
COPY collab/editor.mjs collab/schema.mjs collab/tables.mjs collab/syntax.mjs collab/serialize.mjs collab/parse.mjs collab/cells.mjs \
     collab/canonical.mjs collab/inline.mjs collab/wikilinks.mjs /src/collab/
RUN npm run build

# --- collab: the live-editing process with its production dependencies -------------
FROM ${NODE_IMAGE} AS collab
WORKDIR /src/collab
COPY collab/package.json collab/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund
COPY collab/*.mjs ./

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

# --- restic (offsite backups, plan M9 decision 8; BSD-2-Clause), built from source -----
# The release binaries lag behind Go's and the libraries' security fixes (0.19.1 is
# built with go1.26.4; Trivy fails the image on them), so restic is built here: the
# release's source archive (checksum from its SHA256SUMS) with deploy/restic/go.mod and
# go.sum, which are the release's own with the modules Trivy flagged raised to fixed
# versions (`go get github.com/klauspost/compress@v1.18.7 golang.org/x/net@v0.62.0
# google.golang.org/grpc@v1.83.2 && go mod tidy` in the unpacked source; go.sum checks
# every module), the official build's tags and flags, without self-update.
# Cross-compiled on the build platform (CGO_ENABLED=0), -trimpath for a reproducible
# binary. The stage restic-bin exports only the binary (CI's backend job tests it).
FROM --platform=${BUILDPLATFORM} ${GO_IMAGE} AS restic
ARG TARGETARCH
ADD --checksum=sha256:bb9b1a19040744d26d8a79be029d4e6b189c45ccc9d8831d7fe367d3c33df725 \
    https://github.com/restic/restic/releases/download/v0.19.1/restic-0.19.1.tar.gz /restic.tar.gz
WORKDIR /src
RUN tar -xzf /restic.tar.gz --strip-components=1 && rm /restic.tar.gz
COPY deploy/restic/go.mod deploy/restic/go.sum ./
RUN CGO_ENABLED=0 GOOS=linux GOARCH=${TARGETARCH} GOTOOLCHAIN=local GOFLAGS=-mod=readonly \
        go build -trimpath -buildvcs=false -tags disable_grpc_modules -ldflags "-s -w" \
        -o /restic ./cmd/restic

FROM scratch AS restic-bin
COPY --from=restic /restic /restic

# --- runtime -------------------------------------------------------------------------
FROM ${PYTHON_IMAGE}
ARG TARGETARCH
ARG VERSION=1.0.0
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
    HERD_COLLAB_SCRIPT=/app/collab/server.mjs \
    NODE_ENV=production \
    OTEL_SERVICE_NAME=to-herd-cats-ai
# The app runs from /app/.venv. The base image's own pip (with its vendored libraries)
# and setuptools are never used at runtime, so they are removed instead of patched.
RUN rm -rf /usr/local/lib/python3.13/site-packages/* /usr/local/bin/pip*
# Debian security updates published after the pinned base image was built, and
# PostgreSQL's client tools for backups (`python -m app.ops backup`, plan M9 decision
# 2: pg_dump/pg_restore 17 serve servers 16 and 17; PostgreSQL licence).
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends postgresql-client-17 \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /var/log/apt /var/log/dpkg.log
WORKDIR /app
COPY --from=tini --chmod=0755 /tini-${TARGETARCH} /usr/bin/tini
COPY --from=restic-bin /restic /usr/local/bin/restic
COPY --from=python /app /app
COPY --from=frontend /src/frontend/dist /app/static
COPY --from=collab /usr/local/bin/node /usr/local/bin/node
COPY --from=collab /src/collab /app/collab
# The files volume (attachments): owned by the app user, so that a fresh named volume
# mounted here (docker copies the directory's owner into it) is writable.
# The same for the Hostinger stack's secret volumes (docker-compose.yml in the repo's
# root, `python -m app.stack init` writes them).
RUN mkdir /data && chown 10001:10001 /data \
    && mkdir -m 0700 /backups && chown 10001:10001 /backups \
    && mkdir -m 0700 /secrets /db-secret && chown 10001:10001 /secrets /db-secret
USER 10001:10001
EXPOSE 8080 9090
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('HERD_INTERNAL_PORT', '9090'), timeout=2)"]
ENTRYPOINT ["/usr/bin/tini", "--", "python", "-m", "app.launch"]
