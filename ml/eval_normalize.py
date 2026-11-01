"""Recovery rate of normalize() against ml/obfuscate.py on 1,000 YouTube positives."""

import random
import re
import sys

from data import load_training_frame
from obfuscate import TECHNIQUES, obfuscate
from app.detect.normalize import normalize  # backend path added by obfuscate

URL = re.compile(r"\S*://\S*|www\.\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|id|xyz|io|me|co|vip|link|site|info|top)\b\S*", re.I)


def censor(text: str, limit: int = 100) -> str:
    text = URL.sub("[DISENSOR]", text)
    return text if len(text) <= limit else text[:limit] + "…"


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    frame = load_training_frame()
    positives = frame.loc[frame["source"].eq("youtube") & frame["label"].eq(1), "text"]
    texts = positives.sample(1000, random_state=42).tolist()
    expected = [normalize(text) for text in texts]

    rows, failures = [], []
    for name in (*TECHNIQUES, "total"):
        rng = random.Random(42)
        techniques = tuple(TECHNIQUES) if name == "total" else (name,)
        changed = recovered = 0
        for text, target in zip(texts, expected):
            variant = obfuscate(text, rng, techniques=techniques)
            got = normalize(variant)
            changed += variant != text
            if got == target:
                recovered += 1
            elif sum(f[0] == name for f in failures) < 2 or (name == "total" and len(failures) < 10):
                failures.append((name, target, got))
        rows.append((name, changed, recovered))

    print("| Teknik | Teks berubah | Pulih | recovery_rate |")
    print("| --- | ---: | ---: | ---: |")
    for name, changed, recovered in rows:
        print(f"| {name} | {changed} | {recovered} | {recovered / len(texts):.1%} |")
    print("\n10 contoh gagal (maks. 2 per teknik, sisanya dari total), normalize(x) vs normalize(obfuscate(x)):")
    for i, (name, target, got) in enumerate(failures[:10], 1):
        print(f"{i}. [{name}] harap: {censor(target)}\n   dapat: {censor(got)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
