"""OpenSubtitles REST API v1 — search + download."""
import httpx

from app.config import get_settings
from app.core.exceptions import BadGatewayError, ServiceUnavailableError
from app.schemas.subtitle import (
    SubtitleSearchResult,
    SubtitleSearchResponse,
    SubtitleDownloadResponse,
)

settings = get_settings()

_DEMO_SRT = """\
1
00:00:01,000 --> 00:00:04,500
Il était une fois, dans un pays lointain...

2
00:00:05,000 --> 00:00:08,200
Une fille époustouflante vivait seule.

3
00:00:08,800 --> 00:00:12,000
Elle kiffait les petits plaisirs de la vie.

4
00:00:12,500 --> 00:00:16,000
Mais elle avait le cafard depuis longtemps.

5
00:00:16,500 --> 00:00:20,000
— Configurez OPENSUBS_API_KEY pour les vrais sous-titres.
"""

_DEMO_RESULTS: list[SubtitleSearchResult] = [
    SubtitleSearchResult(
        id="demo-1", file_id=0,
        title="Amélie (2001)", year=2001,
        language="fr", download_count=18420,
        release_name="demo — add OPENSUBS_API_KEY for real results",
    ),
    SubtitleSearchResult(
        id="demo-2", file_id=0,
        title="Le Fabuleux Destin d'Amélie Poulain", year=2001,
        language="fr", download_count=9210,
        release_name="demo — add OPENSUBS_API_KEY for real results",
    ),
]


def _headers() -> dict:
    return {
        "Api-Key":      settings.opensubs_api_key,
        "User-Agent":   settings.opensubs_user_agent,
        "Content-Type": "application/json",
    }


def search(query: str, language: str = "fr", page: int = 1) -> SubtitleSearchResponse:
    if not settings.opensubs_api_key:
        return SubtitleSearchResponse(results=_DEMO_RESULTS, total_pages=1, mock=True)

    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            f"{settings.opensubs_base_url}/subtitles",
            params={"query": query, "languages": language, "page": page},
            headers=_headers(),
        )

    if r.status_code != 200:
        raise BadGatewayError(f"OpenSubtitles search failed: HTTP {r.status_code}")

    data  = r.json()
    items = []
    for item in data.get("data", [])[:20]:
        attrs   = item.get("attributes", {})
        fd      = attrs.get("feature_details", {})
        files   = attrs.get("files", [{}])
        file_id = files[0].get("file_id", 0) if files else 0
        items.append(
            SubtitleSearchResult(
                id=str(item.get("id", "")),
                file_id=file_id,
                title=fd.get("title") or fd.get("movie_name") or query,
                year=fd.get("year"),
                language=attrs.get("language", language),
                download_count=attrs.get("download_count", 0),
                release_name=attrs.get("release", ""),
                feature_type=fd.get("feature_type"),
            )
        )
    return SubtitleSearchResponse(
        results=items,
        total_pages=data.get("total_pages", 1),
        mock=False,
    )


def download(file_id: int) -> SubtitleDownloadResponse:
    if not settings.opensubs_api_key or file_id == 0:
        return SubtitleDownloadResponse(
            content=_DEMO_SRT, filename="demo-cinelang.srt", mock=True
        )

    with httpx.Client(timeout=15.0) as client:
        # Step 1: request download link
        r = client.post(
            f"{settings.opensubs_base_url}/download",
            json={"file_id": file_id},
            headers=_headers(),
        )
        if r.status_code != 200:
            raise BadGatewayError(f"OpenSubtitles download request failed: HTTP {r.status_code}")

        link = r.json().get("link")
        if not link:
            raise BadGatewayError("OpenSubtitles returned no download link")

        # Step 2: fetch SRT content
        srt_r = client.get(link, timeout=30.0)
        if srt_r.status_code != 200:
            raise BadGatewayError("Failed to fetch SRT file from download link")

    raw_name = link.split("?")[0].split("/")[-1] or f"subtitle-{file_id}.srt"
    if not raw_name.endswith(".srt"):
        raw_name += ".srt"

    return SubtitleDownloadResponse(content=srt_r.text, filename=raw_name, mock=False)
