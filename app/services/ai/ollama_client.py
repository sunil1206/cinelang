"""Ollama client — wraps LangChain's Ollama integration for Gemma 3 4B."""
from functools import lru_cache

from langchain_ollama import ChatOllama, OllamaEmbeddings
from app.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_llm(model: str | None = None, temperature: float = 0.3) -> ChatOllama:
    """Return a ChatOllama instance pointed at the local Ollama server."""
    return ChatOllama(
        model=model or settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
    )


@lru_cache(maxsize=1)
def get_embeddings(model: str | None = None) -> OllamaEmbeddings:
    """Return an OllamaEmbeddings instance for vector encoding."""
    return OllamaEmbeddings(
        model=model or settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


async def is_ollama_available() -> bool:
    """Quick health check — returns True if Ollama is reachable."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{settings.ollama_base_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False


async def list_models() -> list[str]:
    """List models currently loaded in Ollama."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{settings.ollama_base_url}/api/tags")
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []
