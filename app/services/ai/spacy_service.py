"""spaCy NLP pipeline — tokenisation, POS, NER, and content-word extraction."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import NamedTuple

import spacy
from spacy.language import Language


# Map ISO-639-1 codes → spaCy model names (small CPU models)
_MODEL_MAP: dict[str, str] = {
    "en": "en_core_web_sm",
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "es": "es_core_news_sm",
    "it": "it_core_news_sm",
    "pt": "pt_core_news_sm",
    "nl": "nl_core_news_sm",
    "pl": "pl_core_news_sm",
}
_FALLBACK = "xx_ent_wiki_sm"   # multi-language fallback (no POS)


class Token(NamedTuple):
    text: str
    lemma: str
    pos: str       # NOUN, VERB, ADJ, ADV, …
    is_stop: bool


@lru_cache(maxsize=8)
def _load_model(lang: str) -> Language:
    model_name = _MODEL_MAP.get(lang, _FALLBACK)
    try:
        return spacy.load(model_name)
    except OSError:
        # Model not downloaded yet — download it on first use
        spacy.cli.download(model_name)
        return spacy.load(model_name)


def tokenize(text: str, lang: str = "en") -> list[Token]:
    """Return spaCy tokens for a text."""
    nlp = _load_model(lang)
    doc = nlp(text)
    return [
        Token(
            text=tok.text,
            lemma=tok.lemma_.lower(),
            pos=tok.pos_,
            is_stop=tok.is_stop,
        )
        for tok in doc
        if not tok.is_space and not tok.is_punct
    ]


def extract_content_words(
    text: str,
    lang: str = "en",
    pos_filter: set[str] | None = None,
    min_len: int = 3,
) -> list[str]:
    """
    Return lemmatized content words (nouns, verbs, adjectives, adverbs by default).
    Filters out stop-words, punctuation, and tokens shorter than min_len.
    """
    if pos_filter is None:
        pos_filter = {"NOUN", "VERB", "ADJ", "ADV"}

    seen: set[str] = set()
    words: list[str] = []
    for tok in tokenize(text, lang):
        if (
            tok.pos in pos_filter
            and not tok.is_stop
            and len(tok.lemma) >= min_len
            and tok.lemma not in seen
            and re.match(r"^[a-zA-ZÀ-ÿ\-']+$", tok.lemma)
        ):
            seen.add(tok.lemma)
            words.append(tok.lemma)
    return words


def extract_entities(text: str, lang: str = "en") -> list[dict]:
    """Return named entities {text, label} from text."""
    nlp = _load_model(lang)
    doc = nlp(text)
    return [{"text": ent.text, "label": ent.label_} for ent in doc.ents]


def sentences(text: str, lang: str = "en") -> list[str]:
    """Split text into sentences."""
    nlp = _load_model(lang)
    doc = nlp(text)
    return [s.text.strip() for s in doc.sents if s.text.strip()]
