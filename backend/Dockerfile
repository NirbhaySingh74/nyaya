# Backend image for Hugging Face Spaces (Docker SDK, port 7860, non-root uid 1000).
FROM python:3.11-slim

RUN useradd -m -u 1000 user
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.18
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    HF_HUB_DISABLE_XET=1 PORT=7860

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
# Bake the ONNX models into the image so startup doesn't download ~1.3 GB.
RUN uv run --no-sync python -c "from app.models import embedder, reranker; embedder(); reranker()" \
    && chown -R user:user /app

USER user
EXPOSE 7860
CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
