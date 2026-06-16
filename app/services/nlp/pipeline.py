"""
NLP pipeline — spaCy + wordfreq vocabulary extraction.
Extracts lemmatized, POS-tagged, CEFR-classified vocabulary from subtitle text.
"""
from __future__ import annotations
import re
import logging
from collections import Counter

log = logging.getLogger(__name__)

_POS_DISPLAY     = {"NOUN": "Noun", "VERB": "Verb", "ADJ": "Adjective", "ADV": "Adverb"}
_WF_LANG         = {"fr": "fr", "de": "de", "es": "es", "it": "it", "pt": "pt", "en": "en"}
_CEFR_THRESHOLDS = [(6.0, "A1"), (5.0, "A2"), (4.0, "B1"), (3.0, "B2"), (0.0, "C1")]
_SPACY_MODELS    = {"fr": "fr_core_news_sm", "de": "de_core_news_sm", "es": "es_core_news_sm"}

_nlp_cache: dict = {}


def _load_spacy(lang_code: str):
    if lang_code in _nlp_cache:
        return _nlp_cache[lang_code]
    model = _SPACY_MODELS.get(lang_code)
    if not model:
        _nlp_cache[lang_code] = None
        return None
    try:
        import spacy
        nlp = spacy.load(model)
        _nlp_cache[lang_code] = nlp
        return nlp
    except OSError:
        try:
            import spacy
            spacy.cli.download(model)
            nlp = spacy.load(model)
            _nlp_cache[lang_code] = nlp
            return nlp
        except Exception as exc:
            log.warning("spaCy model %s unavailable: %s", model, exc)
            _nlp_cache[lang_code] = None
            return None


def _zipf_to_cefr(word: str, lang_code: str) -> tuple[str, float]:
    try:
        from wordfreq import zipf_frequency
        wf_lang = _WF_LANG.get(lang_code, "en")
        zipf    = zipf_frequency(word.lower(), wf_lang)
        for threshold, level in _CEFR_THRESHOLDS:
            if zipf >= threshold:
                return level, zipf
        return "C1", 0.0
    except Exception:
        return "B1", 3.0


def extract_vocabulary(
    text: str,
    lang_code: str,
    source_frames: list[dict] | None = None,
    top_n: int   = 30,
    min_length: int  = 3,
    min_zipf: float  = 2.0,
) -> list[dict]:
    """
    Full NLP pipeline:
    1. spaCy tokenise + POS + NER (remove proper nouns)
    2. Lemmatize + deduplicate
    3. wordfreq Zipf → CEFR
    4. Filter too-obscure (Zipf < 2.0)
    5. Rank by usefulness
    6. Attach context sentences
    Falls back to frequency-based extraction if spaCy unavailable.
    """
    nlp = _load_spacy(lang_code)
    if nlp:
        return _spacy_extract(text, nlp, lang_code, source_frames, top_n, min_length, min_zipf)
    return _freq_extract(text, source_frames, top_n, min_length)


def _spacy_extract(text, nlp, lang_code, source_frames, top_n, min_length, min_zipf):
    doc      = nlp(text[:50000])
    ner_ents = {e.text.lower() for e in doc.ents if e.label_ in ("PER", "PERSON", "ORG", "GPE", "LOC")}

    counter:   Counter = Counter()
    word_data: dict    = {}

    for token in doc:
        if token.pos_ not in ("NOUN", "VERB", "ADJ", "ADV"):
            continue
        if token.is_stop or token.is_punct or token.like_num:
            continue
        lemma = token.lemma_.lower()
        if len(lemma) < min_length:
            continue
        if not re.match(r"^[a-zA-ZÀ-ÿ\-]+$", lemma):
            continue
        if lemma in ner_ents or token.text.lower() in ner_ents:
            continue

        cefr, zipf = _zipf_to_cefr(lemma, lang_code)
        if zipf < min_zipf:
            continue

        counter[lemma] += 1
        if lemma not in word_data:
            word_data[lemma] = {
                "word": token.text, "lemma": lemma,
                "pos":  _POS_DISPLAY.get(token.pos_, "Noun"),
                "cefr": cefr, "zipf": zipf, "contexts": [],
            }

    # Attach context sentences
    for frame in (source_frames or []):
        txt   = frame.get("text", "")
        ts    = f"{frame.get('start','')} → {frame.get('end','')}"
        for lemma, data in word_data.items():
            if lemma in txt.lower() and len(data["contexts"]) < 3:
                data["contexts"].append({"text": txt, "timestamp": ts})

    _level_score = {"A1": 5, "A2": 4, "B1": 3, "B2": 2, "C1": 1}
    max_count    = max(counter.values()) if counter else 1

    ranked = sorted(
        counter.keys(),
        key=lambda w: (
            _level_score.get(word_data[w]["cefr"], 3) * 0.5
            + (word_data[w]["zipf"] / 7.0) * 0.3
            + (counter[w] / max_count) * 0.2
        ),
        reverse=True,
    )

    return [
        {
            "word":        word_data[lm]["word"],
            "lemma":       lm,
            "pos":         word_data[lm]["pos"],
            "cefr":        word_data[lm]["cefr"],
            "zipf":        word_data[lm]["zipf"],
            "count":       counter[lm],
            "example":     word_data[lm]["contexts"][0]["text"] if word_data[lm]["contexts"] else "",
            "contexts":    word_data[lm]["contexts"],
            "translation": "", "phonetic": "", "explanation": "",
        }
        for lm in ranked[:top_n]
    ]


def _freq_extract(text, source_frames, top_n, min_length):
    """Frequency-based fallback when spaCy is unavailable."""
    _STOP = {
        "the","a","an","is","it","in","on","at","to","of","and","or","but","not",
        "he","she","they","we","i","you","his","her","its","our","their","my","your",
        "was","were","be","been","have","has","did","will","would","could","should",
        "qui","que","est","les","des","une","dans","pas","sur","par","pour","avec",
        "der","die","das","ist","ein","eine","und","oder","nicht","von","mit","zu",
    }
    word_re  = re.compile(r"\b[a-zA-ZÀ-ÿ]{4,}\b")
    counter: Counter = Counter()
    contexts: dict   = {}

    for frame in (source_frames or [{"text": text}]):
        txt = frame.get("text", "")
        for w in word_re.findall(txt.lower()):
            if w not in _STOP:
                counter[w] += 1
                if w not in contexts:
                    contexts[w] = []
                if len(contexts[w]) < 3:
                    contexts[w].append({"text": txt, "timestamp": ""})

    return [
        {
            "word": w, "lemma": w, "pos": "Noun",
            "cefr": "B1", "zipf": 3.0, "count": c,
            "example":   contexts[w][0]["text"] if contexts.get(w) else "",
            "contexts":  contexts.get(w, []),
            "translation": "", "phonetic": "", "explanation": "",
        }
        for w, c in counter.most_common(top_n)
    ]
