"""
Subtitle translation + vocabulary extraction router.

Pipeline (LangGraph workflow):
  Translation Agent  → deep-translator → Groq → Gemini → Ollama → offline echo
  Vocabulary Agent   → spaCy NLP pipeline
  Enrichment Agent   → ProviderManager (Groq → Gemini → Ollama → offline dict)
  CEFR Agent         → wordfreq Zipf scores
  Idiom Agent        → offline dictionary + provider
  Grammar Agent      → rule-based pattern detection
  Scene Agent        → rule-based scene summary
  Quiz Agent         → template-based questions

The app NEVER fails — every agent has a fallback chain.
"""
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter

from app.dependencies import DBSession, OptionalCurrentUser
from app.schemas.subtitle import TranslateRequest, TranslateResponse, VocabItem, TranslatedFrame
from app.services import vocab_service
from app.core.exceptions import ServiceUnavailableError

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/translations", tags=["Translations"])

_MAX_ENRICH = 12


# ── Main endpoint ─────────────────────────────────────────────────────────────

@router.post("", response_model=TranslateResponse, summary="Translate subtitles + extract vocabulary")
def translate_subtitles(body: TranslateRequest, db: DBSession, current_user: OptionalCurrentUser):
    subs = body.subtitles[:150]
    src  = body.source_lang
    tgt  = body.target_lang

    # Build blocks for the pipeline
    blocks = [{"index": s.index, "text": s.text, "start": s.start, "end": s.end} for s in subs]

    # ── Step 1: Run LangGraph workflow (or sequential fallback) ───────────────
    try:
        from app.agents.workflow import run_pipeline
        state = run_pipeline(
            subtitle_blocks=blocks,
            source_lang=src,
            target_lang=tgt,
            movie_title="",
        )
        translated  = state.get("translated_blocks", [])
        raw_vocab   = state.get("raw_vocab", [])
        enriched    = state.get("enriched_vocab", [])
        errors      = state.get("errors", [])
        if errors:
            log.warning("Pipeline errors: %s", errors)
    except Exception as exc:
        log.error("Workflow failed, running manual fallback: %s", exc)
        translated, raw_vocab, enriched = _manual_pipeline(blocks, src, tgt)

    # ── Step 2: If no vocab yet, extract directly from source text ───────────────
    if not raw_vocab and not enriched:
        from app.services.nlp.pipeline import extract_vocabulary
        source_text = " ".join(b["text"] for b in blocks)
        raw_vocab = extract_vocabulary(source_text, lang_code=src, source_frames=blocks)
        log.info("Extracted %d words from source text (lang=%s)", len(raw_vocab), src)

    # ── Step 3: Enrich raw vocab if not yet enriched ──────────────────────────
    if not enriched and raw_vocab:
        enriched = _enrich_batch(raw_vocab, src, tgt)
    final_vocab = enriched or raw_vocab

    # ── Step 3: Persist to DB (with movie folder) ────────────────────────────
    if current_user and final_vocab:
        try:
            movie_title = getattr(body, "movie_title", "") or ""
            movie_id = _upsert_movie(db, current_user.id, movie_title, src, tgt, len(blocks))
            _bulk_upsert_with_movie(db, current_user, _to_legacy(final_vocab), src, tgt, movie_id, movie_title)
            if movie_id:
                _update_movie_cefr(db, movie_id, final_vocab, current_user.id)
            # Sync into UserVocab (SM-2 study table) + auto-create study deck
            try:
                from app.services.user_vocab_service import sync_to_user_vocab
                sync_to_user_vocab(
                    db=db, user_id=current_user.id, lang_code=src,
                    vocab_items=_to_legacy(final_vocab),
                    source_title=movie_title, movie_id=movie_id,
                )
            except Exception as exc:
                log.warning("sync_to_user_vocab (movie) failed: %s", exc)
        except Exception as exc:
            log.warning("vocab persist failed: %s", exc)

    # ── Step 4: Build response ────────────────────────────────────────────────
    vocab_items = [
        VocabItem(
            word=v.get("word", ""),
            translation=v.get("translation", ""),
            pos=v.get("partOfSpeech") or v.get("pos", "Noun"),
            phonetic=v.get("phonetic", ""),
            explanation=v.get("explanation", ""),
            example=v.get("exampleSentence") or v.get("example", ""),
            count=v.get("count", 1),
            contexts=[c.get("text", c) if isinstance(c, dict) else c for c in v.get("contexts", [])],
            timestamps=[c.get("timestamp", "") if isinstance(c, dict) else "" for c in v.get("contexts", [])],
            source_lang=src,
            target_lang=tgt,
        )
        for v in final_vocab
    ]

    return TranslateResponse(
        translated=[
            TranslatedFrame(
                index=t.get("index", 0),
                start=t.get("start", ""),
                end=t.get("end", ""),
                original=t.get("original", t.get("text", "")),
                text=t.get("text", ""),
            )
            for t in translated
        ],
        vocabulary=vocab_items,
        source_lang=src,
        target_lang=tgt,
        subtitle_count=len(translated),
        vocab_count=len(vocab_items),
    )


