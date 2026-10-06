# Backend image for Google Cloud Run (listens on $PORT, runs as non-root).
FROM python:3.11-slim

# Production reranker: same held-out Recall@5 as bge-reranker-base (93.6%) at
# ~1/4 of the memory (0.65 GB vs 2.5 GB peak) and ~2x the speed.
ARG RERANK_MODEL=Xenova/ms-marco-MiniLM-L-12-v2

RUN useradd -m -u 1000 user && pip install --no-cache-dir uv==0.11.18
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    HF_HUB_DISABLE_XET=1 RERANK_MODEL=${RERANK_MODEL} PORT=8080

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# Bake the ONNX models into the image so cold starts don't download them.
RUN uv run --no-sync python -c "from app.models import embedder, reranker; embedder(); reranker()" \
    && chown -R user:user /app

USER user
EXPOSE 8080
CMD ["sh", "-c", "exec uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
