W_HIDDEN = 0.6
W_TEXT = 0.7
THRESHOLD = 0.5


def risk(s_hidden: float, s_text_hidden: float) -> tuple[float, str]:
    """Noisy-OR of L2 and L3 (hidden text only); deterministic, never decided by an LLM."""
    r = 1 - (1 - W_HIDDEN * s_hidden) * (1 - W_TEXT * s_text_hidden)
    return r, "terindikasi" if r >= THRESHOLD else "aman"
