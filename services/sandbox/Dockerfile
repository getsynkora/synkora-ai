FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        git \
        coreutils \
        findutils \
        procps bubblewrap \
    && rm -rf /var/lib/lists/*

COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.lock

RUN mkdir -p /workspaces

COPY app.py isolation.py capability.py ./

EXPOSE 5004

RUN useradd -m -u 1000 -s /bin/bash sandbox && chown -R sandbox:sandbox /app /workspaces
USER sandbox

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5004"]
