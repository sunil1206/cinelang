"""
LangGraph subtitle analysis workflow.

Graph: Orchestrator → [Translation, Grammar, CEFR, Idiom, Vocabulary] → Scene Analysis → Quiz

Each node is an independent agent. The graph state flows through all nodes.
All agents use the ProviderManager for resilient AI calls.
"""
from __future__ import annotations
import logging
import re
from typing import TypedDict, Annotated
import operator

from app.providers.manager import provider_manager
from app.offline.dictionary import search_idioms

log = logging.getLogger(__name__)


# ── Graph State ───────────────────────────────────────────────────────────────

class WorkflowState(TypedDict):
    # Input
    subtitle_blocks:  list[dict]    # [{index, text, start, end}]
    source_lang:      str
    target_lang:      str
    movie_title:      str

    # Translation agent output
    translated_blocks: list[dict]   # [{index, original, text, start, end}]
    translation_provider: str

    # Vocabulary agent output
    raw_vocab:        list[dict]    # spaCy extracted words with POS/lemma
    enriched_vocab:   Annotated[list[dict], operator.add]  # final enriched vocab

    # Grammar agent output
    grammar_notes:    list[dict]    # [{pattern, example, explanation}]

    # CEFR agent output
    cefr_distribution: dict         # {A1: 5, A2: 10, ...}
    dominant_cefr:    str

    # Idiom agent output
    idioms_found:     list[dict]

    # Scene analysis output
    scene_summary:    str
    key_themes:       list[str]

    # Quiz output
    quiz_questions:   list[dict]

    # Meta
    errors:           Annotated[list[str], operator.add]
    provider_used:    str


# ── Agent nodes ───────────────────────────────────────────────────────────────

def translation_agent(state: WorkflowState) -> dict:
    """Translate subtitle blocks using the provider chain."""
    try:
        blocks = [
            {"index": b["index"], "text": b["text"]}
            for b in state["subtitle_blocks"]
        ]
        result = provider_manager.translate_batch(
            blocks, state["source_lang"], state["target_lang"]
        )
        tmap = {t["index"]: t["text"] for t in result.translations}
        translated = [
            {
                "index":    b["index"],
                "start":    b.get("start", ""),
                "end":      b.get("end", ""),
                "original": b["text"],
                "text":     tmap.get(b["index"], b["text"]),
            }
            for b in state["subtitle_blocks"]
        ]
        return {
            "translated_blocks": translated,
            "translation_provider": result.provider,
            "errors": [],
        }
    except Exception as exc:
        log.error("translation_agent error: %s", exc)
        # Fallback: echo originals
        fallback = [
            {**b, "original": b["text"]}
            for b in state["subtitle_blocks"]
        ]
        return {
            "translated_blocks": fallback,
            "translation_provider": "echo",
            "errors": [f"translation_agent: {exc}"],
        }


def vocabulary_agent(state: WorkflowState) -> dict:
    """Extract vocabulary using spaCy on translated text."""
    try:
        translated = state.get("translated_blocks", [])
        if not translated:
            return {"raw_vocab": [], "errors": []}

        # Use spaCy pipeline
        from app.services.nlp.pipeline import extract_vocabulary
        full_text = " ".join(b["text"] for b in translated if b.get("text"))
        contexts  = {b["text"][:80]: b for b in translated if b.get("text")}
        vocab = extract_vocabulary(
            full_text,
            lang_code=state["target_lang"],
            source_frames=translated,
        )
        return {"raw_vocab": vocab, "errors": []}
    except Exception as exc:
        log.error("vocabulary_agent error: %s", exc)
        return {"raw_vocab": [], "errors": [f"vocabulary_agent: {exc}"]}


def enrichment_agent(state: WorkflowState) -> dict:
    """Enrich top vocabulary words via the provider chain."""
    try:
        raw = state.get("raw_vocab", [])[:20]  # top 20 words
        enriched = []

        for v in raw:
            word    = v.get("word", "")
            lemma   = v.get("lemma", word)
            context = v.get("example", "")

            result = provider_manager.enrich_word(
                word=word,
                lemma=lemma,
                context=context,
                source_lang=state["target_lang"],   # word is in target lang
                target_lang=state["source_lang"],   # translate to source lang
            )
            enriched.append({
                **v,
                **result,
                "word":  word,
                "lemma": lemma,
            })

        return {"enriched_vocab": enriched, "errors": []}
    except Exception as exc:
        log.error("enrichment_agent error: %s", exc)
        return {"enriched_vocab": state.get("raw_vocab", []), "errors": [f"enrichment_agent: {exc}"]}


