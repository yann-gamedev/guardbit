"""Random obfuscation of comment text for L3 training variants and normalize evaluation."""

from pathlib import Path
import random
import re
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.detect.confusables_map import CONFUSABLES  # noqa: E402

# Mathematical Alphanumeric bases (capital A); small a = base + 26.
MATH_BASES = (0x1D400, 0x1D434, 0x1D468, 0x1D5A0, 0x1D5D4, 0x1D608, 0x1D63C)
MATH_HOLES = {0x1D455: "\u210e"}  # italic small h lives in Letterlike Symbols
ZERO_WIDTH = "\u200b\u200c\u200d\u2060\u00ad"
LEET = dict(zip("aeiostbAEIOSTB", "43105784310578"))
HOMOGLYPHS: dict[str, list[str]] = {}
for source, target in sorted(CONFUSABLES.items()):
    # Only Cyrillic/Greek lookalikes that survive NFKC, so normalize sees them as written.
    if unicodedata.name(source, "").startswith(("CYRILLIC", "GREEK")) and unicodedata.normalize("NFKC", source) == source:
        HOMOGLYPHS.setdefault(target, []).append(source)
LETTER_RUN = re.compile(r"[^\W\d_]{3,}")


def _math(token: str, rng: random.Random) -> str:
    base = rng.choice(MATH_BASES)
    out = []
    for char in token:
        if "A" <= char <= "Z" or "a" <= char <= "z":
            code = base + (ord(char) - 65 if char <= "Z" else ord(char) - 97 + 26)
            out.append(MATH_HOLES.get(code, chr(code)))
        else:
            out.append(char)
    return "".join(out)


def _fullwidth(token: str, rng: random.Random) -> str:
    return "".join(chr(ord(c) + 0xFEE0) if c.isascii() and c.isalnum() else c for c in token)


def _zero_width(token: str, rng: random.Random) -> str:
    chars = list(token)
    for _ in range(rng.randint(1, max(1, len(token) // 2))):
        chars.insert(rng.randint(0, len(chars)), rng.choice(ZERO_WIDTH))
    return "".join(chars)


def _homoglyph(token: str, rng: random.Random) -> str:
    return "".join(rng.choice(HOMOGLYPHS[c]) if c in HOMOGLYPHS and rng.random() < 0.5 else c for c in token)


def _leet(token: str, rng: random.Random) -> str:
    # ponytail: only interior letters with non-substituted letter neighbours (g4c0r style);
    # edge leet ("4lexis") skipped, add when L3 eval shows it in real spam.
    out = list(token)
    previous = False
    for i in range(1, len(token) - 1):
        swap = (
            not previous and token[i] in LEET and token[i - 1].isalpha() and token[i + 1].isalpha() and rng.random() < 0.5
        )
        if swap:
            out[i] = LEET[token[i]]
        previous = swap
    return "".join(out)


def _separator(token: str, rng: random.Random) -> str:
    sep = rng.choice(".-")
    return LETTER_RUN.sub(lambda m: sep.join(m.group()), token)


def _spacing(token: str, rng: random.Random) -> str:
    spaced = LETTER_RUN.sub(lambda m: " ".join(m.group()), token)
    # Wider gap keeps adjacent spaced words apart ("s l o t   g a c o r"), as spammers write them.
    return f"  {spaced}  " if spaced != token else token


def _repeat(token: str, rng: random.Random) -> str:
    letters = [i for i, c in enumerate(token) if c.isalpha()]
    if not letters:
        return token
    i = letters[-1]
    return token[: i + 1] + token[i] * rng.randint(2, 4) + token[i + 1 :]


TECHNIQUES = {
    "matematis": _math,
    "fullwidth": _fullwidth,
    "zero_width": _zero_width,
    "kiril_yunani": _homoglyph,
    "leet": _leet,
    "pemisah": _separator,
    "spasi": _spacing,
    "ulang": _repeat,
}


def obfuscate(text: str, rng: random.Random, p: float = 0.5, techniques=tuple(TECHNIQUES)) -> str:
    """Obfuscate each whitespace token with probability p using one random technique."""
    parts = re.split(r"(\s+)", text)
    for i in range(0, len(parts), 2):
        if parts[i] and rng.random() < p:
            parts[i] = TECHNIQUES[rng.choice(techniques)](parts[i], rng)
    return "".join(parts)


def make_variants(texts: list[str], n: int, seed: int) -> list[str]:
    """n obfuscated variants of randomly chosen texts; same seed gives the same list."""
    rng = random.Random(seed)
    return [obfuscate(rng.choice(texts), rng) for _ in range(n)]
