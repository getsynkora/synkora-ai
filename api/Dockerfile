# base image
FROM python:3.11-slim-bookworm AS base

WORKDIR /app/api

# Install uv
ENV UV_VERSION=0.5.11
RUN pip install --no-cache-dir uv==${UV_VERSION}


# packages stage - install dependencies
FROM base AS packages

# Install build dependencies including SAML/xmlsec requirements
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        make \
        libc-dev \
        libffi-dev \
        libpq-dev \
        libxml2-dev \
        libxmlsec1-dev \
        libxmlsec1-openssl \
        pkg-config \
        libcairo2-dev \
        libpango1.0-dev \
        libgdk-pixbuf2.0-dev \
        unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies system-wide using the lock file
COPY pyproject.toml uv.lock ./
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install --system --no-cache --extra diagrams -r pyproject.toml

# Install awslambdaric here so the lambda stage does not need to run as root
RUN pip install --no-cache-dir awslambdaric==2.0.8


# production stage
FROM base AS production

ENV PYTHONUNBUFFERED=1
ENV EDITION=SELF_HOSTED
ENV DEPLOY_ENV=PRODUCTION

EXPOSE 5001

# Set timezone
ENV TZ=UTC

# Set UTF-8 locale
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
ENV PYTHONIOENCODING=utf-8

WORKDIR /app/api

# Install runtime dependencies: Node.js (npx for MCP servers), SAML/xmlsec libs
# Playwright/Chromium now lives in synkora-scraper; those libs removed here.
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        postgresql-client \
        libpq5 \
        libmagic1 \
        ca-certificates \
        git \
        openssh-client \
        tree \
        # SAML/xmlsec runtime libraries
        libxml2 \
        libxmlsec1 \
        libxmlsec1-openssl \
        # cairosvg runtime libraries (SVG→PNG conversion)
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf2.0-0 \
        # SQL Server ODBC runtime (required by aioodbc/pyodbc)
        libodbc2 \
        # Node.js (Debian bookworm ships Node 18 — sufficient for npx/MCP)
        nodejs \
        npm \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from packages stage
COPY --from=packages /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=packages /usr/local/bin /usr/local/bin

# Configure git identity for agent git operations (commit requires user.name + user.email)
# These are overridden at runtime by GIT_AGENT_EMAIL / GIT_AGENT_NAME env vars in git_commit_tools.py
RUN git config --system user.email "agent@localhost" && \
    git config --system user.name "AI Agent"

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy source code
COPY . /app/api/

# Copy and set entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && chown -R appuser:appuser /app

ARG COMMIT_SHA
ENV COMMIT_SHA=${COMMIT_SHA}

USER appuser

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:5001/health || exit 1

ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]


# ── Lambda stage ─────────────────────────────────────────────────────────────
# Same code as production but uses the AWS Lambda Runtime Interface Client (RIC)
# as entrypoint so AWS can call our handler function.
#
# Build:   docker build --target lambda -t synkora-agent-runner:lambda .
# Push:    docker tag ... {account}.dkr.ecr.{region}.amazonaws.com/synkora-agent-runner:latest
#
# Cloud Run and DO Functions use the production stage above with a different
# CMD — no separate Dockerfile needed for them.
FROM production AS lambda

# awslambdaric is pre-installed in the packages stage — no root required here.
# USER appuser is inherited from the production stage above.

# Prevent the executor from re-dispatching to Lambda (infinite loop guard)
ENV SYNKORA_DIRECT_EXECUTION=true

# AWS Lambda calls ENTRYPOINT [RIC] with CMD [handler] as argument
ENTRYPOINT ["/usr/local/bin/python", "-m", "awslambdaric"]
CMD ["src.handlers.lambda_handler.handler"]
