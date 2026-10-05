import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from groq import RateLimitError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app import llm
from app.config import get_settings
from app.db import get_pool
from app.models import embedder, reranker
from app.retrieval import Hit, Mode, retrieve, section_context

EVAL_RESULTS = Path(__file__).resolve().parent.parent / "eval" / "results"


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Load ONNX models and open the pool up front so the first request isn't slow.
    await run_in_threadpool(embedder)
    await run_in_threadpool(reranker)
    get_pool()
    yield
    get_pool().close()


app = FastAPI(title="Nyaya RAG API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_origin_regex=get_settings().cors_origin_regex or None,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = []
    mode: Mode = "hybrid_rerank"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Mode = "hybrid_rerank"
    top_k: int = Field(default=10, ge=1, le=30)


def source_payload(hits: list[Hit]) -> list[dict]:
    return [
        {
            "n": i,
            "chunk_id": h.id,  # section id once expanded by section_context
            "section_id": h.section_id,
            "act_id": h.act_id,
            "act_short": h.act_short,
            "section": h.section,
            "title": h.title,
            "chapter": h.chapter,
            "page": h.page,
            "source_url": h.source_url,
            "content": h.content,
            "score": round(h.score, 4),
            "ranks": h.ranks,
        }
        for i, h in enumerate(hits, start=1)
    ]


_requests: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(request: Request) -> None:
    """In-memory sliding window per client IP (single instance is enough for a demo)."""
    s = get_settings()
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    now = time.time()
    q = _requests[ip]
    while q and now - q[0] > 86400:
        q.popleft()
    last_minute = sum(1 for t in q if now - t < 60)
    if last_minute >= s.chat_per_minute:
        raise HTTPException(429, "You're asking quickly. Wait a minute and try again.")
    if len(q) >= s.chat_per_day:
        raise HTTPException(429, "You've reached today's question limit for this demo. Try again tomorrow.")
    q.append(now)


@app.get("/")
def root():
    return {"name": "Nyaya RAG API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    with get_pool().connection() as conn:
        n = conn.execute("SELECT count(*) AS n FROM chunks").fetchone()["n"]
    return {"ok": True, "chunks": n, "llm_configured": llm.llm_configured()}


@app.get("/api/meta")
def meta():
    s = get_settings()
    with get_pool().connection() as conn:
        acts = conn.execute(
            """SELECT s.act_id, s.act_name, s.act_short, s.source_url,
                      count(DISTINCT s.id) AS sections, count(c.id) AS chunks
               FROM sections s JOIN chunks c ON c.section_id = s.id
               GROUP BY 1, 2, 3, 4 ORDER BY 1"""
        ).fetchall()
    summary = EVAL_RESULTS / "summary.json"
    return {
        "acts": acts,
        "models": {
            "answer": s.answer_model,
            "rewrite": s.rewrite_model,
            "judge": s.judge_model,
            "embedding": s.embed_model,
            "reranker": s.rerank_model,
        },
        "llm_configured": llm.llm_configured(),
        "eval": json.loads(summary.read_text()) if summary.exists() else None,
    }


@app.get("/api/sections/{section_id}")
def get_section(section_id: str):
    with get_pool().connection() as conn:
        row = conn.execute("SELECT * FROM sections WHERE id = %s", (section_id,)).fetchone()
    if not row:
        raise HTTPException(404, "section not found")
    return row


@app.post("/api/search")
async def search(req: SearchRequest):
    res = await run_in_threadpool(retrieve, req.query, req.mode, req.top_k)
    return {"results": source_payload(res.hits), "timings_ms": res.timings_ms}


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    check_rate_limit(request)
    history = [t.model_dump() for t in req.history]

    async def events():
        t0 = time.perf_counter()
        timings: dict[str, float] = {}
        query = req.question
        try:
            if history and llm.llm_configured():
                t = time.perf_counter()
                query = await run_in_threadpool(llm.rewrite_query, req.question, history)
                timings["rewrite"] = round((time.perf_counter() - t) * 1000, 1)

            s = get_settings()
            res = await run_in_threadpool(retrieve, query, req.mode, s.context_fetch_chunks)
            timings.update(res.timings_ms)
            context = await run_in_threadpool(section_context, res.hits)
            yield {"event": "sources", "data": json.dumps({"query": query, "sources": source_payload(context)})}

            if not llm.llm_configured():
                yield {"event": "error", "data": json.dumps({"message": "GROQ_API_KEY is not set on the server. Retrieval works; generation is disabled."})}
                return

            t = time.perf_counter()
            first_token_ms = None
            async for delta in llm.stream_answer(req.question, context, history):
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - t0) * 1000, 1)
                yield {"event": "token", "data": json.dumps({"t": delta})}
            timings["generate"] = round((time.perf_counter() - t) * 1000, 1)
            timings["first_token"] = first_token_ms or 0.0
            timings["total"] = round((time.perf_counter() - t0) * 1000, 1)
            yield {"event": "done", "data": json.dumps({"timings_ms": timings, "model": get_settings().answer_model})}
        except RateLimitError:
            msg = "The demo has used up its free AI quota for now. Retrieval still works; try again later."
            yield {"event": "error", "data": json.dumps({"message": msg})}
        except Exception as e:  # surface failures to the client instead of a dropped stream
            yield {"event": "error", "data": json.dumps({"message": f"{type(e).__name__}: {e}"})}

    return EventSourceResponse(events())
