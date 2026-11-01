"""Keyword fallback for L3 until the trained model lands; same score_text signature."""

import re

from app.detect.normalize import normalize


KEYWORDS = re.compile(
    r"slot|gacor|togel|toto|maxwin|kasino|sbobet|\b4d\b|rtp|jackpot|scatter|pragmatic|mahjong"
)


def keyword_hits(text: str) -> int:
    return len(KEYWORDS.findall(text))


def score_text(text: str) -> float:
    # shortcut: 3 keyword hits saturate; replaced by l3_text.score_text (P4).
    return min(1.0, keyword_hits(normalize(text)) / 3)
