-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Subtitle embeddings for semantic search
CREATE TABLE IF NOT EXISTS subtitle_embeddings (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER,
    movie_title TEXT,
    subtitle_index INTEGER,
    start_time  TEXT,
    end_time    TEXT,
    original    TEXT NOT NULL,
    translation TEXT,
    source_lang TEXT NOT NULL DEFAULT 'en',
    target_lang TEXT NOT NULL DEFAULT 'fr',
    embedding   vector(768),         -- nomic-embed-text dim; change for other models
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Vocabulary embeddings for semantic similarity
CREATE TABLE IF NOT EXISTS vocab_embeddings (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER,
    word        TEXT NOT NULL,
    translation TEXT,
    explanation TEXT,
    target_lang TEXT NOT NULL,
    embedding   vector(768),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- LangGraph checkpoints (persists agent state across sessions)
CREATE TABLE IF NOT EXISTS langgraph_checkpoints (
    thread_id   TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type        TEXT,
    checkpoint  BYTEA,
    metadata    BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS langgraph_checkpoint_blobs (
    thread_id   TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel     TEXT NOT NULL,
    version     TEXT NOT NULL,
    type        TEXT NOT NULL,
    blob        BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS langgraph_checkpoint_writes (
    thread_id   TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id     TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    channel     TEXT NOT NULL,
    type        TEXT,
    blob        BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Indexes for vector similarity search (IVFFlat — fast approximate)
CREATE INDEX IF NOT EXISTS idx_subtitle_emb_vec
    ON subtitle_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_vocab_emb_vec
    ON vocab_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- Indexes for filtering
CREATE INDEX IF NOT EXISTS idx_subtitle_emb_user   ON subtitle_embeddings (user_id);
CREATE INDEX IF NOT EXISTS idx_subtitle_emb_langs  ON subtitle_embeddings (source_lang, target_lang);
CREATE INDEX IF NOT EXISTS idx_vocab_emb_user_lang ON vocab_embeddings (user_id, target_lang);