# ── Provider status endpoint ───────────────────────────────────────────────────

@router.get("/providers", summary="Check AI provider availability")
def provider_status():
    from app.providers.manager import provider_manager
    from app.cache.redis_cache import is_healthy as redis_healthy
    return {
        "providers": provider_manager.status(),
        "redis": redis_healthy(),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _manual_pipeline(blocks, src, tgt):
    """Sequential fallback when LangGraph is unavailable."""
    # Translation
    from app.providers.manager import provider_manager
    tr = provider_manager.translate_batch(blocks, src, tgt)
    tmap = {t["index"]: t["text"] for t in tr.translations}
    translated = [
        {
            "index": b["index"], "start": b.get("start", ""),
            "end": b.get("end", ""), "original": b["text"],
            "text": tmap.get(b["index"], b["text"]),
        }
        for b in blocks
    ]
    # Vocabulary — extract from source language text (more reliable than translated)
    from app.services.nlp.pipeline import extract_vocabulary
    source_text = " ".join(b["text"] for b in blocks)
    raw_vocab = extract_vocabulary(source_text, lang_code=src, source_frames=blocks)
    if not raw_vocab:
        # fallback: try extracting from translated text
        full_text = " ".join(t["text"] for t in translated)
        raw_vocab = extract_vocabulary(full_text, lang_code=tgt, source_frames=translated)
    # Enrichment
    enriched  = _enrich_batch(raw_vocab, tgt, src)
    return translated, raw_vocab, enriched


def _enrich_batch(vocab: list[dict], word_lang: str, translate_to: str) -> list[dict]:
    """Parallel enrichment via ProviderManager — capped at _MAX_ENRICH words."""
    from app.providers.manager import provider_manager

    top  = vocab[:_MAX_ENRICH]
    rest = vocab[_MAX_ENRICH:]
    out  = {}

    with ThreadPoolExecutor(max_workers=min(len(top), 6)) as pool:
        futures = {
            pool.submit(
                provider_manager.enrich_word,
                v.get("word", ""),
                v.get("lemma", v.get("word", "")),
                v.get("example", ""),
                word_lang,
                translate_to,
            ): i
            for i, v in enumerate(top)
        }
        for future in as_completed(futures, timeout=12):
            idx = futures[future]
            try:
                result = future.result()
                out[idx] = result
            except Exception:
                out[idx] = {}

    enriched = []
    for i, v in enumerate(top):
        patch = out.get(i, {})
        enriched.append({**v, **patch, "word": v["word"], "lemma": v.get("lemma", v["word"])})
    enriched.extend(rest)
    return enriched


def _upsert_movie(db, user_id: int, title: str, lang: str, target_lang: str, sub_count: int):
    """Create or update a Movie record; return its id (or None if no title)."""
    if not title or not title.strip():
        return None
    from app.models.movie import Movie
    movie = (
        db.query(Movie)
        .filter(Movie.user_id == user_id, Movie.title == title.strip(), Movie.language == lang)
        .first()
    )
    if movie:
        movie.subtitle_count += sub_count
        movie.target_lang = target_lang
    else:
        movie = Movie(
            user_id=user_id, title=title.strip(),
            language=lang, target_lang=target_lang,
            subtitle_count=sub_count,
        )
        db.add(movie)
    db.flush()
    return movie.id


def _bulk_upsert_with_movie(db, user, items, source_lang, target_lang, movie_id, movie_title):
    """Like vocab_service.bulk_upsert but also sets movie_id/source_movie."""
    import json as _json
    from app.models.vocabulary import VocabEntry
    saved = 0
    for v in items:
        word = (v.get("word") or "").lower().strip()
        if not word:
            continue
        entry = (
            db.query(VocabEntry)
            .filter(VocabEntry.user_id == user.id, VocabEntry.word == word, VocabEntry.target_lang == target_lang)
            .first()
        )
        ctx = v.get("example") or (v.get("contexts") or [""])[0]
        if entry:
            entry.count += v.get("count", 1)
            if movie_id and not entry.movie_id:
                entry.movie_id    = movie_id
                entry.source_movie = movie_title
            if v.get("translation") and not entry.translation:
                entry.translation = v["translation"]
            existing = _json.loads(entry.contexts or "[]")
            if ctx and ctx not in existing:
                existing.insert(0, ctx)
                entry.contexts = _json.dumps(existing[:5])
        else:
            db.add(VocabEntry(
                user_id=user.id, word=word,
                source_lang=source_lang, target_lang=target_lang,
                translation=v.get("translation", ""),
                pos=v.get("pos", ""),
                phonetic=v.get("phonetic", ""),
                explanation=v.get("explanation", ""),
                example_sentence=v.get("example", ""),
                status="new", count=v.get("count", 1),
                movie_id=movie_id, source_movie=movie_title or None,
                contexts=_json.dumps([ctx] if ctx else []),
                timestamps=_json.dumps([]),
            ))
            saved += 1
    db.commit()
    return saved


def _update_movie_cefr(db, movie_id: int, vocab: list[dict], user_id: int):
    """Recalculate and store CEFR breakdown on the movie record."""
    import json as _json
    from app.models.movie import Movie
    from app.models.vocabulary import VocabEntry
    from app.services.nlp.pipeline import _zipf_to_cefr
    breakdown: dict[str, int] = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}
    entries = (
        db.query(VocabEntry)
        .filter(VocabEntry.movie_id == movie_id, VocabEntry.user_id == user_id)
        .all()
    )
    for e in entries:
        lvl = e.cefr_level or "B1"
        breakdown[lvl] = breakdown.get(lvl, 0) + 1
    movie = db.get(Movie, movie_id)
    if movie:
        movie.cefr_json   = _json.dumps(breakdown)
        movie.vocab_count = sum(breakdown.values())
        db.commit()


def _to_legacy(vocab: list[dict]) -> list[dict]:
    """Convert enriched vocab to the format expected by vocab_service.bulk_upsert."""
    return [
        {
            "word":        v.get("word", ""),
            "translation": v.get("translation", ""),
            "pos":         v.get("partOfSpeech") or v.get("pos", "Noun"),
            "phonetic":    v.get("phonetic", ""),
            "explanation": v.get("explanation", ""),
            "example":     v.get("exampleSentence") or v.get("example", ""),
            "count":       v.get("count", 1),
            "contexts":    [c.get("text", c) if isinstance(c, dict) else c for c in v.get("contexts", [])],
            "timestamps":  [],
        }
        for v in vocab
    ]
