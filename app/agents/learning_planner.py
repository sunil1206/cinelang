"""
Agent 2 — Learning Planner

Builds a structured 30-day curriculum using Groq (Llama 3.3 70B).
Falls back to a rule-based plan when no LLM key is available.

The plan is language-specific and CEFR-aware.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field


@dataclass
class DailyPlan:
    day:         int
    focus:       str        # e.g. "Present tense verbs (A1)"
    new_words:   int = 10
    review_words:int = 5
    grammar_tip: str = ""
    goal:        str = ""


@dataclass
class LearningPlan:
    lang_code:  str
    lang_name:  str
    cefr_start: str
    cefr_target:str
    days:       list[DailyPlan] = field(default_factory=list)
    overview:   str = ""


def generate(
    lang_code:   str,
    lang_name:   str,
    cefr_current:str,
    cefr_target: str,
    weak_areas:  list[str] | None = None,
    days:        int = 30,
) -> LearningPlan:
    """
    Generate a learning plan. Uses Groq if available, otherwise rule-based.
    """
    # Try LLM first
    plan = _llm_plan(lang_code, lang_name, cefr_current, cefr_target, weak_areas or [], days)
    if plan:
        return plan
    return _rule_plan(lang_code, lang_name, cefr_current, cefr_target, days)


def _llm_plan(lang_code, lang_name, cefr, target, weak_areas, days) -> LearningPlan | None:
    try:
        from app.services.groq_service import _no_key
        if _no_key():
            return None

        from groq import Groq
        from app.config import get_settings
        settings = get_settings()
        client   = Groq(api_key=settings.groq_api_key)

        prompt = f"""Create a {days}-day {lang_name} learning plan for a {cefr} learner targeting {target}.
Weak areas: {weak_areas or 'none specified'}.

Return JSON: {{
  "overview": "2-sentence summary",
  "days": [
    {{"day": 1, "focus": "...", "new_words": 10, "review_words": 5, "grammar_tip": "...", "goal": "..."}}
    ... (all {days} days)
  ]
}}"""

        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=3000,
            temperature=0.3,
        )
        data = json.loads(resp.choices[0].message.content)
        return LearningPlan(
            lang_code=lang_code, lang_name=lang_name,
            cefr_start=cefr, cefr_target=target,
            overview=data.get("overview", ""),
            days=[DailyPlan(**d) for d in data.get("days", [])[:days]],
        )
    except Exception:
        return None


def _rule_plan(lang_code, lang_name, cefr, target, days) -> LearningPlan:
    """Deterministic fallback plan based on CEFR structure."""
    _THEMES_FR = [
        "Greetings & basics", "Numbers & time", "Family vocabulary",
        "Food & restaurants", "Travel & transport", "Work & professions",
        "Emotions & personality", "Nature & weather", "Arts & culture",
        "Present tense verbs", "Past tense (passé composé)", "Future tense",
        "Adjective agreement", "Negation patterns", "Question forms",
        "Pronouns", "Prepositions", "Conjunctions",
        "Modal verbs", "Subjunctive introduction", "Conditional mood",
        "Formal vs informal register", "French idioms", "News & current events",
        "Literature vocabulary", "Academic language", "Business French",
        "Regional expressions", "Review & consolidation", "Assessment day",
    ]
    _THEMES_DE = [
        "Greetings & basics", "Numbers & cases (Nominativ)", "Family vocabulary",
        "Food & restaurants", "Travel & transport", "Der/Die/Das articles",
        "Plural forms", "Accusative case", "Dative case",
        "Genitive case", "Separable verbs", "Modal verbs",
        "Vergangenheit (Perfekt)", "Präteritum", "Future (werden)",
        "Adjective declension", "Relative clauses", "Subordinate clauses",
        "Konjunktiv II", "Passive voice", "German idioms",
        "Regional dialects", "Formal writing", "Business German",
        "Academic vocabulary", "Literature terms", "News language",
        "Review week 1", "Review week 2", "Assessment day",
    ]
    themes = _THEMES_DE if lang_code == "de" else _THEMES_FR

    day_plans = []
    for i in range(min(days, len(themes))):
        theme = themes[i]
        new_w = 12 if i < 7 else (10 if i < 14 else 8)
        rev_w = max(5, i * 2)
        day_plans.append(DailyPlan(
            day=i + 1,
            focus=f"{theme} ({cefr})",
            new_words=new_w,
            review_words=min(rev_w, 20),
            grammar_tip=f"Focus on {theme.lower()} patterns.",
            goal=f"Master {new_w} new {lang_name} words.",
        ))

    return LearningPlan(
        lang_code=lang_code, lang_name=lang_name,
        cefr_start=cefr, cefr_target=target,
        overview=f"30-day structured {lang_name} curriculum from {cefr} to {target}. "
                 f"Covers core vocabulary, grammar patterns, and cultural expressions.",
        days=day_plans,
    )
