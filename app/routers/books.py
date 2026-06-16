"""
Book Library router — PDF/TXT upload → vocabulary extraction → saved as named book folders.

Endpoints:
  POST   /api/books/analyze      — analyze pasted text
  POST   /api/books/upload       — upload .txt or .pdf
  GET    /api/books              — list user's book library
  GET    /api/books/{id}/vocab   — vocabulary for a specific book
  DELETE /api/books/{id}         — remove book (vocab entries kept)
"""
from __future__ import annotations
import json
import logging
import re
from collections import Counter
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user, get_optional_user
from app.models.book import BookLibrary
from app.models.vocabulary import VocabEntry
from app.models.user import User

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/books", tags=["Books"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalyzeTextRequest(BaseModel):
    text:        str
    title:       str = "Untitled Book"
    author:      str = ""
    lang_code:   str = "fr"
    target_lang: str = "en"
    enrich_top:  int = 50

class WordEntry(BaseModel):
    word:        str
    lemma:       str
    pos:         str
    cefr:        str
    zipf:        float
    count:       int
    example:     str
    translation: str = ""
    ipa:         str = ""
    mnemonic:    str = ""

class BookOut(BaseModel):
    id:             int
    title:          str
    author:         str
    lang_code:      str
    total_words:    int
    unique_words:   int
    saved_count:    int
    cefr_breakdown: dict
    created_at:     str

class AnalyzeResponse(BaseModel):
    book_id:        int
    title:          str
    total_words:    int
    unique_words:   int
    cefr_breakdown: dict
    vocabulary:     list[WordEntry]
    saved_count:    int
    lang_code:      str

# ── Stop words ────────────────────────────────────────────────────────────────

_STOP_WORDS_FR = {
    "le","la","les","un","une","des","du","de","et","en","au","aux",
    "à","ce","se","sa","son","ses","mon","ma","mes","ton","ta","tes",
    "nous","vous","ils","elles","je","tu","il","elle","on","y","ne",
    "pas","plus","par","sur","sous","dans","avec","pour","que","qui",
    "qu","est","sont","était","être","avoir","avait","été","fait",
    "dit","va","très","bien","mais","car","si","ou","ni","donc",
    "or","tout","tous","toute","toutes","comme","même","aussi",
    "c","d","j","l","m","n","s","t",
}

# ── PDF extraction ────────────────────────────────────────────────────────────

def _extract_text_from_pdf(content: bytes) -> str:
    try:
        import pypdf, io
        reader = pypdf.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:
                pass
        return "\n".join(parts)
    except ImportError:
        raise HTTPException(400, "PDF support requires pypdf — run: pip install pypdf")
    except Exception as exc:
        raise HTTPException(400, f"Could not read PDF: {exc}")


def _clean_text(text: str) -> str:
    text = re.sub(r'\*{3}.*?\*{3}', '', text, flags=re.DOTALL)
    text = re.sub(r'[^\w\s\'\-àâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]', ' ', text, flags=re.IGNORECASE)
    return text


# ── NLP extraction ────────────────────────────────────────────────────────────

def _extract_book_vocab(text: str, lang_code: str, top_n: int = 300) -> list[dict]:
    from app.services.nlp.pipeline import _load_spacy, _zipf_to_cefr, _POS_DISPLAY

    cleaned   = _clean_text(text)
    MAX_CHUNK = 50_000
    chunks    = [cleaned[i:i + MAX_CHUNK] for i in range(0, min(len(cleaned), 500_000), MAX_CHUNK)]

    nlp = _load_spacy(lang_code)
    word_counts: Counter = Counter()
    word_meta: dict[str, dict] = {}

    if nlp:
        for chunk in chunks:
            doc = nlp(chunk)
            for token in doc:
                if (
                    token.is_alpha
                    and len(token.text) >= 3
                    and token.pos_ in ("NOUN", "VERB", "ADJ", "ADV")
                    and not token.is_stop
                    and token.lemma_.lower() not in _STOP_WORDS_FR
                    and token.ent_type_ not in ("PER", "ORG", "GPE", "LOC")
                ):
                    lemma = token.lemma_.lower()
                    word_counts[lemma] += 1
                    if lemma not in word_meta:
                        cefr, zipf = _zipf_to_cefr(lemma, lang_code)
                        word_meta[lemma] = {
                            "word":    token.text.lower(),
                            "lemma":   lemma,
                            "pos":     _POS_DISPLAY.get(token.pos_, token.pos_),
                            "cefr":    cefr,
                            "zipf":    round(zipf, 2),
                            "example": token.sent.text.strip()[:150] if token.sent else "",
                        }
    else:
        from wordfreq import zipf_frequency
        words = re.findall(r'\b[a-zA-ZàâäéèêëîïôùûüçœæÀÂÄÉÈÊËÎÏÔÙÛÜÇŒÆ]{3,}\b', cleaned)
        for w in words:
            lemma = w.lower()
            if lemma not in _STOP_WORDS_FR:
                word_counts[lemma] += 1
                if lemma not in word_meta:
                    cefr, zipf = _zipf_to_cefr(lemma, lang_code)
                    word_meta[lemma] = {
                        "word": lemma, "lemma": lemma,
                        "pos": "Unknown", "cefr": cefr, "zipf": round(zipf, 2), "example": "",
                    }

    result = []
    for lemma, count in word_counts.most_common(top_n * 3):
        if count < 2 or lemma not in word_meta:
            continue
        result.append({**word_meta[lemma], "count": count})
        if len(result) >= top_n:
            break
    return result


