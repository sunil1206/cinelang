from pydantic import BaseModel


# ── SRT ───────────────────────────────────────────────────────────────────────

class SubtitleFrame(BaseModel):
    index: int
    start: str
    end:   str
    text:  str


class ParseSRTRequest(BaseModel):
    content: str


class ParseSRTResponse(BaseModel):
    subtitle_count: int
    subtitles:      list[SubtitleFrame]


class DetectLanguageRequest(BaseModel):
    content: str


class DetectLanguageResponse(BaseModel):
    language_code: str
    language_name: str
    confidence:    float = 1.0


# ── Translation ───────────────────────────────────────────────────────────────

class TranslatedFrame(BaseModel):
    index:    int
    start:    str
    end:      str
    original: str
    text:     str          # translated


class TranslateRequest(BaseModel):
    subtitles:   list[SubtitleFrame]
    source_lang: str  = "en"
    target_lang: str  = "fr"
    auto_detect: bool = False
    movie_title: str  = ""    # used to create/update movie folder in cinema library


class VocabItem(BaseModel):
    word:        str
    translation: str
    pos:         str
    phonetic:    str
    explanation: str
    example:     str
    count:       int       = 1
    contexts:    list[str] = []
    timestamps:  list[str] = []
    source_lang: str       = "en"
    target_lang: str       = "fr"
    status:      str       = "new"


class TranslateResponse(BaseModel):
    translated:     list[TranslatedFrame]
    vocabulary:     list[VocabItem]
    source_lang:    str
    target_lang:    str
    subtitle_count: int
    vocab_count:    int


# ── OpenSubtitles ─────────────────────────────────────────────────────────────

class SubtitleSearchRequest(BaseModel):
    query:    str
    language: str = "fr"
    page:     int = 1


class SubtitleSearchResult(BaseModel):
    id:             str
    file_id:        int
    title:          str
    year:           int | None  = None
    language:       str
    download_count: int
    release_name:   str
    feature_type:   str | None  = None


class SubtitleSearchResponse(BaseModel):
    results:     list[SubtitleSearchResult]
    total_pages: int
    mock:        bool = False


class SubtitleDownloadRequest(BaseModel):
    file_id: int


class SubtitleDownloadResponse(BaseModel):
    content:  str
    filename: str
    mock:     bool = False
