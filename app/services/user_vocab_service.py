"""
Sync vocabulary from VocabEntry (movie/book) → UserVocab (SM-2 study table).

Called after every movie subtitle analysis or book upload so that
all new words immediately appear in the user's study queue.
"""
from __future__ import annotations
import logging
from sqlalchemy.orm import Session

from app.models.user_vocab import UserVocab
from app.models.deck import Deck, DeckWord

log = logging.getLogger(__name__)


def sync_to_user_vocab(
    db:           Session,
    user_id:      int,
    lang_code:    str,
    vocab_items:  list[dict],   # enriched word dicts
    source_title: str = "",     # movie title OR book title
    movie_id:     int | None = None,
    book_id:      int | None = None,
) -> int:
    """
    Upsert each word into UserVocab (the SM-2 study table).
    New words get status="new" and join the study queue.
    Existing words are updated with better enrichment if missing.
    Returns count of newly inserted rows.
    """
    saved = 0
    for item in vocab_items:
        lemma = (item.get("lemma") or item.get("word", "")).lower().strip()
        if not lemma or len(lemma) < 2:
            continue

        existing = (
            db.query(UserVocab)
            .filter(
                UserVocab.user_id  == user_id,
                UserVocab.lang_code == lang_code,
                UserVocab.lemma    == lemma,
            )
            .first()
        )

        if existing:
            # Fill in any missing enrichment
            if not existing.translation and item.get("translation"):
                existing.translation = item["translation"]
            if not existing.ipa and (item.get("ipa") or item.get("phonetic")):
                existing.ipa = item.get("ipa") or item.get("phonetic")
            if not existing.definition and (item.get("mnemonic") or item.get("explanation")):
                existing.definition = item.get("mnemonic") or item.get("explanation")
            if not existing.example and item.get("example"):
                existing.example = item["example"]
            if not existing.context_sentence and item.get("example"):
                existing.context_sentence = item["example"]
            # Link to source if not already linked
            if movie_id and not existing.movie_id:
                existing.movie_id    = movie_id
                existing.source_movie = source_title
            if book_id and not existing.book_id:
                existing.book_id    = book_id
                existing.source_book = source_title
        else:
            uv = UserVocab(
                user_id=user_id,
                lang_code=lang_code,
                word=item.get("word", lemma),
                lemma=lemma,
                pos=item.get("pos") or item.get("partOfSpeech", "Noun"),
                cefr=item.get("cefr") or item.get("cefrLevel", "B1"),
                frequency_zipf=float(item.get("zipf", 0.0)),
                translation=item.get("translation", ""),
                ipa=item.get("ipa") or item.get("phonetic", ""),
                definition=item.get("mnemonic") or item.get("explanation", ""),
                example=item.get("example", ""),
                context_sentence=item.get("example", ""),
                source_movie=source_title if movie_id else None,
                source_book=source_title if book_id else None,
                movie_id=movie_id,
                book_id=book_id,
                status="new",
            )
            db.add(uv)
            saved += 1

    db.flush()

    # Auto-create a named study deck for this source
    if source_title and (movie_id or book_id):
        _ensure_source_deck(db, user_id, lang_code, source_title, movie_id, book_id, vocab_items)

    db.commit()
    log.info("sync_to_user_vocab: %d new words added for %r", saved, source_title)
    return saved


def _ensure_source_deck(
    db, user_id, lang_code, source_title, movie_id, book_id, vocab_items
):
    """Create (or update) a deck named after the movie/book."""
    deck_type = "movie" if movie_id else "book"
    deck = (
        db.query(Deck)
        .filter(
            Deck.user_id     == user_id,
            Deck.lang_code   == lang_code,
            Deck.movie_title == source_title,
            Deck.deck_type   == deck_type,
        )
        .first()
    )
    if not deck:
        deck = Deck(
            user_id=user_id,
            lang_code=lang_code,
            deck_type=deck_type,
            name=source_title,
            description=f"Vocabulary from {'🎬' if movie_id else '📖'} {source_title}",
            movie_title=source_title,
        )
        db.add(deck)
        db.flush()

    # Link all words from this source into the deck
    for item in vocab_items:
        lemma = (item.get("lemma") or item.get("word", "")).lower().strip()
        if not lemma:
            continue
        uv = (
            db.query(UserVocab)
            .filter(UserVocab.user_id == user_id, UserVocab.lang_code == lang_code, UserVocab.lemma == lemma)
            .first()
        )
        if not uv:
            continue
        already = db.query(DeckWord).filter(
            DeckWord.deck_id == deck.id, DeckWord.user_vocab_id == uv.id
        ).first()
        if not already:
            db.add(DeckWord(deck_id=deck.id, user_vocab_id=uv.id))

    deck.word_count = db.query(DeckWord).filter(DeckWord.deck_id == deck.id).count()
    db.flush()