# ── DB save ───────────────────────────────────────────────────────────────────

def _save_book_vocab(db: Session, user_id: int, book: BookLibrary, vocab: list[dict], target_lang: str) -> int:
    saved = 0
    for v in vocab:
        word = (v.get("lemma") or v.get("word", "")).lower().strip()
        if not word:
            continue
        entry = (
            db.query(VocabEntry)
            .filter(
                VocabEntry.user_id    == user_id,
                VocabEntry.word       == word,
                VocabEntry.target_lang == target_lang,
            )
            .first()
        )
        ctx = v.get("example", "")
        if entry:
            entry.count += v.get("count", 1)
            if not entry.book_id:
                entry.book_id    = book.id
                entry.source_book = book.title
            if v.get("translation") and not entry.translation:
                entry.translation = v["translation"]
            if v.get("ipa") and not entry.phonetic:
                entry.phonetic = v["ipa"]
            if v.get("example") and not entry.example_sentence:
                entry.example_sentence = v["example"]
            if not entry.cefr_level:
                entry.cefr_level = v.get("cefr", "B1")
            existing = json.loads(entry.contexts or "[]")
            if ctx and ctx not in existing:
                existing.insert(0, ctx)
                entry.contexts = json.dumps(existing[:5])
        else:
            db.add(VocabEntry(
                user_id=user_id,
                word=word,
                lemma=v.get("lemma", word),
                source_lang=book.lang_code,
                target_lang=target_lang,
                translation=v.get("translation", ""),
                pos=v.get("pos", ""),
                phonetic=v.get("ipa", ""),
                explanation=v.get("mnemonic", ""),
                example_sentence=v.get("example", ""),
                cefr_level=v.get("cefr", "B1"),
                status="new",
                count=v.get("count", 1),
                book_id=book.id,
                source_book=book.title,
                contexts=json.dumps([ctx] if ctx else []),
                timestamps=json.dumps([]),
            ))
            saved += 1
    db.commit()
    return saved


# ── Shared analysis logic ─────────────────────────────────────────────────────

