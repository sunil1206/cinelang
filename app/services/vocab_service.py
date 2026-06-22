"""Vocabulary CRUD — all DB writes go through here."""
import json
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ForbiddenError
from app.models.user import User
from app.models.vocabulary import VocabEntry
from app.schemas.vocabulary import VocabOut, VocabUpsertRequest


def _serialise(entry: VocabEntry) -> VocabOut:
    return VocabOut.model_validate(entry)


def list_vocab(
    db: Session,
    user: User,
    target_lang: str | None = None,
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[VocabOut]:
    q = db.query(VocabEntry).filter(VocabEntry.user_id == user.id)
    if target_lang:
        q = q.filter(VocabEntry.target_lang == target_lang)
    if status:
        q = q.filter(VocabEntry.status == status)
    return [_serialise(e) for e in q.order_by(VocabEntry.updated_at.desc()).offset(offset).limit(limit).all()]


def upsert_vocab(db: Session, user: User, req: VocabUpsertRequest) -> VocabOut:
    entry = (
        db.query(VocabEntry)
        .filter(
            VocabEntry.user_id == user.id,
            VocabEntry.word    == req.word,
            VocabEntry.target_lang == req.target_lang,
        )
        .first()
    )
    if entry:
        if req.translation: entry.translation = req.translation
        if req.pos:         entry.pos         = req.pos
        if req.phonetic:    entry.phonetic     = req.phonetic
        if req.explanation: entry.explanation  = req.explanation
        entry.status  = req.status
        entry.count   = max(entry.count, req.count)
        # merge contexts (keep newest first, cap at 5)
        existing_ctx = json.loads(entry.contexts or "[]")
        merged = list(dict.fromkeys(req.contexts + existing_ctx))[:5]
        entry.contexts = json.dumps(merged)
    else:
        entry = VocabEntry(
            user_id=user.id,
            word=req.word,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            translation=req.translation,
            pos=req.pos,
            phonetic=req.phonetic,
            explanation=req.explanation,
            status=req.status,
            count=req.count,
            contexts=json.dumps(req.contexts[:5]),
            timestamps=json.dumps(req.timestamps[:5]),
        )
        db.add(entry)

    db.commit()
    db.refresh(entry)
    return _serialise(entry)


def update_status(db: Session, user: User, vocab_id: int, status: str) -> VocabOut:
    entry = db.get(VocabEntry, vocab_id)
    if entry is None:
        raise NotFoundError(f"Vocab entry {vocab_id} not found")
    if entry.user_id != user.id:
        raise ForbiddenError("Not your vocabulary entry")
    entry.status = status
    db.commit()
    db.refresh(entry)
    return _serialise(entry)


def delete_vocab(db: Session, user: User, vocab_id: int) -> None:
    entry = db.get(VocabEntry, vocab_id)
    if entry is None:
        raise NotFoundError(f"Vocab entry {vocab_id} not found")
    if entry.user_id != user.id:
        raise ForbiddenError("Not your vocabulary entry")
    db.delete(entry)
    db.commit()


def bulk_upsert(
    db: Session,
    user: User,
    items: list[dict],
    source_lang: str,
    target_lang: str,
) -> int:
    """Merge a list of raw vocab dicts from a translation response into the DB."""
    saved = 0
    for v in items:
        word = v.get("word", "").lower().strip()
        if not word:
            continue
        entry = (
            db.query(VocabEntry)
            .filter(
                VocabEntry.user_id    == user.id,
                VocabEntry.word       == word,
                VocabEntry.target_lang == target_lang,
            )
            .first()
        )
        if entry:
            entry.count += v.get("count", 1)
            ctx = json.loads(entry.contexts or "[]")
            for c in v.get("contexts", []):
                if c not in ctx:
                    ctx.append(c)
            entry.contexts = json.dumps(ctx[:5])
        else:
            db.add(VocabEntry(
                user_id=user.id,
                word=word,
                source_lang=source_lang,
                target_lang=target_lang,
                translation=v.get("translation"),
                pos=v.get("pos"),
                phonetic=v.get("phonetic"),
                explanation=v.get("explanation"),
                status="new",
                count=v.get("count", 1),
                contexts=json.dumps(v.get("contexts", [])[:5]),
                timestamps=json.dumps(v.get("timestamps", [])[:5]),
            ))
            saved += 1
    db.commit()
    return saved
