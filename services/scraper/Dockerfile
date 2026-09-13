FROM python:3.11-slim-bookworm

WORKDIR /app

# System dependencies for Playwright Chromium
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

# Install Playwright Chromium to a shared path accessible by non-root user
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium --with-deps \
    && chmod -R 755 /ms-playwright

COPY browser_session.py .
COPY app.py .

EXPOSE 5003

# Non-root user for security
RUN useradd -m -u 1000 -s /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5003"]
