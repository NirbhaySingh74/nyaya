CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sections (
    id          text PRIMARY KEY,          -- e.g. "dpdp-6", "rti-second-schedule"
    act_id      text NOT NULL,
    act_name    text NOT NULL,
    act_short   text NOT NULL,
    section     text NOT NULL,             -- "6", "Second Schedule"
    title       text NOT NULL,
    chapter     text NOT NULL,
    page        int  NOT NULL,
    source_url  text NOT NULL,
    text        text NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    id          text PRIMARY KEY,          -- "<section_id>#<n>"
    section_id  text NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    act_id      text NOT NULL,
    chunk_index int  NOT NULL,
    header      text NOT NULL,             -- "DPDP Act, 2023 — Section 6: Consent"
    content     text NOT NULL,
    embedding   vector(768) NOT NULL,
    -- Header is weighted higher so "section 6 consent" style queries hit titles.
    tsv tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('english', header), 'A') ||
        setweight(to_tsvector('english', content), 'B')
    ) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_gin ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_section_idx ON chunks (section_id);
