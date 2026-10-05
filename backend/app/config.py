from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT.parent / ".env"), extra="ignore")

    database_url: str = "postgresql://rag:rag@localhost:5433/rag"

    groq_api_key: str = ""
    answer_model: str = "openai/gpt-oss-120b"
    rewrite_model: str = "openai/gpt-oss-20b"
    # A different model family from the answerer, to limit self-preference bias.
    judge_model: str = "qwen/qwen3.8-27b"
    reasoning_effort: str = "medium"  # gpt-oss only: low | medium | high

    embed_model: str = "BAAI/bge-base-en-v1.5"
    rerank_model: str = "BAAI/bge-reranker-base"

    candidates: int = 30         # per retriever, before fusion
    rerank_candidates: int = 20  # fused candidates sent to the cross-encoder
    top_k: int = 5                 # chunks returned by /api/search
    # Small-to-big context: rank chunks, then give the LLM whole sections.
    context_fetch_chunks: int = 15  # ranked chunks to group into sections
    context_sections: int = 5       # sections passed to the LLM
    context_char_budget: int = 16000
    rrf_k: int = 60

    # Comma-separated, e.g. "https://nyaya.vercel.app,http://localhost:3000"
    cors_origins: str = "http://localhost:3000"
    # Also allow this app's Vercel preview deployments.
    cors_origin_regex: str = r"https://.*\.vercel\.app"

    # Per-visitor limits on /api/chat, so a public demo can't drain the LLM quota.
    chat_per_minute: int = 6
    chat_per_day: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
