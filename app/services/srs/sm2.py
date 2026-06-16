"""
SM-2 Spaced Repetition algorithm.

Original algorithm by Piotr Woźniak (SuperMemo 2).
Responses: 'again' | 'hard' | 'good' | 'easy'
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class SRSCard:
    ease_factor:   float = 2.5
    interval_days: float = 1.0
    review_count:  int   = 0
    consecutive_correct: int = 0
    lapse_count:   int   = 0


@dataclass
class SRSResult:
    ease_factor:         float
    interval_days:       float
    next_review:         datetime
    new_status:          str
    review_count:        int
    consecutive_correct: int
    lapse_count:         int
    mastery_score:       float


def update(card: SRSCard, response: str) -> SRSResult:
    """
    Apply one SM-2 review step.

    Status transitions:
      new        → learning  (any first review)
      learning   → review    (interval ≥ 3 days)
      review     → mastered  (interval ≥ 21 days)
      mastered   → known     (≥ 5 consecutive correct)
      any        → lapsed    (response == 'again' after mastered)
    """
    ef  = card.ease_factor
    n   = card.review_count
    cc  = card.consecutive_correct
    lap = card.lapse_count

    if response == "again":
        interval = 1.0
        ef       = max(1.3, ef - 0.2)
        cc       = 0
        lap     += 1
    elif response == "hard":
        interval = max(1.0, card.interval_days * 1.2)
        ef       = max(1.3, ef - 0.15)
        cc       = max(0, cc - 1)
    elif response == "good":
        if n == 0:   interval = 1.0
        elif n == 1: interval = 4.0
        else:        interval = card.interval_days * ef
        cc += 1
    else:  # easy
        if n == 0:   interval = 4.0
        elif n == 1: interval = 10.0
        else:        interval = card.interval_days * ef * 1.3
        ef  = min(4.0, ef + 0.15)
        cc += 1

    ef       = round(min(4.0, max(1.3, ef)), 2)
    interval = round(max(1.0, interval), 1)
    n       += 1

    # Determine new status
    if response == "again" and card.interval_days >= 3:
        status = "lapsed"
    elif interval >= 21 and cc >= 3:
        status = "mastered"
    elif cc >= 5:
        status = "known"
    elif interval >= 3:
        status = "review"
    elif n >= 1:
        status = "learning"
    else:
        status = "new"

    # Mastery score: weighted combination of interval and ease
    mastery = min(1.0, (interval / 30) * 0.6 + ((ef - 1.3) / 2.7) * 0.4)

    now        = datetime.now(timezone.utc)
    next_review = now + timedelta(days=interval)

    return SRSResult(
        ease_factor=ef,
        interval_days=interval,
        next_review=next_review,
        new_status=status,
        review_count=n,
        consecutive_correct=cc,
        lapse_count=lap,
        mastery_score=round(mastery, 3),
    )


def xp_for_response(response: str, interval_days: float) -> int:
    """XP earned for a review response."""
    base = {"again": 1, "hard": 3, "good": 5, "easy": 7}.get(response, 0)
    # Bonus for longer intervals (reviewing mature cards)
    bonus = min(10, int(interval_days / 7))
    return base + bonus
