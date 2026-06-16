"""AI router — Ollama/Gemma + LangGraph + pgvector endpoints."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import CurrentUser, OptionalCurrentUser, DBSession
from app.services.ai.ollama_client import is_ollama_available, list_models
from app.services.ai.langgraph_agent import enrich_word_local
from app.services.ai.spacy_service import extract_content_words, extract_entities

router = APIRouter(prefix="/ai", tags=["AI"])


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status", summary="Check Ollama availability + loaded models")
async def ai_status():
    available = await is_ollama_available()
    models    = await list_models() if available else []
    return {"ollama_available": available, "models": models}


# ── Local word enrichment (Ollama/Gemma) ─────────────────────────────────────

class LocalEnrichRequest(BaseModel):
    word:        str
    context:     str = ""
    source_lang: str = "en"
    target_lang: str = "fr"


@router.post("/enrich", summary="Enrich a word using local Gemma 3 via Ollama")
async def enrich_local(body: LocalEnrichRequest, current_user: OptionalCurrentUser):
    thread_id = str(current_user.id) if current_user else "anonymous"
    result = await enrich_word_local(
        word=body.word,
        context=body.context,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        thread_id=thread_id,
    )
    return result


# ── spaCy analysis ────────────────────────────────────────────────────────────

class SpacyRequest(BaseModel):
    text: str
    lang: str = "en"


@router.post("/analyse", summary="spaCy tokenisation + content-word extraction")
def analyse_text(body: SpacyRequest):
    words    = extract_content_words(body.text, body.lang)
    entities = extract_entities(body.text, body.lang)
    return {"content_words": words, "entities": entities, "lang": body.lang}
