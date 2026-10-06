"""Local embedding and cross-encoder models (ONNX via fastembed, CPU-only)."""

from functools import lru_cache

import numpy as np
from fastembed import TextEmbedding
from fastembed.rerank.cross_encoder import TextCrossEncoder

from app.config import ROOT, get_settings

CACHE_DIR = str(ROOT / ".models")

# bge models expect this prefix on queries (not on passages).
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _threads() -> int | None:
    return get_settings().onnx_threads or None


@lru_cache
def embedder() -> TextEmbedding:
    return TextEmbedding(get_settings().embed_model, cache_dir=CACHE_DIR, threads=_threads())


@lru_cache
def reranker() -> TextCrossEncoder:
    return TextCrossEncoder(get_settings().rerank_model, cache_dir=CACHE_DIR, threads=_threads())


def embed_passages(texts: list[str]) -> list[np.ndarray]:
    return list(embedder().embed(texts, batch_size=32))


def embed_query(text: str) -> np.ndarray:
    prefix = BGE_QUERY_PREFIX if "bge" in get_settings().embed_model.lower() else ""
    return next(iter(embedder().embed([prefix + text])))


def rerank_scores(query: str, docs: list[str]) -> list[float]:
    return list(reranker().rerank(query, docs, batch_size=16))
