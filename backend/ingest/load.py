"""Chunk parsed sections, embed them, and load everything into Postgres.

Idempotent: tables are truncated and rebuilt on every run.
"""

import json
import time
from pathlib import Path

from app.db import get_pool
from app.models import embed_passages
from ingest.chunk import chunk_section

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    sections = [json.loads(l) for l in (ROOT / "data/processed/sections.jsonl").open()]
    chunks = [c for s in sections for c in chunk_section(s)]
    print(f"{len(sections)} sections -> {len(chunks)} chunks")

    t0 = time.perf_counter()
    vectors = embed_passages([f"{c.header}\n{c.content}" for c in chunks])
    print(f"embedded in {time.perf_counter() - t0:.1f}s")

    with get_pool().connection() as conn:
        conn.execute((ROOT / "sql/schema.sql").read_text())
        conn.execute("TRUNCATE sections CASCADE")
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO sections (id, act_id, act_name, act_short, section, title, chapter, page, source_url, text)
                   VALUES (%(id)s, %(act_id)s, %(act_name)s, %(act_short)s, %(section)s, %(title)s,
                           %(chapter)s, %(page)s, %(source_url)s, %(text)s)""",
                sections,
            )
            cur.executemany(
                """INSERT INTO chunks (id, section_id, act_id, chunk_index, header, content, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [(c.id, c.section_id, c.act_id, c.chunk_index, c.header, c.content, v) for c, v in zip(chunks, vectors)],
            )
        conn.execute("ANALYZE chunks")
    print("loaded into Postgres")


if __name__ == "__main__":
    main()
