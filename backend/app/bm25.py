"""Okapi BM25 over the chunks table.

Postgres full-text ranking (ts_rank_cd) has no IDF, so a chunk matching common
words ("act", "section") scores like one matching rare, decisive terms
("adulterant", "endorser"). This computes real BM25 using the lexemes Postgres
already stores in `chunks.tsv`, so stemming/stopwords match the FTS config.
Terms from the chunk header (weight 'A') count double: a light BM25F.

The index is tiny (hundreds of chunks) and built in memory once per process.
For a large corpus, swap this for ParadeDB pg_search or a dedicated engine.
"""

import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache

from app.db import get_pool

K1, B = 1.2, 0.75
HEADER_BOOST = 2


@dataclass
class BM25Index:
    postings: dict[str, list[tuple[str, float]]]  # lexeme -> [(chunk_id, tf)]
    doc_len: dict[str, float]
    avg_len: float

    def idf(self, term: str) -> float:
        n, df = len(self.doc_len), len(self.postings.get(term, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, terms: list[str], k: int) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for term in set(terms):
            idf = self.idf(term)
            for doc, tf in self.postings.get(term, ()):
                norm = K1 * (1 - B + B * self.doc_len[doc] / self.avg_len)
                scores[doc] += idf * tf * (K1 + 1) / (tf + norm)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]


@lru_cache
def index() -> BM25Index:
    with get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT c.id, t.lexeme, t.weights FROM chunks c, unnest(c.tsv) AS t(lexeme, positions, weights)"
        ).fetchall()
    postings: dict[str, list[tuple[str, float]]] = defaultdict(list)
    doc_len: dict[str, float] = defaultdict(float)
    for r in rows:
        tf = sum(HEADER_BOOST if w == "A" else 1 for w in r["weights"])
        postings[r["lexeme"]].append((r["id"], tf))
        doc_len[r["id"]] += tf
    return BM25Index(dict(postings), dict(doc_len), sum(doc_len.values()) / max(len(doc_len), 1))


def query_terms(query: str) -> list[str]:
    with get_pool().connection() as conn:
        row = conn.execute(
            "SELECT tsvector_to_array(to_tsvector('english', %s)) AS terms", (query,)
        ).fetchone()
    return row["terms"] or []
