"""Retrieval pipeline: vector + BM25 search, RRF fusion, cross-encoder rerank.

Modes (all comparable in eval/retrieval_eval.py):
  vector         pgvector cosine similarity (HNSW)
  fts            Postgres full-text search (OR-of-terms, ts_rank_cd) — baseline
  bm25           Okapi BM25 over the same Postgres lexemes (app/bm25.py)
  hybrid         Reciprocal Rank Fusion of vector + bm25
  hybrid_rerank  top hybrid candidates re-scored by a cross-encoder, fused with
                 their hybrid rank
"""

import time
from dataclasses import dataclass, field
from typing import Literal

from app.config import get_settings
from app import bm25
from app.db import get_pool
from app.models import embed_query, rerank_scores

Mode = Literal["vector", "fts", "bm25", "hybrid", "hybrid_rerank"]
MODES: tuple[Mode, ...] = ("vector", "fts", "bm25", "hybrid", "hybrid_rerank")

CHUNK_COLS = """c.id, c.section_id, c.act_id, c.chunk_index, c.header, c.content,
                s.section, s.title, s.act_short, s.chapter, s.page, s.source_url"""


@dataclass
class Hit:
    id: str
    section_id: str
    act_id: str
    act_short: str
    section: str
    title: str
    chapter: str
    page: int
    source_url: str
    header: str
    content: str
    chunk_index: int
    score: float = 0.0
    ranks: dict[str, int] = field(default_factory=dict)  # rank in each retriever, 1-based


@dataclass
class RetrievalResult:
    hits: list[Hit]
    timings_ms: dict[str, float]


def _hit(row: dict) -> Hit:
    keep = {k: row[k] for k in Hit.__dataclass_fields__ if k in row and k not in ("score", "ranks")}
    return Hit(**keep)


def vector_search(query: str, k: int) -> list[Hit]:
    qv = embed_query(query)
    with get_pool().connection() as conn:
        rows = conn.execute(
            f"""SELECT {CHUNK_COLS}, 1 - (c.embedding <=> %s) AS score
                FROM chunks c JOIN sections s ON s.id = c.section_id
                ORDER BY c.embedding <=> %s LIMIT %s""",
            (qv, qv, k),
        ).fetchall()
    hits = []
    for r in rows:
        h = _hit(r)
        h.score = float(r["score"])
        hits.append(h)
    return hits


def fts_search(query: str, k: int) -> list[Hit]:
    # OR the query's lexemes together: websearch/plainto_tsquery AND every term,
    # which returns nothing for most natural-language questions.
    with get_pool().connection() as conn:
        rows = conn.execute(
            f"""WITH q AS (
                    SELECT to_tsquery('english', string_agg(lexeme, ' | ')) AS tsq
                    FROM unnest(tsvector_to_array(to_tsvector('english', %s))) AS lexeme
                )
                SELECT {CHUNK_COLS}, ts_rank_cd(c.tsv, q.tsq, 1) AS score
                FROM chunks c JOIN sections s ON s.id = c.section_id, q
                WHERE q.tsq IS NOT NULL AND c.tsv @@ q.tsq
                ORDER BY score DESC LIMIT %s""",
            (query, k),
        ).fetchall()
    hits = []
    for r in rows:
        h = _hit(r)
        h.score = float(r["score"])
        hits.append(h)
    return hits


def bm25_search(query: str, k: int) -> list[Hit]:
    ranked = bm25.index().search(bm25.query_terms(query), k)
    if not ranked:
        return []
    with get_pool().connection() as conn:
        rows = conn.execute(
            f"""SELECT {CHUNK_COLS} FROM chunks c JOIN sections s ON s.id = c.section_id
                WHERE c.id = ANY(%s)""",
            ([cid for cid, _ in ranked],),
        ).fetchall()
    by_id = {r["id"]: r for r in rows}
    hits = []
    for cid, sc in ranked:
        h = _hit(by_id[cid])
        h.score = sc
        hits.append(h)
    return hits


def rrf_fuse(result_lists: dict[str, list[Hit]], rrf_k: int) -> list[Hit]:
    fused: dict[str, Hit] = {}
    for name, hits in result_lists.items():
        for rank, h in enumerate(hits, start=1):
            cur = fused.setdefault(h.id, h)
            cur.ranks[name] = rank
    for h in fused.values():
        h.score = sum(1.0 / (rrf_k + r) for r in h.ranks.values())
    return sorted(fused.values(), key=lambda h: h.score, reverse=True)


