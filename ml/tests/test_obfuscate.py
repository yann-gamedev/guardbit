from pathlib import Path
import random
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from obfuscate import TECHNIQUES, make_variants, obfuscate  # noqa: E402
from app.detect.normalize import normalize  # noqa: E402

SENTENCES = [
    "slot gacor hari ini",
    "situs judi online terpercaya",
    "main togel dapat jackpot besar",
    "daftar sekarang bonus member baru",
    "kasino online paling aman",
    "pasti menang setiap hari",
    "link alternatif resmi gampang maxwin",
    "deposit pulsa tanpa potongan",
    "bandar bola terbesar di asia",
    "info gacor buat kalian semua",
    "Bikin aku jadi sultan beneran",
    "Rekomendasi situs paling hoki",
    "akhirnya bisa bayar utang juga",
    "coba main di sini pasti cuan",
    "pola jitu sore ini mantap",
    "kemenangan beruntun tiap malam",
    "admin ramah proses cepat",
    "withdraw lancar tanpa ribet",
    "terima kasih sudah berbagi info",
    "rasakan sensasi menang besar",
]


def test_deterministic_with_seed():
    assert obfuscate(SENTENCES[0], random.Random(7)) == obfuscate(SENTENCES[0], random.Random(7))
    assert make_variants(SENTENCES, 50, seed=3) == make_variants(SENTENCES, 50, seed=3)
    assert len(make_variants(SENTENCES, 50, seed=3)) == 50


def test_p1_changes_every_text():
    rng = random.Random(0)
    for text in SENTENCES:
        assert obfuscate(text, rng, p=1.0) != text
    for name in TECHNIQUES:
        assert obfuscate("gacor", random.Random(1), p=1.0, techniques=(name,)) != "gacor", name


RECOVERABLE = tuple(name for name in TECHNIQUES if name != "ulang")


def test_normalize_recovers_simple_sentences():
    rng = random.Random(42)
    for text in SENTENCES:
        for _ in range(5):
            variant = obfuscate(text, rng, p=1.0, techniques=RECOVERABLE)
            assert normalize(variant) == normalize(text), (text, variant)


@pytest.mark.xfail(strict=True, reason="temuan F2-L2: normalize memangkas huruf berulang ke 2, bukan 1")
def test_normalize_recovers_repeated_last_letter():
    assert normalize(obfuscate("slot gacor", random.Random(0), p=1.0, techniques=("ulang",))) == "slot gacor"
