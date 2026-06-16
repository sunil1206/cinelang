"""SRT parsing and client-side tokenisation."""
import re
from app.schemas.subtitle import SubtitleFrame

_SRT_PATTERN = re.compile(
    r"(\d+)\s*\n"
    r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
    r"([\s\S]*?)(?=\n\s*\n\d+\s*\n|\Z)",
    re.MULTILINE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_srt(content: str) -> list[SubtitleFrame]:
    frames: list[SubtitleFrame] = []
    # Ensure the string ends with a double-newline so the last block matches
    for m in _SRT_PATTERN.finditer(content.strip() + "\n\n"):
        text = _TAG_RE.sub("", m.group(4)).strip()
        if text:
            frames.append(
                SubtitleFrame(
                    index=int(m.group(1)),
                    start=m.group(2),
                    end=m.group(3),
                    text=text,
                )
            )
    return frames