def retrieve(query: str, mode: Mode = "hybrid_rerank", top_k: int | None = None) -> RetrievalResult:
    s = get_settings()
    top_k = top_k or s.top_k
    timings: dict[str, float] = {}

    def timed(name, fn, *args):
        t0 = time.perf_counter()
        out = fn(*args)
        timings[name] = round((time.perf_counter() - t0) * 1000, 1)
        return out

    if mode == "vector":
        return RetrievalResult(timed("vector", vector_search, query, top_k), timings)
    if mode == "fts":
        return RetrievalResult(timed("fts", fts_search, query, top_k), timings)
    if mode == "bm25":
        return RetrievalResult(timed("bm25", bm25_search, query, top_k), timings)

    lists = {
        "vector": timed("vector", vector_search, query, s.candidates),
        "bm25": timed("bm25", bm25_search, query, s.candidates),
    }
    fused = rrf_fuse(lists, s.rrf_k)
    if mode == "hybrid":
        return RetrievalResult(fused[:top_k], timings)

    def rerank(hits: list[Hit]) -> list[Hit]:
        # Final order = RRF of cross-encoder rank and hybrid rank. Reranker-only
        # ordering lost recall: it can override vector+BM25 agreement on lay-language
        # questions. See eval/results/rerank_experiment.md.
        scores = rerank_scores(query, [f"{h.header}\n{h.content}" for h in hits])
        by_ce = sorted(range(len(hits)), key=lambda i: scores[i], reverse=True)
        for ce_rank, i in enumerate(by_ce, start=1):
            h = hits[i]
            h.ranks["fused"] = i + 1
            h.ranks["rerank"] = ce_rank
            h.score = 1 / (s.rrf_k + ce_rank) + 1 / (s.rrf_k + i + 1)
        return sorted(hits, key=lambda h: h.score, reverse=True)

    reranked = timed("rerank", rerank, fused[: s.rerank_candidates])
    return RetrievalResult((reranked + fused[s.rerank_candidates :])[:top_k], timings)


def dedupe_sections(hits: list[Hit]) -> list[str]:
    """Ordered unique section ids — the unit we evaluate recall on."""
    seen: list[str] = []
    for h in hits:
        if h.section_id not in seen:
            seen.append(h.section_id)
    return seen


def section_context(hits: list[Hit]) -> list[Hit]:
    """Small-to-big: turn ranked chunks into whole-section context for the LLM.

    Chunks are precise to retrieve but can cut a section mid-list (e.g. s.7's
    "employment" clause lives in a later chunk than its preamble). Sections are
    taken in rank order of their best chunk. Each gets its full text if it fits
    the budget; long sections (e.g. CPA definitions) get only their retrieved
    chunks plus immediate neighbours, in document order.
    """
    s = get_settings()
    order = dedupe_sections(hits)[: s.context_sections]
    if not order:
        return []
    matched: dict[str, set[int]] = {}
    for h in hits:
        matched.setdefault(h.section_id, set()).add(h.chunk_index)
    best = {sid: next(h for h in hits if h.section_id == sid) for sid in order}

    with get_pool().connection() as conn:
        sections = {r["id"]: r for r in conn.execute("SELECT id, text FROM sections WHERE id = ANY(%s)", (order,))}
        chunk_rows = conn.execute(
            "SELECT section_id, chunk_index, content FROM chunks WHERE section_id = ANY(%s) ORDER BY section_id, chunk_index",
            (order,),
        ).fetchall()
    chunks: dict[str, dict[int, str]] = {}
    for r in chunk_rows:
        chunks.setdefault(r["section_id"], {})[r["chunk_index"]] = r["content"]

    out: list[Hit] = []
    budget = s.context_char_budget
    for i, sid in enumerate(order):
        top = best[sid]
        full = sections[sid]["text"]
        n_chunks = len(chunks[sid])
        # Leave room for the remaining sections' best chunks.
        reserve = sum(len(best[o].content) for o in order[i + 1 :])
        if len(full) <= budget - reserve:
            content = full
        else:
            want = sorted({j + d for j in matched[sid] for d in (-1, 0, 1) if 0 <= j + d < n_chunks})
            content = "\n…\n".join(chunks[sid][j] for j in want)
            if len(content) > budget - reserve:
                content = top.content
        budget -= len(content)
        header = top.header.split(" (part ")[0]
        out.append(Hit(**{**top.__dict__, "id": sid, "header": header, "content": content, "ranks": dict(top.ranks)}))
    return out
