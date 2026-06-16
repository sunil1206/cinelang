"""FastAPI application — CineLang v3."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.database import create_tables
from app.routers import auth, users, vocabulary, subtitles, translations, ai
from app.routers import languages, decks, reviews, lessons, quiz, books, cinema

log      = logging.getLogger(__name__)
settings = get_settings()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    create_tables()
    log.info("CineLang v%s started", settings.app_version)
    # Warm up provider manager
    try:
        from app.providers.manager import provider_manager
        status = provider_manager.status()
        available = [k for k, v in status.items() if v["available"]]
        log.info("AI providers available: %s", available)
    except Exception as exc:
        log.warning("Provider warmup failed: %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "CineLang API v3 — AI-powered language learning through cinema.\n\n"
            "**AI stack**: Groq (primary) → Gemini Flash → Ollama → Offline dictionary\n\n"
            "**Auth**: POST `/api/auth/google` with Google id_token → access_token + refresh_token"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    prefix = "/api"
    app.include_router(auth.router,         prefix=prefix)
    app.include_router(users.router,        prefix=prefix)
    app.include_router(vocabulary.router,   prefix=prefix)
    app.include_router(subtitles.router,    prefix=prefix)
    app.include_router(translations.router, prefix=prefix)
    app.include_router(ai.router,           prefix=prefix)
    app.include_router(languages.router,    prefix=prefix)
    app.include_router(decks.router,        prefix=prefix)
    app.include_router(reviews.router,      prefix=prefix)
    app.include_router(lessons.router,      prefix=prefix)
    app.include_router(quiz.router,         prefix=prefix)
    app.include_router(books.router,        prefix=prefix)
    app.include_router(cinema.router,       prefix=prefix)

    @app.get("/api/health", tags=["System"])
    def health():
        from app.providers.manager import provider_manager
        from app.cache.redis_cache import is_healthy as redis_ok
        status = provider_manager.status()
        primary = next((k for k, v in status.items() if v["available"] and not v["circuit_open"]), "offline")
        return {
            "status":   "ok",
            "version":  settings.app_version,
            "ai":       {"primary_provider": primary, "providers": status},
            "cache":    {"redis": redis_ok()},
        }

    @app.get("/api/config", tags=["System"])
    def config():
        return {
            "google_client_id":  settings.google_client_id,
            "groq_configured":   bool(settings.groq_api_key),
            "gemini_configured": bool(settings.gemini_api_key and len(settings.gemini_api_key) > 10),
            "redis_url":         settings.redis_url,
        }

    @app.post("/api/health/reset-circuits", tags=["System"])
    def reset_circuits():
        from app.providers.manager import provider_manager
        provider_manager.reset_circuits()
        return {"reset": True, "providers": provider_manager.status()}

    return app


app = create_app()