def _run_analysis(
    text: str, title: str, author: str,
    lang_code: str, target_lang: str, enrich_top: int,
    db: Session, user_id: Optional[int],
) -> AnalyzeResponse:
    if len(text.strip()) < 50:
        raise HTTPException(400, "Text too short — paste at least a paragraph.")

    vocab = _extract_book_vocab(text, lang_code, top_n=300)

    cefr_breakdown: dict[str, int] = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}
    for v in vocab:
        lvl = v.get("cefr", "B1")
        cefr_breakdown[lvl] = cefr_breakdown.get(lvl, 0) + 1

    # LangChain OpenAI agent enrichment
    enriched = vocab
    if user_id:
        top  = vocab[:enrich_top]
        rest = vocab[enrich_top:]
        try:
            from app.agents.book_agent import enrich_words_with_langchain
            enriched_top = enrich_words_with_langchain(top, lang_code, target_lang)
            enriched = enriched_top + rest
        except Exception as exc:
            log.warning("LangChain enrichment failed: %s", exc)

    # Persist book + vocab
    saved, book_id = 0, 0
    if user_id:
        book = BookLibrary(
            user_id=user_id,
            title=title,
            author=author,
            lang_code=lang_code,
            target_lang=target_lang,
            total_words=len(re.findall(r'\b\w{2,}\b', text)),
            unique_words=len(vocab),
            cefr_json=json.dumps(cefr_breakdown),
        )
        db.add(book)
        db.flush()
        saved = _save_book_vocab(db, user_id, book, enriched, target_lang)
        book.saved_count = saved
        db.commit()
        book_id = book.id

        # Sync into UserVocab (SM-2 study table) + auto-create study deck
        try:
            from app.services.user_vocab_service import sync_to_user_vocab
            sync_to_user_vocab(
                db=db, user_id=user_id, lang_code=lang_code,
                vocab_items=enriched, source_title=title,
                book_id=book_id,
            )
        except Exception as exc:
            log.warning("sync_to_user_vocab (book) failed: %s", exc)

    return AnalyzeResponse(
        book_id=book_id,
        title=title,
        total_words=len(re.findall(r'\b\w{2,}\b', text)),
        unique_words=len(vocab),
        cefr_breakdown=cefr_breakdown,
        vocabulary=[
            WordEntry(
                word=v.get("word", ""),
                lemma=v.get("lemma", ""),
                pos=v.get("pos", ""),
                cefr=v.get("cefr", "B1"),
                zipf=v.get("zipf", 0.0),
                count=v.get("count", 1),
                example=v.get("example", ""),
                translation=v.get("translation", ""),
                ipa=v.get("ipa", ""),
                mnemonic=v.get("mnemonic", ""),
            )
            for v in enriched[:250]
        ],
        saved_count=saved,
        lang_code=lang_code,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_book_text(
    body:         AnalyzeTextRequest,
    db:           Session      = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    return _run_analysis(
        text=body.text, title=body.title, author=body.author,
        lang_code=body.lang_code, target_lang=body.target_lang,
        enrich_top=body.enrich_top, db=db,
        user_id=current_user.id if current_user else None,
    )


@router.post("/upload", response_model=AnalyzeResponse)
async def upload_book_file(
    file:         UploadFile    = File(...),
    title:        str           = Form(""),
    author:       str           = Form(""),
    lang_code:    str           = Form("fr"),
    target_lang:  str           = Form("en"),
    enrich_top:   int           = Form(50),
    db:           Session       = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Upload .txt or .pdf — vocabulary saved as a named book folder."""
    fname   = file.filename or ""
    content = await file.read()

    if fname.lower().endswith(".pdf"):
        text = _extract_text_from_pdf(content)
    elif fname.lower().endswith(".txt"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    else:
        raise HTTPException(400, "Only .txt and .pdf files supported.")

    book_title = title or fname.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    return _run_analysis(
        text=text, title=book_title, author=author,
        lang_code=lang_code, target_lang=target_lang,
        enrich_top=enrich_top, db=db,
        user_id=current_user.id if current_user else None,
    )


@router.get("", response_model=list[BookOut])
def list_books(
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Return user's book library (most recent first)."""
    books = (
        db.query(BookLibrary)
        .filter(BookLibrary.user_id == current_user.id)
        .order_by(BookLibrary.created_at.desc())
        .all()
    )
    return [
        BookOut(
            id=b.id, title=b.title, author=b.author, lang_code=b.lang_code,
            total_words=b.total_words, unique_words=b.unique_words, saved_count=b.saved_count,
            cefr_breakdown=json.loads(b.cefr_json or "{}"),
            created_at=b.created_at.isoformat(),
        )
        for b in books
    ]


@router.get("/{book_id}/vocab", response_model=list[WordEntry])
def book_vocabulary(
    book_id:      int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Return vocabulary for a specific book."""
    book = db.get(BookLibrary, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    entries = (
        db.query(VocabEntry)
        .filter(VocabEntry.book_id == book_id, VocabEntry.user_id == current_user.id)
        .order_by(VocabEntry.count.desc())
        .all()
    )
    return [
        WordEntry(
            word=e.word, lemma=e.lemma or e.word,
            pos=e.pos or "", cefr=e.cefr_level or "B1",
            zipf=0.0, count=e.count,
            example=e.example_sentence or "",
            translation=e.translation or "",
            ipa=e.phonetic or "",
            mnemonic=e.explanation or "",
        )
        for e in entries
    ]


@router.get("/{book_id}/study")
def study_book_vocab(
    book_id:      int,
    limit:        int     = 20,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Return SM-2 study queue for a specific book — due + new words."""
    from datetime import datetime, timezone
    from app.models.user_vocab import UserVocab

    book = db.get(BookLibrary, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")

    now = datetime.now(timezone.utc)
    base = db.query(UserVocab).filter(
        UserVocab.user_id == current_user.id,
        UserVocab.book_id == book_id,
    )
    due = (
        base.filter(UserVocab.next_review <= now, UserVocab.status.notin_(["new", "known"]))
        .order_by(UserVocab.next_review.asc()).limit(limit).all()
    )
    remaining = limit - len(due)
    new_words = (
        base.filter(UserVocab.status == "new").limit(remaining).all()
        if remaining > 0 else []
    )
    words = due + new_words
    return {
        "book_id": book_id, "title": book.title,
        "total": base.count(), "due": len(due), "new": len(new_words),
        "words": [_uv_out(w) for w in words],
    }


def _uv_out(v) -> dict:
    return {
        "id": v.id, "word": v.word, "lemma": v.lemma,
        "pos": v.pos, "cefr": v.cefr, "status": v.status,
        "translation": v.translation or "", "ipa": v.ipa or "",
        "definition": v.definition or "", "example": v.example or "",
        "context_sentence": v.context_sentence or "",
        "mastery_score": v.mastery_score,
        "next_review": v.next_review.isoformat() if v.next_review else None,
    }


@router.delete("/{book_id}", status_code=204)
def delete_book(
    book_id:      int,
    db:           Session = Depends(get_db),
    current_user: User    = Depends(get_current_user),
):
    """Delete book record (vocabulary entries are kept in your learning library)."""
    book = db.get(BookLibrary, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "Book not found")
    db.delete(book)
    db.commit()
