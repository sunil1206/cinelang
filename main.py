"""
CineLang v2 — FastAPI backend
pip install fastapi uvicorn requests pydantic sqlalchemy PyJWT
"""
import json, os, re, time, secrets
from datetime import datetime, timedelta
from typing import Any, List, Optional

import jwt
import requests
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

app = FastAPI(title="CineLang API v2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Config ────────────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = "gemini-2.5-flash-preview-05-20"
GEMINI_URL       = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
JWT_SECRET      = os.getenv("JWT_SECRET", secrets.token_hex(32))
JWT_ALGO        = "HS256"
JWT_EXPIRE_DAYS = 7

LANG_NAMES = {
    "en": "English",  "fr": "French",   "de": "German",   "es": "Spanish",
    "it": "Italian",  "pt": "Portuguese","ja": "Japanese", "ko": "Korean",
    "zh": "Mandarin", "ru": "Russian",   "ar": "Arabic",   "nl": "Dutch",
    "pl": "Polish",   "sv": "Swedish",   "tr": "Turkish",  "hi": "Hindi",
}

# ── Database ──────────────────────────────────────────────────────────────────
Base = declarative_base()
_db_path = os.getenv("DB_PATH", "cinelang.db")
engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id         = Column(Integer, primary_key=True, index=True)
    google_id  = Column(String, unique=True, nullable=False)
    email      = Column(String)
    name       = Column(String)
    picture    = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    vocab      = relationship("VocabEntry", back_populates="user", cascade="all, delete-orphan")

class VocabEntry(Base):
    __tablename__ = "vocabulary"
    id          = Column(Integer, primary_key=True, index=True)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    word        = Column(String, nullable=False)
    source_lang = Column(String, default="en")
    target_lang = Column(String, default="fr")
    translation = Column(String)
    pos         = Column(String)
    phonetic    = Column(String)
    explanation = Column(String)
    status      = Column(String, default="new")
    count       = Column(Integer, default=1)
    contexts    = Column(Text, default="[]")
    ts          = Column("timestamps", Text, default="[]")
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint("user_id", "word", "target_lang"),)
    user = relationship("User", back_populates="vocab")

Base.metadata.create_all(engine)

# ── Auth ──────────────────────────────────────────────────────────────────────
def verify_google_token(token_str: str) -> dict:
    r = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": token_str}, timeout=10
    )
    if r.status_code != 200:
        raise HTTPException(401, "Invalid Google token")
    data = r.json()
    if GOOGLE_CLIENT_ID and data.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(401, "Token audience mismatch")
    return data

def make_jwt(user_id: int) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS)},
        JWT_SECRET, algorithm=JWT_ALGO
    )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization")
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGO])
        uid = int(payload["sub"])
    except Exception:
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user

