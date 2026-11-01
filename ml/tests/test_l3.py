"""Run with python ml/tests/test_l3.py; no local datasets needed."""

from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from bs4 import BeautifulSoup
import pandas as pd

from app.detect import l3_text
from ml.eval_v1 import hidden_anchors
from ml.train import augment_training, build_model, split_frame, training_frame


def test_dedup_and_group_split():
    frame = pd.DataFrame([
        {"text": f"{'slot gacor' if label else 'berita kampus'} {i}", "label": label,
         "source": "youtube", "group": f"yt:{i}"}
        for i in range(20) for label in (0, 1)
    ])
    duplicate = frame.iloc[[1]].copy()
    duplicate["text"] = "𝙎𝙇𝙊𝙏 𝙂𝘼𝘾𝙊𝙍 0"
    conflict = pd.DataFrame({"text": ["t.o.t.o", "toto"], "label": [0, 1],
                             "source": "youtube", "group": "yt:conflict"})
    with patch("ml.train.load_training_frame", return_value=pd.concat([frame, duplicate, conflict])):
        dedup = training_frame()
    assert len(dedup) == len(frame)
    assert not dedup["normalized"].duplicated().any()
    train, test = split_frame(dedup)
    assert set(train["group"]).isdisjoint(test["group"])
    assert set(train["normalized"]).isdisjoint(test["normalized"])
    first = augment_training(train, excluded=test["normalized"])
    second = augment_training(train, excluded=test["normalized"])
    assert first.equals(second)
    pd.testing.assert_frame_equal(first.iloc[:len(train)].reset_index(drop=True), train.reset_index(drop=True))
    assert first.iloc[len(train):]["label"].eq(1).all()
    assert set(first["normalized"]).isdisjoint(test["normalized"])


def test_hidden_selection_without_keyword_filter():
    soup = BeautifulSoup('''<body>
        <a href="/visible">slot gacor visible</a>
        <div style="display:none"><a href="/one">plain hidden</a></div>
        <div style="left:-9999px"><a href="/two">offscreen</a></div>
        <a style="font-size:1px;color:#ffffff" href="/three">tiny</a>
        <a hidden href="/four">hidden attribute</a>
        </body>''', "lxml")
    text, techniques, count = hidden_anchors(soup.body)
    assert text == "plain hidden offscreen tiny hidden attribute"
    assert techniques == {"css_hidden", "offscreen", "tiny_white"}
    assert count == 4
    assert hidden_anchors(BeautifulSoup('<body><a href="/">normal</a></body>', "lxml").body) == ("", set(), 0)


def test_pipeline_and_lazy_probability():
    model = build_model()
    assert model.named_steps["tfidf"].get_params()["ngram_range"] == (2, 5)
    assert model.named_steps["classifier"].cv == 3
    texts = [f"berita kampus akademik {i}" for i in range(6)] + [f"slot gacor jackpot {i}" for i in range(6)]
    model.fit(texts, [0] * 6 + [1] * 6)
    l3_text.load_model.cache_clear()
    with patch.object(l3_text.joblib, "load", return_value=model) as loader:
        positive = l3_text.score_text("𝙎𝙇𝙊𝙏 gacor jackpot")
        negative = l3_text.score_text("berita kampus akademik")
        assert 0 <= negative < positive <= 1
        assert loader.call_count == 1
    l3_text.load_model.cache_clear()


if __name__ == "__main__":
    test_dedup_and_group_split()
    test_hidden_selection_without_keyword_filter()
    test_pipeline_and_lazy_probability()
    print("L3 checks: passed")
