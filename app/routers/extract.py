"""
Vocabulary extraction — no authentication required.

Endpoints:
  POST /api/extract/srt   — parse SRT text + run NLP pipeline
  POST /api/extract/pdf   — extract text from PDF + run NLP pipeline
  POST /api/extract/text  — raw text + NLP pipeline
  GET  /api/extract/lookup — free dictionary lookup (MyMemory + FreeDictionary)
"""
from __future__ import annotations
import io
import logging
import re

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/extract", tags=["Extract"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SRTRequest(BaseModel):
    content:     str
    source_lang: str = "fr"
    target_lang: str = "en"

class TextRequest(BaseModel):
    text:        str
    source_lang: str = "fr"
    target_lang: str = "en"

class WordOut(BaseModel):
    word:        str
    lemma:       str
    pos:         str
    cefr:        str
    count:       int
    example:     str
    translation: str = ""
    phonetic:    str = ""
    explanation: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_srt(content: str) -> str:
    """Strip SRT timecodes and indices, return plain text."""
    content = re.sub(r"^\d+\s*$", "", content, flags=re.MULTILINE)
    content = re.sub(r"\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}", "", content)
    content = re.sub(r"<[^>]+>", "", content)  # strip HTML tags
    return " ".join(content.split())


def _translate_word(word: str, src: str, tgt: str) -> str:
    """Translate a single word using the full service chain (DeepL → MyMemory → Google)."""
    try:
        from app.services.translate_service import translate_text
        result = translate_text(word, src, tgt)
        # Reject if the translation is the same as the input (untranslated)
        if result and result.lower().strip() != word.lower().strip():
            return result
    except Exception:
        pass
    # Fallback: try word in a short phrase so MyMemory has context
    try:
        from app.services.translate_service import translate_text
        phrase = f"définition de {word}" if src == "fr" else f"meaning of {word}"
        result = translate_text(phrase, src, tgt)
        # Extract just the word from "definition of X" → "definición de X"
        # Not reliable, skip
    except Exception:
        pass
    return ""


def _extract(text: str, src: str, tgt: str, auto_enrich: bool = True) -> list[dict]:
    """Run NLP pipeline + optional free-dictionary enrichment."""
    from app.services.nlp.pipeline import extract_vocabulary
    raw = extract_vocabulary(text, lang_code=src, source_frames=[])

    if not auto_enrich:
        return raw

    # Enrich top 60 words: translate + get phonetic/definition
    from app.providers.dictionary_provider import _free_dict_lookup, _wiktionary_lookup
    enriched = []
    for item in raw[:60]:
        word = item.get("word", "")
        try:
            # Translation via full service chain
            item["translation"] = _translate_word(word, src, tgt)
            # Phonetic + definition via free dictionary
            if src == "en":
                dict_data = _free_dict_lookup(word)
            else:
                dict_data = _wiktionary_lookup(word, src)
                if not dict_data.get("definition"):
                    dict_data = _free_dict_lookup(word)
            item["phonetic"]    = dict_data.get("phonetic", "")
            item["explanation"] = dict_data.get("definition", "")
        except Exception:
            pass
        enriched.append(item)

    enriched.extend(raw[60:])
    return enriched


def _to_word_out(item: dict) -> dict:
    return {
        "word":        item.get("word", ""),
        "lemma":       item.get("lemma", item.get("word", "")),
        "pos":         item.get("pos", ""),
        "cefr":        item.get("cefr_level", "B1"),
        "count":       item.get("count", 1),
        "example":     item.get("contexts", [""])[0] if item.get("contexts") else "",
        "translation": item.get("translation", ""),
        "phonetic":    item.get("phonetic", ""),
        "explanation": item.get("explanation", ""),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/srt", summary="Extract vocabulary from SRT subtitle text")
def extract_from_srt(body: SRTRequest):
    if not body.content.strip():
        raise HTTPException(400, "SRT content is empty")
    text = _parse_srt(body.content)
    if not text:
        raise HTTPException(400, "No readable text found in SRT")
    items = _extract(text, body.source_lang, body.target_lang)
    return {
        "source_lang": body.source_lang,
        "target_lang": body.target_lang,
        "word_count":  len(items),
        "words":       [_to_word_out(i) for i in items],
    }


@router.post("/pdf", summary="Extract vocabulary from uploaded PDF")
async def extract_from_pdf(
    file:        UploadFile = File(...),
    source_lang: str        = Query("fr"),
    target_lang: str        = Query("en"),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Please upload a PDF file")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(400, "PDF too large (max 20 MB)")

    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages  = []
        for page in reader.pages[:80]:  # max 80 pages
            txt = page.extract_text() or ""
            pages.append(txt)
        text = " ".join(pages)
    except Exception as exc:
        log.error("PDF parse error: %s", exc)
        raise HTTPException(422, f"Could not read PDF: {exc}")

    if not text.strip():
        raise HTTPException(422, "PDF appears to have no extractable text (scanned image?)")

    items = _extract(text, source_lang, target_lang)
    return {
        "source_lang": source_lang,
        "target_lang": target_lang,
        "filename":    file.filename,
        "word_count":  len(items),
        "words":       [_to_word_out(i) for i in items],
    }


@router.post("/text", summary="Extract vocabulary from plain text")
def extract_from_text(body: TextRequest):
    if not body.text.strip():
        raise HTTPException(400, "Text is empty")
    items = _extract(body.text, body.source_lang, body.target_lang)
    return {
        "source_lang": body.source_lang,
        "target_lang": body.target_lang,
        "word_count":  len(items),
        "words":       [_to_word_out(i) for i in items],
    }


@router.get("/lookup", summary="Free dictionary lookup — no API key needed")
def lookup_word(
    word:        str = Query(..., description="Word to look up"),
    source_lang: str = Query("fr"),
    target_lang: str = Query("en"),
):
    """Uses MyMemory (translation) + FreeDictionary API (definition/IPA). No key required."""
    try:
        from app.providers.dictionary_provider import _free_dict_lookup, _wiktionary_lookup
        translation = _translate_word(word, source_lang, target_lang)
        if source_lang == "en":
            dict_data = _free_dict_lookup(word)
        else:
            dict_data = _wiktionary_lookup(word, source_lang)
            if not dict_data.get("definition"):
                dict_data = _free_dict_lookup(word)
        return {
            "word":        word,
            "translation": translation,
            "phonetic":    dict_data.get("phonetic", ""),
            "explanation": dict_data.get("definition", ""),
            "pos":         dict_data.get("partOfSpeech", ""),
        }
    except Exception as exc:
        log.error("Lookup failed for %r: %s", word, exc)
        return {"word": word, "translation": "", "phonetic": "", "explanation": "", "pos": ""}
