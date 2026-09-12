FROM python:3.11-slim-bookworm

WORKDIR /app

ARG EMBEDDING_MODEL_REVISION
ARG RERANK_MODEL_REVISION
RUN test -n "$EMBEDDING_MODEL_REVISION" && test -n "$RERANK_MODEL_REVISION"
ENV EMBEDDING_MODEL_REVISION=$EMBEDDING_MODEL_REVISION \
    RERANK_MODEL_REVISION=$RERANK_MODEL_REVISION
RUN pip install --no-cache-dir \
    fastapi==0.136.1 \
    'uvicorn[standard]==0.41.0' \
    sentence-transformers==5.1.2 \
    faiss-cpu==1.12.0 \
    numpy==1.26.4 \
    pydantic==2.12.5

COPY app.py .

# Pre-download models at build time so startup is instant (no runtime download).
# Needs real network access, so this must run before HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE
# are set below — those env vars are for the running service only, to guarantee it
# never phones home and only ever serves the pinned revisions baked into this image.
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
from sentence_transformers.cross_encoder import CrossEncoder; \
SentenceTransformer('all-MiniLM-L6-v2', revision='$EMBEDDING_MODEL_REVISION'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', revision='$RERANK_MODEL_REVISION')"

ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

EXPOSE 5002

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]
