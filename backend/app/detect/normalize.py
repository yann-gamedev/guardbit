"""Deterministic text normalization for L3; keeps URL and email tokens intact."""

import re
import unicodedata

from app.detect.confusables_map import CONFUSABLES


INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
LATIN = str.maketrans(CONFUSABLES)
LEET = str.maketrans("4310578@$", "aeiostbas")
PROTECTED = re.compile(
    r"(?<!\S)("
    r"\S*://\S*|www\.\S+|[^\s@]+@[^\s@]+\.[^\s@]+|[\w-]+(?:\.[\w-]+)+/\S*"
    r")(?!\S)"
)
SPACED = re.compile(
    r"(?<![^\W_])(?<![^\W_][._*·-])"
    r"([^\W\d_](?P<sep>[._*· -])[^\W\d_](?:(?P=sep)[^\W\d_])+)"
    r"(?![^\W_])(?![._*·-][^\W_])"
)
LEETSPEAK = re.compile(r"(?<=[^\W\d_])[4310578@$](?=[^\W\d_])")
REPEATED = re.compile(r"([^\W\d_])\1{2,}")


def _plain(text: str) -> str:
    text = SPACED.sub(lambda match: match.group(1).replace(match.group("sep"), ""), text)
    text = LEETSPEAK.sub(lambda match: match.group().translate(LEET), text)
    return REPEATED.sub(r"\1\1", text)


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(INVISIBLE).translate(LATIN).lower()
    # re.split keeps captured URL/email tokens at odd indexes.
    parts = PROTECTED.split(text)
    parts[::2] = map(_plain, parts[::2])
    return " ".join("".join(parts).split())
