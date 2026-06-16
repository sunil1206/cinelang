"""Legacy shim — delegates to translate_service (deep-translator)."""
from app.services.translate_service import translate_text, translate_batch  # noqa: F401
