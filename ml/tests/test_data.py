import importlib.util
from pathlib import Path

import pandas as pd
import pytest


def load_module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


data = load_module("data")
pages = load_module("pages_text")


@pytest.fixture
def raw(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "RAW_DIR", tmp_path)
    pd.DataFrame({
        "komentar": [" raw text ", "majority", "majority", "majority", "tie", "tie", "  "],
        "label": [1, 0, 1, 1, 0, 1, 1],
        "video_id": ["001", "002", "003", "004", "005", "006", "007"],
        "predicted_label": [0] * 7,
        "komentar_clean": ["WRONG"] * 7,
    }).to_csv(tmp_path / "youtube_judol.csv", index=False)
    pd.DataFrame({"text": ["formal text"], "subset": ["formal"], "source": ["indonlu_facqa"]}).to_csv(tmp_path / "indonlu_negatives.csv", index=False)
    pd.DataFrame({"text": ["discussion"], "subset": ["judi_obrolan"], "group": ["008"]}).to_csv(tmp_path / "tiktok_hardneg.csv", index=False)
    return tmp_path


def test_output_columns_and_raw_manual_labels(raw):
    frame = data.load_training_frame()
    assert list(frame.columns) == ["text", "label", "source", "group", "subset"]
    assert not {"predicted_label", "komentar_clean"} & set(frame.columns)
    row = frame.set_index("text").loc["raw text"]
    assert row["label"] == 1
    assert row["group"] == "yt:001"
    assert "WRONG" not in set(frame["text"])


def test_dedup_majority_conflicts_and_groups(raw):
    frame = data.load_training_frame()
    assert not frame["text"].duplicated().any()
    assert frame["group"].str.strip().ne("").all()
    assert frame.set_index("text").loc["majority", "label"] == 1
    assert frame.set_index("text").loc["majority", "group"] == "yt:003"
    assert "tie" not in set(frame["text"])
    assert set(frame["group"]) == {"yt:001", "yt:003", "indo:formal", "tt:008"}
    assert frame.attrs["conflicting_texts"] == 2
    assert frame.attrs["duplicates_removed"] == 3
    assert frame.attrs["tied_texts_removed"] == 1
    assert frame.attrs["empty_rows_removed"] == 1
    assert frame.attrs["rows_removed_dedup"] == 4


@pytest.mark.parametrize("content", [None, "", "   \n", "text,subset,source_id\n", "text,subset,source_id\nabstract,general,ignored\n"])
def test_optional_openalex(raw, content):
    if content is not None:
        (raw / "openalex_negatives.csv").write_text(content, encoding="utf-8")
    frame = data.load_training_frame()
    expected = 1 if content and "abstract" in content else 0
    assert int(frame["source"].eq("openalex").sum()) == expected
    if expected:
        row = frame.loc[frame["source"].eq("openalex")].iloc[0]
        assert row["label"] == 0
        assert row["group"] == "oa:general"


@pytest.mark.parametrize("column,value", [("label", "bad"), ("video_id", " ")])
def test_bad_required_values_fail(raw, column, value):
    path = raw / "youtube_judol.csv"
    frame = pd.read_csv(path, dtype=str)
    frame.loc[0, column] = value
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError):
        data.load_training_frame()


def test_actual_training_frame_if_available():
    if not all((data.RAW_DIR / name).exists() for name in ("youtube_judol.csv", "indonlu_negatives.csv", "tiktok_hardneg.csv")):
        pytest.skip("Raw datasets are local-only")
    frame = data.load_training_frame()
    assert list(frame.columns) == data.COLUMNS
    assert not frame["text"].duplicated().any()
    assert frame["text"].str.strip().ne("").all()
    assert frame["group"].str.strip().ne("").all()
    assert frame["label"].isin([0, 1]).all()


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    labels = tmp_path / "labels.csv"
    directory = tmp_path / "snapshots"
    directory.mkdir()
    monkeypatch.setattr(pages, "LABELS_PATH", labels)
    monkeypatch.setattr(pages, "SNAPSHOT_DIR", directory)
    pd.DataFrame([
        {"page_id": "pg_001", "alias": "kampus-a", "set": "uji_nyata", "label": "infected"},
        {"page_id": "pg_002", "alias": "kampus-a", "set": "latih_negatif", "label": "clean"},
        {"page_id": "pg_003", "alias": "kampus-a", "set": "keluar", "label": "unknown"},
    ]).to_csv(labels, index=False)
    for page_id in ("pg_001", "pg_002"):
        path = directory / "kampus-a" / page_id / "browser_1.html"
        path.parent.mkdir(parents=True)
        path.write_text('<html><head><title>OMIT</title></head><body>Visible<script>OMIT</script><style>OMIT</style><noscript>OMIT</noscript><div style="display:none">Hidden</div><a href="https://example.invalid/">Link</a></body></html>', encoding="utf-8")
    return directory


def test_pages_body_only_and_set_preserved(snapshots, capsys):
    frame = pages.extract_pages()
    assert list(frame.columns) == pages.COLUMNS
    assert list(frame["set"]) == ["uji_nyata", "latih_negatif"]
    assert set(frame["label"]) == {"infected", "clean"}
    assert frame["text"].eq("Visible Hidden Link").all()
    assert pages.main() == 0
    result = pd.read_csv(snapshots / "_pages_text.csv")
    assert len(result) == 2
    assert "https://" not in capsys.readouterr().out


def test_missing_snapshot_preserves_previous_output(snapshots, capsys):
    output = snapshots / "_pages_text.csv"
    output.write_text("previous", encoding="utf-8")
    (snapshots / "kampus-a/pg_002/browser_1.html").unlink()
    assert pages.main() == 1
    assert output.read_text() == "previous"
    assert "https://" not in capsys.readouterr().out


def test_snapshot_path_traversal_rejected(snapshots):
    labels = pd.read_csv(pages.LABELS_PATH)
    labels.loc[0, "alias"] = "../outside"
    labels.to_csv(pages.LABELS_PATH, index=False)
    with pytest.raises(ValueError):
        pages.extract_pages()
