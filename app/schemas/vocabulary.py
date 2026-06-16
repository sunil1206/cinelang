from datetime import datetime
from typing import Literal
from pydantic import BaseModel, field_validator
import json

VocabStatus = Literal["new", "learning", "mastered"]
POS         = Literal["Noun", "Verb", "Adjective", "Adverb", "Idiom", "Slang", "Phrase"]


# ── Requests ──────────────────────────────────────────────────────────────────

class VocabUpsertRequest(BaseModel):
    word:        str
    source_lang: str          = "en"
    target_lang: str          = "fr"
    translation: str | None   = None
    pos:         str | None   = None
    phonetic:    str | None   = None
    explanation: str | None   = None
    status:      VocabStatus  = "new"
    count:       int          = 1
    contexts:    list[str]    = []
    timestamps:  list[str]    = []

    @field_validator("word")
    @classmethod
    def normalise_word(cls, v: str) -> str:
        return v.lower().strip()


class VocabStatusUpdate(BaseModel):
    status: VocabStatus


class EnrichRequest(BaseModel):
    word:        str
    sentence:    str = ""
    source_lang: str = "en"
    target_lang: str = "fr"


# ── Responses ─────────────────────────────────────────────────────────────────

class VocabOut(BaseModel):
    id:          int
    word:        str
    source_lang: str
    target_lang: str
    translation: str | None
    pos:         str | None
    phonetic:    str | None
    explanation: str | None
    status:      VocabStatus
    count:       int
    contexts:    list[str]
    timestamps:  list[str]
    created_at:  datetime
    updated_at:  datetime

    model_config = {"from_attributes": True}

    @field_validator("contexts", "timestamps", mode="before")
    @classmethod
    def parse_json_list(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v or []


class EnrichOut(BaseModel):
    translation:         str
    pos:                 str
    phonetic:            str
    explanation:         str
    sentence_translation: str
