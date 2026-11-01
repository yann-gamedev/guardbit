import importlib.util
import string
from pathlib import Path
from timeit import repeat

import pytest


ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ("𝙎𝙇𝙊𝙏 𝙂𝘼𝘾𝙊𝙍", "slot gacor"),
    ("s.l.o.t g-a-c-o-r", "slot gacor"),
    ("g4c0r", "gacor"),
    ("sl\u200bot", "slot"),
    ("ѕlot", "slot"),
    ("SLOT88", "slot88"),
    ("m4xw1n", "maxwin"),
    ("gacorrrr", "gacorr"),
    ("s l o t   g a c o r", "slot gacor"),
    ("ｓｌｏｔ", "slot"),
    ("𝐒𝐆𝐈𝟖𝟖", "sgi88"),
    ("Rp100 tahun 2024", "rp100 tahun 2024"),
    ("beta between", "beta between"),
    ("COVID-19", "covid-19"),
    ("e-ISSN 2581-2505", "e-issn 2581-2505"),
    ("https://kampus-a.example/a.b", "https://kampus-a.example/a.b"),
    ("S.Pd., M.Pd.", "s.pd., m.pd."),
    ("Ini bab 4 dan 5", "ini bab 4 dan 5"),
    ("s_l_o_t s*l*o*t s·l·o·t", "slot slot slot"),
    ("s.l-o.t", "s.l-o.t"),
    ("s l o", "slo"),
    ("a b", "a b"),
    ("s\tl\to\tt", "s l o t"),
    ("sl\u200cot sl\u200dot sl\u2060ot sl\ufeffot sl\u00adot", "slot slot slot slot slot"),
    ("4d slot88 rp100 2024 1234567890", "4d slot88 rp100 2024 1234567890"),
    ("g@cor ca$ino t3st a7a a8a a5a", "gacor casino test ata aba asa"),
    ("g40r", "g40r"),
    ("https://kampus-a.example/s.l.o.t/g4c0r", "https://kampus-a.example/s.l.o.t/g4c0r"),
    ("s.l.o.t+g4c0r@kampus-a.example", "s.l.o.t+g4c0r@kampus-a.example"),
    ("kampus-a.example/s.l.o.t/g4c0r", "kampus-a.example/s.l.o.t/g4c0r"),
    ("s.l.o.t https://kampus-a.example/g4c0r g-a-c-o-r", "slot https://kampus-a.example/g4c0r gacor"),
    ("aa aaa aaaa 8888 !!!", "aa aa aa 8888 !!!"),
    ("  SLOT\n\tGACOR  ", "slot gacor"),
    ("", ""),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_normalize(text, expected):
    from app.detect.normalize import normalize

    assert normalize(text) == expected


def load_generator():
    spec = importlib.util.spec_from_file_location("gen_confusables", ROOT / "scripts/gen_confusables.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generator_filters_and_preserves_case(tmp_path):
    generator = load_generator()
    source = tmp_path / "confusables.txt"
    output = tmp_path / "confusables_map.py"
    source.write_text(
        "# Version: 18.0.0\n"
        "0031 ; 006C ; MA # ASCII digit must stay\n"
        "0049 ; 006C ; MA # ASCII letter must stay\n"
        "0455 ; 0073 ; MA # Cyrillic small dze\n"
        "0391 ; 0041 ; MA # Greek capital alpha\n"
        "0440 ; 0072 006E ; MA # multiple target letters\n"
        "0455 0440 ; 0073 ; MA # multiple source characters\n"
        "0661 ; 0031 ; MA # target digit\n"
        "2010 ; 002D ; MA # punctuation\n",
        encoding="utf-8",
    )
    assert generator.generate(source, output) == 2
    text = output.read_text(encoding="utf-8")
    namespace = {}
    exec(compile(text, str(output), "exec"), namespace)
    assert namespace["CONFUSABLES"] == {"Α": "A", "ѕ": "s"}
    assert all(marker in text for marker in ("18.0.0", "UTS #39", "Unicode", "license", "scripts/gen_confusables.py"))
    generator.generate(source, output)
    assert output.read_text(encoding="utf-8") == text


def test_generated_map_only_non_ascii_to_ascii_letters():
    from app.detect.confusables_map import CONFUSABLES

    assert CONFUSABLES["ѕ"] == "s"
    assert CONFUSABLES
    assert all(len(key) == 1 and ord(key) > 127 for key in CONFUSABLES)
    assert all(len(value) == 1 and value in string.ascii_letters for value in CONFUSABLES.values())
    assert not set(string.printable) & CONFUSABLES.keys()


def test_normalize_thousand_characters_under_one_ms():
    from app.detect.normalize import normalize

    text = ("𝙎𝙇𝙊𝙏 s.l.o.t g4c0r Rp100 tahun 2024 https://kampus-a.example/a.b " * 25)[:1000]
    assert len(text) == 1000
    elapsed = min(repeat(lambda: normalize(text), number=1000, repeat=3)) / 1000
    assert elapsed < 0.001, f"{elapsed * 1000:.3f} ms per 1000 characters"
