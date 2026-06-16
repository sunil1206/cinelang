"""Subtitle search, download, parse, and language detection."""
from fastapi import APIRouter

from app.dependencies import OptionalCurrentUser
from app.schemas.subtitle import (
    SubtitleDownloadRequest, SubtitleDownloadResponse,
    SubtitleSearchRequest, SubtitleSearchResponse,
    ParseSRTRequest, ParseSRTResponse,
    DetectLanguageRequest, DetectLanguageResponse,
)
from app.services import subtitle_service, srt_service

router = APIRouter(prefix="/subtitles", tags=["Subtitles"])


@router.post("/parse", response_model=ParseSRTResponse, summary="Parse an SRT file into frames")
def parse_srt(body: ParseSRTRequest):
    if not body.content.strip():
        from fastapi import HTTPException
        raise HTTPException(400, "Empty SRT content")
    frames = srt_service.parse_srt(body.content)
    if not frames:
        from fastapi import HTTPException
        raise HTTPException(422, "No valid SRT blocks found")
    return ParseSRTResponse(subtitle_count=len(frames), subtitles=frames)


@router.post("/detect-language", response_model=DetectLanguageResponse,
             summary="Detect subtitle language (Groq → Gemini → rule-based)")
def detect_language(body: DetectLanguageRequest, _user: OptionalCurrentUser):
    frames = srt_service.parse_srt(body.content)
    if not frames:
        from fastapi import HTTPException
        raise HTTPException(422, "No subtitle text to detect")

    sample = " ".join(f.text for f in frames[:15])

    # Try Groq first
    try:
        import json
        from groq import Groq
        from app.config import get_settings
        s = get_settings()
        if s.groq_api_key:
            client = Groq(api_key=s.groq_api_key)
            resp = client.chat.completions.create(
                model=s.groq_model,
                messages=[{"role": "user", "content":
                    f'Detect the language. Reply ONLY with JSON: {{"code":"fr","name":"French","confidence":0.99}}\n\nText: {sample[:300]}'}],
                response_format={"type": "json_object"},
                max_tokens=64, temperature=0.0,
            )
            result = json.loads(resp.choices[0].message.content)
            return DetectLanguageResponse(
                language_code=result.get("code", "fr")[:2].lower(),
                language_name=result.get("name", "French"),
                confidence=float(result.get("confidence", 0.95)),
            )
    except Exception:
        pass

    # Rule-based fallback — detect by character frequency
    code, name = _rule_detect(sample)
    return DetectLanguageResponse(language_code=code, language_name=name, confidence=0.7)


@router.post("/search", response_model=SubtitleSearchResponse, summary="Search OpenSubtitles")
def search_subtitles(body: SubtitleSearchRequest, _user: OptionalCurrentUser):
    return subtitle_service.search(body.query, body.language, body.page)


@router.post("/download", response_model=SubtitleDownloadResponse, summary="Download subtitle by file_id")
def download_subtitle(body: SubtitleDownloadRequest, _user: OptionalCurrentUser):
    return subtitle_service.download(body.file_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rule_detect(text: str) -> tuple[str, str]:
    """Simple rule-based language detection by character patterns."""
    t = text.lower()
    scores = {
        "fr": sum(1 for c in ["qu", "oi", "au", "eu", "on ", "an ", "en ", "tion", "ais", "est"] if c in t),
        "de": sum(1 for c in ["sch", "ich", "cht", "nge", "ung", "eit", "cht", "ein ", "und "] if c in t),
        "es": sum(1 for c in ["ción", "está", "para", "que ", "con ", "los ", "una ", "del "] if c in t),
        "it": sum(1 for c in ["zione", "della", "degli", "sono", "questo", "come ", "anche"] if c in t),
        "pt": sum(1 for c in ["ção", "está", "para", "que ", "com ", "dos ", "uma "] if c in t),
        "en": sum(1 for c in ["the ", "and ", "that", "this", "with", "have", "from"] if c in t),
    }
    _NAMES = {"fr": "French", "de": "German", "es": "Spanish", "it": "Italian", "pt": "Portuguese", "en": "English"}
    best = max(scores, key=lambda k: scores[k])
    return best, _NAMES.get(best, best.upper())
