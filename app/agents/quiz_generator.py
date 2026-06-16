"""
Agent 3 — Quiz Generator

Generates three quiz types from user vocabulary — no LLM required.
  1. Fill-in-the-blank  (from context sentence)
  2. Multiple choice    (4 options, siblings from same CEFR/POS group)
  3. Translation        (target → source)

LLM is used ONLY when no context sentence exists and we need a fresh example.
"""
from __future__ import annotations
import random
import re
from dataclasses import dataclass, field


@dataclass
class QuizQuestion:
    q_type:   str        # fill_blank / multiple_choice / translation
    prompt:   str        # question text shown to user
    answer:   str        # correct answer
    options:  list[str] = field(default_factory=list)  # MCQ only
    hint:     str = ""
    word:     str = ""
    cefr:     str = ""


def generate_fill_blank(word: dict) -> QuizQuestion | None:
    """
    Replaces the target word in its context sentence with a blank.
    Returns None if no usable context sentence exists.
    """
    raw_ctx = word.get("context_sentence") or (word.get("contexts") or [None])[0]
    # contexts may be dicts like {"text": "..."} or plain strings
    if isinstance(raw_ctx, dict):
        raw_ctx = raw_ctx.get("text") or raw_ctx.get("sentence", "")
    context = raw_ctx if isinstance(raw_ctx, str) else ""
    if not context:
        return None

    lemma = word.get("lemma", word.get("word", ""))
    surface = word.get("word", lemma)

    # Replace the word (or its inflected form) with ___
    pattern = re.compile(re.escape(surface), re.IGNORECASE)
    blanked  = pattern.sub("_____", context, count=1)
    if blanked == context:
        # Couldn't replace surface form — try lemma
        pattern = re.compile(re.escape(lemma), re.IGNORECASE)
        blanked  = pattern.sub("_____", context, count=1)
    if blanked == context:
        return None

    return QuizQuestion(
        q_type="fill_blank",
        prompt=f"Fill in the blank:\n\n{blanked}",
        answer=surface,
        hint=word.get("translation") or "",
        word=lemma,
        cefr=word.get("cefr", "B1"),
    )


def generate_mcq(word: dict, all_words: list[dict]) -> QuizQuestion:
    """
    Multiple choice: given the definition/translation, pick the correct word.
    Distractors are words with the same POS and nearby CEFR level.
    """
    correct = word.get("translation") or word.get("lemma", "")
    definition = word.get("definition") or f"The {word.get('pos','word').lower()}: {word.get('lemma','')}"

    # Pick 3 distractors from same POS group
    same_pos = [w for w in all_words
                if w.get("pos") == word.get("pos")
                and w.get("lemma") != word.get("lemma")
                and w.get("translation")]
    random.shuffle(same_pos)
    distractors = [w["translation"] for w in same_pos[:3]]

    # Pad with generic distractors if needed
    while len(distractors) < 3:
        distractors.append(f"option_{len(distractors)+1}")

    options = [correct] + distractors[:3]
    random.shuffle(options)

    return QuizQuestion(
        q_type="multiple_choice",
        prompt=f"Which word means:\n\n\"{definition}\"",
        answer=correct,
        options=options,
        word=word.get("lemma", ""),
        cefr=word.get("cefr", "B1"),
    )


def generate_translation(word: dict) -> QuizQuestion:
    """
    Show the word in the target language — user types the translation.
    """
    lemma       = word.get("lemma", word.get("word", ""))
    translation = word.get("translation") or ""
    if isinstance(translation, dict):
        translation = str(translation)
    ipa         = word.get("ipa") or ""
    hint        = f"/{ipa}/" if ipa else ""

    return QuizQuestion(
        q_type="translation",
        prompt=f"Translate this word:\n\n**{lemma}**",
        answer=translation,
        hint=hint,
        word=lemma,
        cefr=word.get("cefr", "B1"),
    )


def generate_session(
    vocab_items: list[dict],
    session_size: int = 10,
    mix: tuple[float, float, float] = (0.4, 0.4, 0.2),  # fill/mcq/trans ratios
) -> list[QuizQuestion]:
    """
    Generate a mixed quiz session from vocabulary items.
    """
    if not vocab_items:
        return []

    items  = random.sample(vocab_items, min(len(vocab_items), session_size))
    fill_n = int(session_size * mix[0])
    mcq_n  = int(session_size * mix[1])
    tra_n  = session_size - fill_n - mcq_n

    questions: list[QuizQuestion] = []

    for item in items[:fill_n]:
        q = generate_fill_blank(item)
        if q:
            questions.append(q)

    for item in items[fill_n:fill_n + mcq_n]:
        questions.append(generate_mcq(item, vocab_items))

    for item in items[fill_n + mcq_n:fill_n + mcq_n + tra_n]:
        q = generate_translation(item)
        if q.answer:
            questions.append(q)

    random.shuffle(questions)
    return questions