def grammar_agent(state: WorkflowState) -> dict:
    """Identify grammar patterns in the translated text (rule-based)."""
    try:
        translated = state.get("translated_blocks", [])
        tgt = state["target_lang"]

        notes = []
        _PATTERNS_FR = [
            (r"\bne\s+\w+\s+pas\b",  "Negation (ne...pas)",     "Standard French negation structure"),
            (r"\bc'est\b",            "C'est construction",       "Used to describe or introduce things"),
            (r"\bil\s+faut\b",        "Il faut + infinitive",     "Expresses necessity — 'it is necessary'"),
            (r"\bje\s+vais\b",        "Near future (aller+inf)",  "Immediate future: je vais + infinitive"),
            (r"\bon\s+\w+",           "Indefinite pronoun 'on'",  "Used colloquially instead of 'nous'"),
            (r"\bqu[ei]\b",           "Relative pronoun que/qui", "Links clauses — qui (subject), que (object)"),
        ]
        _PATTERNS_DE = [
            (r"\bich\s+habe\b",    "Perfekt with haben",    "Past tense formed with haben + past participle"),
            (r"\bich\s+bin\b",     "Sein conjugation",      "Verb 'to be' — also used in Perfekt"),
            (r"\bwird\b",          "Future with werden",    "German future tense construction"),
            (r"\bkein\w*\b",       "Kein negation",         "Negating nouns — kein/keine/keinen"),
        ]
        patterns = _PATTERNS_FR if tgt == "fr" else _PATTERNS_DE

        full_text = " ".join(b["text"] for b in translated)
        seen = set()
        for pattern, name, explanation in patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches and name not in seen:
                seen.add(name)
                notes.append({
                    "pattern":     name,
                    "example":     matches[0],
                    "explanation": explanation,
                    "count":       len(matches),
                })

        return {"grammar_notes": notes, "errors": []}
    except Exception as exc:
        return {"grammar_notes": [], "errors": [f"grammar_agent: {exc}"]}


def cefr_agent(state: WorkflowState) -> dict:
    """Classify vocabulary distribution by CEFR level."""
    try:
        from wordfreq import zipf_frequency

        _WF_LANG = {
            "fr": "fr", "de": "de", "es": "es", "it": "it",
            "pt": "pt", "nl": "nl", "ja": "ja", "zh": "zh",
        }
        _THRESHOLDS = [(6.0, "A1"), (5.0, "A2"), (4.0, "B1"), (3.0, "B2"), (0.0, "C1")]

        tgt   = state["target_lang"]
        wlang = _WF_LANG.get(tgt, "en")
        dist  = {"A1": 0, "A2": 0, "B1": 0, "B2": 0, "C1": 0}

        for v in state.get("raw_vocab", []):
            w    = v.get("lemma", v.get("word", ""))
            zipf = zipf_frequency(w.lower(), wlang)
            for threshold, level in _THRESHOLDS:
                if zipf >= threshold:
                    dist[level] += 1
                    break

        dominant = max(dist, key=lambda k: dist[k]) if any(dist.values()) else "B1"
        return {"cefr_distribution": dist, "dominant_cefr": dominant, "errors": []}
    except Exception as exc:
        return {"cefr_distribution": {}, "dominant_cefr": "B1", "errors": [f"cefr_agent: {exc}"]}


def idiom_agent(state: WorkflowState) -> dict:
    """Detect idioms and slang in the subtitle text."""
    try:
        full_text = " ".join(
            b["text"] for b in state.get("translated_blocks", []) if b.get("text")
        )
        # Offline detection first
        idioms = search_idioms(full_text)

        # Also check raw vocab for slang markers
        for v in state.get("raw_vocab", []):
            if v.get("isSlang") or v.get("isIdiom"):
                if not any(i["word"] == v["word"] for i in idioms):
                    idioms.append(v)

        return {"idioms_found": idioms, "errors": []}
    except Exception as exc:
        return {"idioms_found": [], "errors": [f"idiom_agent: {exc}"]}


