"""PostgreSQL + pgvector store for subtitle and vocabulary embeddings."""
from __future__ import annotations

import asyncpg
from pgvector.asyncpg import register_vector
from app.config import get_settings

settings = get_settings()


async def _conn() -> asyncpg.Connection:
    conn = await asyncpg.connect(settings.postgres_url)
    await register_vector(conn)
    return conn


# ── Subtitle embeddings ───────────────────────────────────────────────────────

async def upsert_subtitle_embeddings(
    rows: list[dict],
    user_id: int | None = None,
    movie_title: str = "",
    source_lang: str = "en",
    target_lang: str = "fr",
) -> int:
    """
    rows: list of {index, start, end, original, translation, embedding}
    Returns number of rows inserted.
    """
    if not rows:
        return 0

    conn = await _conn()
    try:
        await conn.executemany(
            """
            INSERT INTO subtitle_embeddings
                (user_id, movie_title, subtitle_index, start_time, end_time,
                 original, translation, source_lang, target_lang, embedding)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    user_id, movie_title,
                    r["index"], r["start"], r["end"],
                    r["original"], r.get("translation"),
                    source_lang, target_lang,
                    r["embedding"],
                )
                for r in rows
            ],
        )
        return len(rows)
    finally:
        await conn.close()


async def search_similar_subtitles(
    query_embedding: list[float],
    target_lang: str = "fr",
    user_id: int | None = None,
    top_k: int = 10,
) -> list[dict]:
    """Cosine similarity search over subtitle_embeddings."""
    conn = await _conn()
    try:
        filters = ["target_lang = $2"]
        params: list = [query_embedding, target_lang]
        if user_id:
            params.append(user_id)
            filters.append(f"user_id = ${len(params)}")

        where = " AND ".join(filters)
        rows = await conn.fetch(
            f"""
            SELECT subtitle_index, start_time, end_time, original, translation,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM subtitle_embeddings
            WHERE {where}
            ORDER BY embedding <=> $1::vector
            LIMIT {top_k}
            """,
            *params,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


# ── Vocabulary embeddings ─────────────────────────────────────────────────────

async def upsert_vocab_embeddings(
    words: list[dict],
    user_id: int | None = None,
    target_lang: str = "fr",
) -> int:
    """words: list of {word, translation, explanation, embedding}"""
    if not words:
        return 0

    conn = await _conn()
    try:
        await conn.executemany(
            """
            INSERT INTO vocab_embeddings
                (user_id, word, translation, explanation, target_lang, embedding)
            VALUES ($1,$2,$3,$4,$5,$6)
            ON CONFLICT DO NOTHING
            """,
            [
                (
                    user_id, w["word"], w.get("translation"),
                    w.get("explanation"), target_lang, w["embedding"],
                )
                for w in words
            ],
        )
        return len(words)
    finally:
        await conn.close()


async def find_similar_words(
    query_embedding: list[float],
    target_lang: str = "fr",
    user_id: int | None = None,
    top_k: int = 5,
) -> list[dict]:
    conn = await _conn()
    try:
        params: list = [query_embedding, target_lang]
        user_filter = ""
        if user_id:
            params.append(user_id)
            user_filter = f"AND user_id = ${len(params)}"

        rows = await conn.fetch(
            f"""
            SELECT word, translation, explanation,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM vocab_embeddings
            WHERE target_lang = $2 {user_filter}
            ORDER BY embedding <=> $1::vector
            LIMIT {top_k}
            """,
            *params,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()
