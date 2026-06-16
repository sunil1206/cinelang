"""
LangGraph vocabulary tutor agent.

Graph:
  START → analyse → enrich → respond → END
           ↑_________↓ (if needs_clarification)

The agent receives a word + context, analyses it with spaCy,
enriches via Ollama/Gemma, and returns structured study notes.
"""
from __future__ import annotations

from typing import TypedDict, Annotated
import operator

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.ai.ollama_client import get_llm
from app.services.ai.spacy_service import extract_content_words, extract_entities
from app.config import get_settings

settings = get_settings()


# ── Agent state ───────────────────────────────────────────────────────────────

class TutorState(TypedDict):
    messages:       Annotated[list[BaseMessage], operator.add]
    word:           str
    context:        str
    source_lang:    str
    target_lang:    str
    spacy_analysis: dict
    enrichment:     dict
    needs_retry:    bool


# ── Nodes ─────────────────────────────────────────────────────────────────────

def analyse_node(state: TutorState) -> dict:
    """Use spaCy to analyse the word and its context sentence."""
    word    = state["word"]
    context = state["context"]
    lang    = state["target_lang"]

    content_words = extract_content_words(context, lang)
    entities      = extract_entities(context, lang)

    return {
        "spacy_analysis": {
            "content_words": content_words,
            "entities":      entities,
            "word_in_context": word in context.lower(),
        }
    }


def enrich_node(state: TutorState) -> dict:
    """Ask Gemma 3 to produce a structured vocabulary card."""
    word    = state["word"]
    context = state["context"]
    src     = state["source_lang"]
    tgt     = state["target_lang"]
    analysis = state["spacy_analysis"]

    prompt = f"""You are a language-learning assistant.

Word to study: "{word}" ({tgt})
Example sentence: "{context}"
Learner's language: {src}
spaCy content words found nearby: {', '.join(analysis.get('content_words', [])[:8])}

Provide a JSON vocabulary card with these exact keys:
{{
  "translation": "...",
  "pos": "Noun|Verb|Adjective|Adverb|Idiom|Phrase",
  "phonetic": "IPA or pronunciation guide",
  "explanation": "one sentence cultural/usage note",
  "example_translation": "fluent {src} translation of the example sentence",
  "difficulty": "A1|A2|B1|B2|C1|C2",
  "mnemonics": "a short memory trick"
}}

Reply with ONLY valid JSON, no markdown fences."""

    llm = get_llm(temperature=0.2)
    response = llm.invoke([HumanMessage(content=prompt)])

    import json, re
    raw = response.content.strip()
    # Strip markdown fences if model adds them anyway
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        enrichment = json.loads(raw)
        needs_retry = False
    except json.JSONDecodeError:
        enrichment = {"raw": raw}
        needs_retry = True

    return {
        "messages":   [AIMessage(content=raw)],
        "enrichment": enrichment,
        "needs_retry": needs_retry,
    }


def respond_node(state: TutorState) -> dict:
    """Format the final response."""
    enrichment = state["enrichment"]
    word       = state["word"]

    if "raw" in enrichment:
        # Fallback — Gemma returned non-JSON
        summary = f"Could not parse enrichment for '{word}'. Raw: {enrichment['raw'][:200]}"
    else:
        summary = (
            f"**{word}** ({enrichment.get('pos','?')}) · {enrichment.get('phonetic','')}\n"
            f"→ {enrichment.get('translation','')}\n"
            f"💡 {enrichment.get('explanation','')}\n"
            f"📚 {enrichment.get('difficulty','?')} · {enrichment.get('mnemonics','')}"
        )

    return {"messages": [AIMessage(content=summary)]}


# ── Graph assembly ────────────────────────────────────────────────────────────

def _should_retry(state: TutorState) -> str:
    return "enrich" if state.get("needs_retry") else "respond"


def build_tutor_graph() -> StateGraph:
    g = StateGraph(TutorState)
    g.add_node("analyse", analyse_node)
    g.add_node("enrich",  enrich_node)
    g.add_node("respond", respond_node)

    g.add_edge(START,     "analyse")
    g.add_edge("analyse", "enrich")
    g.add_conditional_edges("enrich", _should_retry, {"enrich": "enrich", "respond": "respond"})
    g.add_edge("respond", END)

    return g


# Compile once with in-memory checkpointer (swap for Postgres checkpointer in prod)
_memory = MemorySaver()
tutor_graph = build_tutor_graph().compile(checkpointer=_memory)


# ── Public API ────────────────────────────────────────────────────────────────

async def enrich_word_local(
    word: str,
    context: str,
    source_lang: str,
    target_lang: str,
    thread_id: str = "default",
) -> dict:
    """
    Run the tutor agent for one word.
    Returns the enrichment dict (translation, pos, phonetic, explanation, …).
    """
    initial: TutorState = {
        "messages":       [HumanMessage(content=f"Enrich: {word}")],
        "word":           word,
        "context":        context,
        "source_lang":    source_lang,
        "target_lang":    target_lang,
        "spacy_analysis": {},
        "enrichment":     {},
        "needs_retry":    False,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await tutor_graph.ainvoke(initial, config=config)
    return result["enrichment"]