def scene_agent(state: WorkflowState) -> dict:
    """Generate a brief scene summary (rule-based, no LLM needed)."""
    try:
        blocks  = state.get("translated_blocks", [])
        n       = len(blocks)
        idioms  = len(state.get("idioms_found", []))
        vocab   = len(state.get("raw_vocab", []))
        cefr    = state.get("dominant_cefr", "B1")
        themes  = []

        full = " ".join(b["text"] for b in blocks).lower()
        _KEYWORDS = {
            "police / crime":    ["police", "crime", "kill", "arrest", "murder", "suspect"],
            "romance":           ["love", "kiss", "heart", "darling", "beautiful", "together"],
            "family":            ["mother", "father", "sister", "brother", "family", "home"],
            "action / tension":  ["run", "fight", "danger", "hurry", "stop", "now"],
            "drama / emotion":   ["cry", "feel", "sad", "happy", "angry", "afraid"],
        }
        for theme, kws in _KEYWORDS.items():
            if sum(1 for kw in kws if kw in full) >= 2:
                themes.append(theme)

        summary = (
            f"Scene with {n} subtitle frames. "
            f"Dominant CEFR level: {cefr}. "
            f"Vocabulary extracted: {vocab} words. "
            f"Idioms/slang found: {idioms}. "
            + (f"Themes detected: {', '.join(themes[:3])}." if themes else "")
        )
        return {"scene_summary": summary, "key_themes": themes[:5], "errors": []}
    except Exception as exc:
        return {"scene_summary": "", "key_themes": [], "errors": [f"scene_agent: {exc}"]}


def quiz_agent(state: WorkflowState) -> dict:
    """Generate quiz questions from enriched vocabulary."""
    try:
        from app.agents.quiz_generator import generate_session
        vocab = state.get("enriched_vocab", []) or state.get("raw_vocab", [])
        if len(vocab) < 3:
            return {"quiz_questions": [], "errors": []}
        questions = generate_session(vocab, session_size=min(10, len(vocab)))
        return {"quiz_questions": questions, "errors": []}
    except Exception as exc:
        return {"quiz_questions": [], "errors": [f"quiz_agent: {exc}"]}


# ── Build LangGraph ────────────────────────────────────────────────────────────

def build_graph():
    try:
        from langgraph.graph import StateGraph, END

        g = StateGraph(WorkflowState)

        g.add_node("translation",  translation_agent)
        g.add_node("vocabulary",   vocabulary_agent)
        g.add_node("grammar",      grammar_agent)
        g.add_node("cefr",         cefr_agent)
        g.add_node("idiom",        idiom_agent)
        g.add_node("enrichment",   enrichment_agent)
        g.add_node("scene",        scene_agent)
        g.add_node("quiz",         quiz_agent)

        g.set_entry_point("translation")

        # After translation: run parallel independent agents
        g.add_edge("translation", "vocabulary")
        g.add_edge("translation", "grammar")
        g.add_edge("translation", "idiom")
        g.add_edge("vocabulary",  "cefr")
        g.add_edge("vocabulary",  "enrichment")
        g.add_edge("enrichment",  "scene")
        g.add_edge("cefr",        "scene")
        g.add_edge("idiom",       "scene")
        g.add_edge("grammar",     "scene")
        g.add_edge("scene",       "quiz")
        g.add_edge("quiz",        END)

        return g.compile()
    except Exception as exc:
        log.warning("LangGraph not available, using sequential fallback: %s", exc)
        return None


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def run_pipeline(
    subtitle_blocks: list[dict],
    source_lang: str = "en",
    target_lang: str = "fr",
    movie_title: str = "",
) -> WorkflowState:
    """
    Run the full subtitle analysis pipeline.
    Falls back to sequential execution if LangGraph is unavailable.
    """
    initial: WorkflowState = {
        "subtitle_blocks":   subtitle_blocks,
        "source_lang":       source_lang,
        "target_lang":       target_lang,
        "movie_title":       movie_title,
        "translated_blocks": [],
        "raw_vocab":         [],
        "enriched_vocab":    [],
        "grammar_notes":     [],
        "cefr_distribution": {},
        "dominant_cefr":     "B1",
        "idioms_found":      [],
        "scene_summary":     "",
        "key_themes":        [],
        "quiz_questions":    [],
        "errors":            [],
        "translation_provider": "",
        "provider_used":     "",
    }

    graph = get_graph()
    if graph:
        try:
            return graph.invoke(initial)
        except Exception as exc:
            log.error("LangGraph execution failed, using sequential: %s", exc)

    # Sequential fallback
    state = dict(initial)
    for agent in [
        translation_agent, vocabulary_agent, grammar_agent, cefr_agent,
        idiom_agent, enrichment_agent, scene_agent, quiz_agent,
    ]:
        try:
            updates = agent(state)  # type: ignore[arg-type]
            state.update(updates)
        except Exception as exc:
            state["errors"].append(f"{agent.__name__}: {exc}")

    return state  # type: ignore[return-value]