def try_get_user(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Optional[User]:
    """Non-raising auth — returns None if no valid token."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGO])
        return db.query(User).filter(User.id == int(payload["sub"])).first()
    except Exception:
        return None

# ── NLP ───────────────────────────────────────────────────────────────────────
FR_STOPS = {
    "le","la","les","un","une","des","du","de","d","l","je","tu","il","elle",
    "nous","vous","ils","elles","me","te","se","lui","leur","y","en","et","ou",
    "mais","donc","or","ni","car","que","qui","quoi","dont","où","ce","cet",
    "cette","ces","mon","ton","son","ma","ta","sa","nos","vos","leurs","si",
    "ne","pas","plus","très","bien","aussi","alors","pour","par","sur","sous",
    "dans","avec","sans","vers","être","avoir","faire","aller","est","sont",
    "était","ont","a","au","aux","j","m","t","s","n","c","qu","ah","oh",
}
DE_STOPS = {
    "der","die","das","ein","eine","und","oder","aber","wenn","ich","du","er",
    "sie","es","wir","ihr","nicht","ist","sind","war","haben","sein","mit",
    "auf","an","in","zu","von","für","dem","den","des","im","am","vom","zum",
    "zur","als","wie","auch","noch","schon","nur","so","dann","da","hier","kann",
}
ES_STOPS = {
    "el","la","los","las","un","una","de","del","al","en","con","por","para",
    "que","es","son","ser","estar","fue","me","te","se","le","lo","no","si",
    "pero","como","más","ya","muy","todo","también","esto","eso","ese","esta",
}
STOPS = {"fr": FR_STOPS, "de": DE_STOPS, "es": ES_STOPS}
EN_STOPS = {
    "the","a","an","is","are","was","were","be","been","i","you","he","she",
    "it","we","they","me","him","her","us","them","my","your","his","its",
    "our","their","and","or","but","in","on","at","to","for","of","with",
    "by","from","as","this","that","not","no","so","do","did","have","has",
    "had","will","would","could","should","may","might","can","s","t","re",
}
STOPS["en"] = EN_STOPS
TOKEN_RE = re.compile(r"[a-zàâäéèêëïîôùûüÿæœçñßäöü\-']+")
CONTR    = {"l","d","j","qu","m","t","s","n","c"}

def tokenize(text: str, lang: str = "fr") -> list:
    stops = STOPS.get(lang, EN_STOPS)
    out = []
    for tok in TOKEN_RE.findall(text.lower()):
        if "'" in tok:
            pre, root = tok.split("'", 1)
            if pre in CONTR and len(root) > 2:
                tok = root
            else:
                continue
        if tok not in stops and len(tok) > 2:
            out.append(tok)
    return out

def guess_pos(w: str) -> str:
    if re.search(r"(er|ir|re|en|ieren)$", w) and len(w) > 3: return "Verb"
    if re.search(r"(able|ible|eux|euse|al|ale|ique|if|ive|lich|isch|os|oso)$", w): return "Adjective"
    if re.search(r"(ment|lich|weise|mente)$", w): return "Adverb"
    return "Noun"

# ── SRT ───────────────────────────────────────────────────────────────────────
SRT_PAT = re.compile(
    r"(\d+)\s*\n(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
    r"([\s\S]*?)(?=\n\s*\n\d+\s*\n|\Z)",
    re.MULTILINE
)

def parse_srt(content: str) -> list:
    blocks = []
    for m in SRT_PAT.finditer(content.strip() + "\n\n"):
        text = re.sub(r"<[^>]+>", "", m.group(4)).strip()
        if text:
            blocks.append({"index": int(m.group(1)), "start": m.group(2), "end": m.group(3), "text": text})
    return blocks

# ── Gemini ────────────────────────────────────────────────────────────────────
def gemini_call(payload: dict) -> dict:
    last = None
    for i, delay in enumerate([1, 2, 4, 8, 16]):
        try:
            r = requests.post(GEMINI_URL, json=payload, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            if i < 4: time.sleep(delay)
    raise RuntimeError(f"Gemini failed: {last}")

def gemini_json(payload: dict) -> dict:
    data = gemini_call(payload)
    return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])

ENRICH_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translation":       {"type": "STRING"},
        "pos":               {"type": "STRING", "enum": ["Noun","Verb","Adjective","Adverb","Idiom","Slang","Phrase"]},
        "phonetic":          {"type": "STRING"},
        "explanation":       {"type": "STRING"},
        "sentenceTranslation": {"type": "STRING"},
    },
    "required": ["translation","pos","phonetic","explanation","sentenceTranslation"]
}

TRANSLATE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "translations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {"index": {"type": "INTEGER"}, "text": {"type": "STRING"}},
                "required": ["index","text"]
            }
        },
        "vocabulary": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "word":        {"type": "STRING"},
                    "translation": {"type": "STRING"},
                    "pos":         {"type": "STRING", "enum": ["Noun","Verb","Adjective","Adverb","Idiom","Slang","Phrase"]},
                    "phonetic":    {"type": "STRING"},
                    "explanation": {"type": "STRING"},
                    "example":     {"type": "STRING"},
                },
                "required": ["word","translation","pos","phonetic","explanation","example"]
            }
        }
    },
    "required": ["translations","vocabulary"]
}

DETECT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "code":       {"type": "STRING"},
        "name":       {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["code","name","confidence"]
}

def call_detect(sample: str) -> str:
    result = gemini_json({
        "contents": [{"parts": [{"text": f"Detect the language. Return ISO 639-1 code:\n\n{sample[:600]}"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": DETECT_SCHEMA, "temperature": 0}
    })
    return result.get("code", "en").lower()[:2]

def call_translate_batch(blocks: list, src: str, tgt: str) -> dict:
    sn, tn = LANG_NAMES.get(src, src), LANG_NAMES.get(tgt, tgt)
    numbered = "\n".join(f"{b['index']}. {b['text']}" for b in blocks)
    prompt = (
        f"Translate these {sn} subtitles to {tn}.\n"
        f"Also extract 5-8 interesting vocabulary words from your {tn} translations "
        f"that a language learner should know (idioms, expressive verbs, cultural words).\n\n"
        f"Subtitles:\n{numbered}"
    )
    return gemini_json({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": TRANSLATE_SCHEMA,
            "temperature": 0.3
        }
    })

# ── Request models ─────────────────────────────────────────────────────────────
class GoogleAuthReq(BaseModel):
    id_token: str

class ParseSRTReq(BaseModel):
    content: str

class TranslateReq(BaseModel):
    subtitles:   list
    source_lang: str  = "en"
    target_lang: str  = "fr"
    auto_detect: bool = False

class DetectReq(BaseModel):
    content: str

class EnrichReq(BaseModel):
    word:        str
    sentence:    str = ""
    source_lang: str = "en"
    target_lang: str = "fr"

class VocabUpsertReq(BaseModel):
    word:        str
    source_lang: str       = "en"
    target_lang: str       = "fr"
    translation: Optional[str] = None
    pos:         Optional[str] = None
    phonetic:    Optional[str] = None
    explanation: Optional[str] = None
    status:      str       = "new"
    count:       int       = 1
    contexts:    List[str] = []
    timestamps:  List[str] = []

class StatusReq(BaseModel):
    status: str

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "model": GEMINI_MODEL}

@app.get("/api/config")
def config():
    return {"google_client_id": GOOGLE_CLIENT_ID, "model": GEMINI_MODEL}

@app.post("/api/auth/google")
def auth_google(req: GoogleAuthReq, db: Session = Depends(get_db)):
    info = verify_google_token(req.id_token)
    gid  = info.get("sub")
    if not gid:
        raise HTTPException(400, "Missing sub in token")
    user = db.query(User).filter(User.google_id == gid).first()
    if not user:
        user = User(google_id=gid, email=info.get("email"), name=info.get("name"), picture=info.get("picture"))
        db.add(user)
        db.commit()
        db.refresh(user)
    return {
        "token": make_jwt(user.id),
        "user":  {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}
    }

@app.get("/api/auth/me")
def auth_me(user: User = Depends(get_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}

@app.post("/api/parse-srt")
def parse_srt_ep(req: ParseSRTReq):
    if not req.content.strip():
        raise HTTPException(400, "Empty SRT content")
    blocks = parse_srt(req.content)
    if not blocks:
        raise HTTPException(422, "No valid SRT blocks found")
    return {"subtitle_count": len(blocks), "subtitles": blocks}

@app.post("/api/detect-language")
def detect_language(req: DetectReq):
    if not GEMINI_API_KEY:
        raise HTTPException(503, "GEMINI_API_KEY not configured")
    blocks = parse_srt(req.content)
    sample = " ".join(b["text"] for b in blocks[:15])
    code   = call_detect(sample)
    return {"language_code": code, "language_name": LANG_NAMES.get(code, code)}

@app.post("/api/translate-subtitles")
def translate_subtitles(
    req:           TranslateReq,
    authorization: Optional[str] = Header(None),
    db:            Session       = Depends(get_db)
):
    if not GEMINI_API_KEY:
        raise HTTPException(503, "GEMINI_API_KEY not configured")

    user = try_get_user.__wrapped__(authorization, db) if hasattr(try_get_user, "__wrapped__") else None
    # manual user resolution
    if authorization and authorization.startswith("Bearer "):
        try:
            payload = jwt.decode(authorization.split(" ", 1)[1], JWT_SECRET, algorithms=[JWT_ALGO])
            user    = db.query(User).filter(User.id == int(payload["sub"])).first()
        except Exception:
            user = None

    subs = req.subtitles[:100]
    src  = req.source_lang
    if req.auto_detect and subs:
        sample = " ".join(s.get("text", "") for s in subs[:15])
        src    = call_detect(sample)

    tgt             = req.target_lang
    all_translated  = []
    all_vocab: dict = {}

    for i in range(0, len(subs), 25):
        batch  = subs[i:i+25]
        result = call_translate_batch(batch, src, tgt)
        tmap   = {t["index"]: t["text"] for t in result.get("translations", [])}
        for b in batch:
            all_translated.append({
                "index":    b["index"], "start": b["start"], "end": b["end"],
                "original": b["text"],  "text":  tmap.get(b["index"], b["text"])
            })
        for v in result.get("vocabulary", []):
            w = v["word"].lower().strip()
            if w not in all_vocab:
                all_vocab[w] = {**v, "count": 0, "contexts": [], "timestamps": []}
            all_vocab[w]["count"] += 1

    # attach example contexts from translated lines
    for entry in all_translated:
        for w, voc in all_vocab.items():
            if w in entry["text"].lower() and len(voc["contexts"]) < 3:
                voc["contexts"].append(entry["text"])
                voc["timestamps"].append(f"{entry['start']} --> {entry['end']}")

    # persist to DB if authenticated
    if user:
        for w, voc in all_vocab.items():
            existing = db.query(VocabEntry).filter(
                VocabEntry.user_id == user.id,
                VocabEntry.word    == w,
                VocabEntry.target_lang == tgt,
            ).first()
            if existing:
                existing.count      += voc["count"]
                existing.updated_at  = datetime.utcnow()
                ctxs = json.loads(existing.contexts or "[]")
                for c in voc["contexts"]:
                    if c not in ctxs: ctxs.append(c)
                existing.contexts = json.dumps(ctxs[:5])
            else:
                db.add(VocabEntry(
                    user_id=user.id, word=w, source_lang=src, target_lang=tgt,
                    translation=voc.get("translation"), pos=voc.get("pos"),
                    phonetic=voc.get("phonetic"),       explanation=voc.get("explanation"),
                    status="new", count=voc["count"],
                    contexts=json.dumps(voc["contexts"][:5]),
                    ts=json.dumps(voc["timestamps"][:5]),
                ))
        db.commit()

    return {
        "translated":     all_translated,
        "vocabulary":     sorted(
            [{**v, "status": "new", "source_lang": src, "target_lang": tgt} for v in all_vocab.values()],
            key=lambda x: -x["count"]
        ),
        "source_lang":    src,
        "target_lang":    tgt,
        "subtitle_count": len(all_translated),
        "vocab_count":    len(all_vocab),
    }

@app.post("/api/enrich-word")
def enrich_word(req: EnrichReq, user: User = Depends(get_user), db: Session = Depends(get_db)):
    if not req.word.strip():
        raise HTTPException(400, "Word required")
    if not GEMINI_API_KEY:
        raise HTTPException(503, "GEMINI_API_KEY not configured")
    sn, tn = LANG_NAMES.get(req.source_lang, "English"), LANG_NAMES.get(req.target_lang, "French")
    result = gemini_json({
        "contents": [{"parts": [{"text": (
            f"Analyze this {tn} word: '{req.word}'\nContext: \"{req.sentence}\"\n"
            f"Provide accurate {sn} translation, part of speech, phonetic guide, "
            f"short usage explanation, and fluent {sn} translation of the context sentence."
        )}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseSchema": ENRICH_SCHEMA, "temperature": 0.2}
    })
    entry = db.query(VocabEntry).filter(
        VocabEntry.user_id == user.id, VocabEntry.word == req.word.lower(), VocabEntry.target_lang == req.target_lang
    ).first()
    if entry:
        entry.translation = result.get("translation")
        entry.pos         = result.get("pos")
        entry.phonetic    = result.get("phonetic")
        entry.explanation = result.get("explanation")
        entry.updated_at  = datetime.utcnow()
        db.commit()
    return result

@app.get("/api/vocabulary")
def get_vocab(
    target_lang: Optional[str] = None,
    status:      Optional[str] = None,
    user:        User           = Depends(get_user),
    db:          Session        = Depends(get_db),
):
    q = db.query(VocabEntry).filter(VocabEntry.user_id == user.id)
    if target_lang: q = q.filter(VocabEntry.target_lang == target_lang)
    if status:      q = q.filter(VocabEntry.status == status)
    return [
        {
            "id": e.id, "word": e.word, "source_lang": e.source_lang, "target_lang": e.target_lang,
            "translation": e.translation, "pos": e.pos, "phonetic": e.phonetic,
            "explanation": e.explanation, "status": e.status, "count": e.count,
            "contexts":    json.loads(e.contexts or "[]"),
            "timestamps":  json.loads(e.ts or "[]"),
            "created_at":  e.created_at.isoformat() if e.created_at else None,
            "updated_at":  e.updated_at.isoformat() if e.updated_at else None,
        }
        for e in q.order_by(VocabEntry.updated_at.desc()).all()
    ]

@app.post("/api/vocabulary")
def upsert_vocab(req: VocabUpsertReq, user: User = Depends(get_user), db: Session = Depends(get_db)):
    w     = req.word.lower().strip()
    entry = db.query(VocabEntry).filter(
        VocabEntry.user_id == user.id, VocabEntry.word == w, VocabEntry.target_lang == req.target_lang
    ).first()
    if entry:
        if req.translation: entry.translation = req.translation
        if req.pos:         entry.pos         = req.pos
        if req.phonetic:    entry.phonetic     = req.phonetic
        if req.explanation: entry.explanation  = req.explanation
        entry.status     = req.status
        entry.count      = max(entry.count, req.count)
        entry.updated_at = datetime.utcnow()
    else:
        entry = VocabEntry(
            user_id=user.id, word=w, source_lang=req.source_lang, target_lang=req.target_lang,
            translation=req.translation, pos=req.pos, phonetic=req.phonetic,
            explanation=req.explanation, status=req.status, count=req.count,
            contexts=json.dumps(req.contexts[:5]), ts=json.dumps(req.timestamps[:5]),
        )
        db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"saved": True, "id": entry.id}

@app.patch("/api/vocabulary/{vid}/status")
def set_status(vid: int, req: StatusReq, user: User = Depends(get_user), db: Session = Depends(get_db)):
    entry = db.query(VocabEntry).filter(VocabEntry.id == vid, VocabEntry.user_id == user.id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    if req.status not in ("new", "learning", "mastered"):
        raise HTTPException(400, "Invalid status")
    entry.status     = req.status
    entry.updated_at = datetime.utcnow()
    db.commit()
    return {"saved": True}

@app.delete("/api/vocabulary/{vid}")
def del_vocab(vid: int, user: User = Depends(get_user), db: Session = Depends(get_db)):
    entry = db.query(VocabEntry).filter(VocabEntry.id == vid, VocabEntry.user_id == user.id).first()
    if not entry:
        raise HTTPException(404, "Not found")
    db.delete(entry)
    db.commit()
    return {"deleted": True}

# ── OpenSubtitles ─────────────────────────────────────────────────────────────
OPENSUBS_API_KEY = os.getenv("OPENSUBS_API_KEY", "")
OPENSUBS_BASE    = "https://api.opensubtitles.com/api/v1"
OPENSUBS_HEADERS = {
    "Api-Key":    OPENSUBS_API_KEY,
    "User-Agent": "CineLang/2.0",
    "Content-Type": "application/json",
}

class SubSearchReq(BaseModel):
    query:    str
    language: str = "fr"
    page:     int = 1

class SubDownloadReq(BaseModel):
    file_id: int

@app.post("/api/subtitles/search")
def subtitles_search(req: SubSearchReq):
    if not OPENSUBS_API_KEY:
        # return curated mock results so the UI still works without an API key
        return {"results": [
            {"id": "demo-1", "file_id": 0, "title": "Amélie (2001)", "year": 2001,
             "language": req.language, "download_count": 18420,
             "release_name": "Amelie.2001.BluRay.FRENCH", "url": ""},
            {"id": "demo-2", "file_id": 0, "title": "Le Fabuleux Destin d'Amélie Poulain",
             "year": 2001, "language": req.language, "download_count": 9210,
             "release_name": "demo — configure OPENSUBS_API_KEY for real results", "url": ""},
        ], "mock": True}

    params: dict = {
        "query":         req.query,
        "languages":     req.language,
        "page":          req.page,
    }
    r = requests.get(f"{OPENSUBS_BASE}/subtitles", params=params, headers={
        "Api-Key": OPENSUBS_API_KEY, "User-Agent": "CineLang/2.0",
    }, timeout=15)
    if r.status_code != 200:
        raise HTTPException(502, f"OpenSubtitles error: {r.status_code}")

    data = r.json()
    results = []
    for item in data.get("data", [])[:20]:
        attrs = item.get("attributes", {})
        files = attrs.get("files", [{}])
        file_id = files[0].get("file_id", 0) if files else 0
        results.append({
            "id":             str(item.get("id", "")),
            "file_id":        file_id,
            "title":          attrs.get("feature_details", {}).get("title", attrs.get("feature_details", {}).get("movie_name", req.query)),
            "year":           attrs.get("feature_details", {}).get("year"),
            "language":       attrs.get("language", req.language),
            "download_count": attrs.get("download_count", 0),
            "release_name":   attrs.get("release", ""),
            "url":            attrs.get("url", ""),
        })
    return {"results": results, "total_pages": data.get("total_pages", 1)}

@app.post("/api/subtitles/download")
def subtitles_download(req: SubDownloadReq):
    if not OPENSUBS_API_KEY or req.file_id == 0:
        # return demo SRT so the UI can work without API key
        demo_srt = (
            "1\n00:00:01,000 --> 00:00:04,500\nIl était une fois, dans un pays lointain...\n\n"
            "2\n00:00:05,000 --> 00:00:08,200\nUne fille époustouflante vivait seule.\n\n"
            "3\n00:00:08,800 --> 00:00:12,000\nElle kiffait les petits plaisirs de la vie.\n\n"
            "4\n00:00:12,500 --> 00:00:16,000\nMais elle avait le cafard depuis longtemps.\n\n"
            "5\n00:00:16,500 --> 00:00:20,000\n— Configurez OPENSUBS_API_KEY pour les vrais sous-titres.\n"
        )
        return {"content": demo_srt, "filename": "demo-cinelang.srt", "mock": True}

    # Step 1: request download link
    r = requests.post(
        f"{OPENSUBS_BASE}/download",
        json={"file_id": req.file_id},
        headers=OPENSUBS_HEADERS,
        timeout=15,
    )
    if r.status_code != 200:
        raise HTTPException(502, f"OpenSubtitles download error: {r.status_code}")
    link = r.json().get("link")
    if not link:
        raise HTTPException(502, "No download link returned")

    # Step 2: fetch actual SRT content
    srt_r = requests.get(link, timeout=30)
    if srt_r.status_code != 200:
        raise HTTPException(502, "Failed to fetch SRT file")

    content = srt_r.text
    # Try to derive filename from the download URL
    raw_filename = link.split("?")[0].split("/")[-1] or f"subtitle-{req.file_id}.srt"
    if not raw_filename.endswith(".srt"):
        raw_filename += ".srt"
    return {"content": content, "filename": raw_filename, "mock": False}
