"""Vocabulary CRUD router — uses ProviderManager for enrichment."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import CurrentUser, DBSession
from app.schemas.vocabulary import (
    EnrichOut, EnrichRequest,
    VocabOut, VocabStatusUpdate, VocabUpsertRequest,
)
from app.services import vocab_service

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary"])


class ManualMeaningUpdate(BaseModel):
    translation:      str
    phonetic:         str | None = None
    explanation:      str | None = None
    example_sentence: str | None = None


class ManualAddWord(BaseModel):
    word:             str
    source_lang:      str = "fr"
    target_lang:      str = "en"
    translation:      str = ""
    phonetic:         str | None = None
    explanation:      str | None = None
    example_sentence: str | None = None
    movie_id:         int | None = None
    book_id:          int | None = None


@router.get("", response_model=list[VocabOut], summary="List vocabulary for the current user")
def list_vocab(
    current_user: CurrentUser,
    db:           DBSession,
    target_lang:  Optional[str] = Query(None),
    status:       Optional[str] = Query(None),
):
    return vocab_service.list_vocab(db, current_user, target_lang, status)


@router.post("", response_model=VocabOut, summary="Add or update a vocabulary entry")
def upsert_vocab(body: VocabUpsertRequest, current_user: CurrentUser, db: DBSession):
    return vocab_service.upsert_vocab(db, current_user, body)


@router.patch("/{vocab_id}/status", response_model=VocabOut, summary="Update entry status")
def update_status(vocab_id: int, body: VocabStatusUpdate, current_user: CurrentUser, db: DBSession):
    return vocab_service.update_status(db, current_user, vocab_id, body.status)


@router.delete("/{vocab_id}", status_code=204, summary="Delete a vocabulary entry")
def delete_vocab(vocab_id: int, current_user: CurrentUser, db: DBSession):
    vocab_service.delete_vocab(db, current_user, vocab_id)


@router.patch("/{vocab_id}/meaning", summary="Manually update translation/meaning")
def update_meaning(vocab_id: int, body: ManualMeaningUpdate, current_user: CurrentUser, db: DBSession):
    from app.models.vocabulary import VocabEntry
    entry = db.query(VocabEntry).filter(
        VocabEntry.id == vocab_id, VocabEntry.user_id == current_user.id
    ).first()
    if not entry:
        raise HTTPException(404, "Vocabulary entry not found")
    entry.translation = body.translation
    if body.phonetic is not None:
        entry.phonetic = body.phonetic
    if body.explanation is not None:
        entry.explanation = body.explanation
    if body.example_sentence is not None:
        entry.example_sentence = body.example_sentence
    # Also update UserVocab table
    try:
        from app.models.user_vocab import UserVocab
        uv = db.query(UserVocab).filter(
            UserVocab.user_id == current_user.id,
            UserVocab.lemma == (entry.lemma or entry.word),
        ).first()
        if uv:
            uv.translation = body.translation
            if body.phonetic:
                uv.ipa = body.phonetic
            if body.explanation:
                uv.definition = body.explanation
            if body.example_sentence:
                uv.example = body.example_sentence
    except Exception:
        pass
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "word": entry.word, "translation": entry.translation, "ok": True}


@router.post("/manual-add", summary="Manually add a word with meaning")
def manual_add_word(body: ManualAddWord, current_user: CurrentUser, db: DBSession):
    from app.models.vocabulary import VocabEntry
    word = body.word.lower().strip()
    if not word:
        raise HTTPException(400, "Word is required")
    # Check duplicate
    existing = db.query(VocabEntry).filter(
        VocabEntry.user_id == current_user.id,
        VocabEntry.word == word,
        VocabEntry.target_lang == body.target_lang,
    ).first()
    if existing:
        # Update meaning if provided
        if body.translation:
            existing.translation = body.translation
        if body.phonetic:
            existing.phonetic = body.phonetic
        if body.explanation:
            existing.explanation = body.explanation
        if body.example_sentence:
            existing.example_sentence = body.example_sentence
        db.commit()
        return {"id": existing.id, "word": existing.word, "status": "updated"}

    entry = VocabEntry(
        user_id=current_user.id,
        word=word, lemma=word,
        source_lang=body.source_lang, target_lang=body.target_lang,
        translation=body.translation,
        phonetic=body.phonetic or "",
        explanation=body.explanation or "",
        example_sentence=body.example_sentence or "",
        status="new", count=1,
        movie_id=body.movie_id, book_id=body.book_id,
        contexts="[]", timestamps="[]",
    )
    db.add(entry)
    db.flush()
    # Auto-enrich if no translation provided
    if not body.translation:
        try:
            from app.providers.manager import provider_manager
            result = provider_manager.enrich_word(word, word, "", body.source_lang, body.target_lang)
            entry.translation = result.get("translation", "")
            entry.phonetic    = result.get("phonetic", "")
            entry.explanation = result.get("explanation", "")
        except Exception:
            pass
    db.commit()
    # Sync to UserVocab
    try:
        from app.services.user_vocab_service import sync_to_user_vocab
        sync_to_user_vocab(
            db=db, user_id=current_user.id, lang_code=body.source_lang,
            vocab_items=[{"word": word, "translation": entry.translation or "",
                          "phonetic": entry.phonetic or "", "explanation": entry.explanation or "",
                          "count": 1, "contexts": [], "timestamps": []}],
            movie_id=body.movie_id, book_id=body.book_id,
        )
    except Exception:
        pass
    return {"id": entry.id, "word": entry.word, "translation": entry.translation, "status": "created"}


@router.post("/enrich", response_model=EnrichOut, summary="Enrich a word (Groq → Gemini → Ollama → offline)")
def enrich_word(body: EnrichRequest, current_user: CurrentUser, db: DBSession):
    from app.providers.manager import provider_manager
    result = provider_manager.enrich_word(
        word=body.word,
        lemma=body.word,
        context=body.sentence,
        source_lang=body.target_lang,   # word is in target lang
        target_lang=body.source_lang,   # translate TO source lang
    )
    # Persist enrichment back to DB
    from app.models.vocabulary import VocabEntry
    entry = (
        db.query(VocabEntry)
        .filter(
            VocabEntry.user_id     == current_user.id,
            VocabEntry.word        == body.word.lower().strip(),
            VocabEntry.target_lang == body.target_lang,
        )
        .first()
    )
    if entry:
        entry.translation = result.get("translation")
        entry.pos         = result.get("partOfSpeech")
        entry.phonetic    = result.get("phonetic")
        entry.explanation = result.get("explanation")
        db.commit()

    return {
        "translation":          result.get("translation", ""),
        "pos":                  result.get("partOfSpeech", "Noun"),
        "phonetic":             result.get("phonetic", ""),
        "explanation":          result.get("explanation", ""),
        "sentence_translation": result.get("sentenceTranslation", ""),
        "provider":             result.get("provider", ""),
    }
