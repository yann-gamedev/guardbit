"""Offline L3 evaluation. Output only aggregate metrics and anonymized page IDs."""

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_fscore_support, recall_score

from app.detect.l3_lite import score_text as keyword_score
from app.detect.l3_text import load_model
from ml.train import augment_training, build_model, split_frame, training_frame

TEST_SETS = {"uji_nyata", "uji_negatif", "uji_negatif_sulit"}
THRESHOLD = 0.5


def hidden_anchors(soup: BeautifulSoup) -> tuple[str, set[str], int]:
    """Select by inline visibility only, never by label, keyword, href or brand."""
    texts, techniques = [], set()
    for anchor in soup.select("a[href]"):
        reasons = set()
        for element in (anchor, *anchor.parents):
            style = dict(re.findall(r"([\w-]+)\s*:\s*([^;]+)", element.get("style", "").lower()))
            style = {key: value.replace("!important", "").strip() for key, value in style.items()}
            if element.has_attr("hidden") or style.get("display") == "none" or style.get("visibility") == "hidden":
                reasons.add("css_hidden")
            for key in ("left", "top"):
                offset = re.fullmatch(r"(-?[\d.]+)px", style.get(key, ""))
                if offset and float(offset[1]) <= -1000:
                    reasons.add("offscreen")
            size = re.fullmatch(r"([\d.]+)px", style.get("font-size", ""))
            if size and float(size[1]) <= 1:
                reasons.add("tiny_white")
        text = anchor.get_text(" ", strip=True)
        if reasons and text:
            texts.append(text)
            techniques.update(reasons)
    return " ".join(texts), techniques, len(texts)


def web_frame() -> pd.DataFrame:
    labels = pd.read_csv(ROOT / "data/labels/labels.csv", keep_default_na=False)
    selected = labels.loc[labels["set"].isin(TEST_SETS)].copy()
    if selected["page_id"].duplicated().any() or not selected["label"].isin(["infected", "clean"]).all():
        raise ValueError("Label uji web tidak valid")
    counts = selected["label"].value_counts().to_dict()
    if counts != {"infected": 7, "clean": 7}:
        raise ValueError("Set web harus berisi 7 terinfeksi dan 7 bersih")
    blocks = pd.read_csv(ROOT / "data/labels/spam_blocks.csv", keep_default_na=False)
    cache_path = ROOT / "data/snapshots/_pages_text.csv"
    cached = pd.read_csv(cache_path, keep_default_na=False).set_index("page_id") if cache_path.exists() else None
    if cached is not None and not cached.index.is_unique:
        raise ValueError("page_id cache duplikat")
    rows = []
    snapshot_dir = (ROOT / "data/snapshots").resolve()
    for row in selected.itertuples(index=False):
        for component in (row.alias, row.page_id):
            if not component or component in {".", ".."} or any(char in component for char in '/\\:'):
                raise ValueError("Komponen path snapshot tidak valid")
        path = (snapshot_dir / row.alias / row.page_id / "browser_1.html").resolve()
        if not path.is_relative_to(snapshot_dir):
            raise ValueError("Path snapshot tidak valid")
        soup = BeautifulSoup(path.read_bytes(), "lxml")
        for element in soup.find_all(["script", "style", "noscript"]):
            element.decompose()
        if soup.body is None:
            raise ValueError("Body snapshot tidak tersedia")
        hidden, found, count = hidden_anchors(soup.body)
        # Ground truth supplies technique/location coverage checks, not positive text selection.
        locations = blocks.loc[blocks["page_id"].eq(row.page_id)]
        if row.label == "infected" and (locations.empty or not set(locations["teknik"]).issubset(found)):
            raise ValueError("Lokasi spam berlabel belum tercakup ekstraksi inline")
        full = cached.loc[row.page_id, "text"] if cached is not None and row.page_id in cached.index else soup.body.get_text(" ", strip=True)
        if not isinstance(full, str) or not full.strip():
            raise ValueError("Teks halaman uji kosong")
        location_info = "; ".join(sorted(set(locations["posisi"] + ":" + locations["teknik"]))) or "tidak ada"
        rows.append({"page_id": row.page_id, "label": int(row.label == "infected"),
                     "text": hidden or full, "full_text": full, "hidden_count": count,
                     "locations": location_info})
    return pd.DataFrame(rows)


def probabilities(model, texts) -> np.ndarray:
    return model.predict_proba(texts)[:, list(model.classes_).index(1)]


def metrics_row(name: str, labels, scores) -> str:
    labels = np.asarray(labels)
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, np.asarray(scores) >= THRESHOLD, average="binary", zero_division=0
    )
    return f"| {name} | {sum(labels == 1)} | {sum(labels == 0)} | {precision:.4f} | {recall:.4f} | {f1:.4f} |"


def main() -> int:
    frame = training_frame()
    train, test = split_frame(frame)
    model = load_model()
    kaggle = test.loc[test["source"].eq("youtube")]
    rows = [metrics_row("Holdout Kaggle / model", kaggle["label"], probabilities(model, kaggle["text"])),
            metrics_row("Holdout Kaggle / kata kunci", kaggle["label"], kaggle["text"].map(keyword_score))]

    # Independent brand experiment: no normalized or raw alexis row may enter training.
    brand = frame["normalized"].str.contains("alexis", regex=False) | frame["text"].str.contains("alexis", case=False, regex=False)
    brand_test = frame.loc[brand]
    if brand_test["label"].eq(1).any():
        brand_train = augment_training(frame.loc[~brand], excluded=brand_test["normalized"])
        assert not brand_train["normalized"].str.contains("alexis", regex=False).any()
        assert not brand_train["text"].str.contains("alexis", case=False, regex=False).any()
        brand_model = build_model().fit(brand_train["text"], brand_train["label"])
        brand_recall = recall_score(brand_test["label"], probabilities(brand_model, brand_test["text"]) >= THRESHOLD, zero_division=0)
        lite_recall = recall_score(brand_test["label"], brand_test["text"].map(keyword_score) >= THRESHOLD, zero_division=0)
        n1, n0 = int(brand_test["label"].sum()), int(brand_test["label"].eq(0).sum())
        rows.extend([f"| Merek tersembunyi alexis / model | {n1} | {n0} | tidak diukur | {brand_recall:.4f} | tidak diukur |",
                     f"| Merek tersembunyi alexis / kata kunci | {n1} | {n0} | tidak diukur | {lite_recall:.4f} | tidak diukur |"])
    else:
        rows.append("| Merek tersembunyi alexis | 0 | 0 | tidak diukur | tidak diukur | tidak diukur |")

    pages = None
    try:
        pages = web_frame()
    except (OSError, ValueError, KeyError, pd.errors.ParserError):
        rows.append("| Web nyata (target 7 terinfeksi, 7 bersih) | — | — | tidak diukur | tidak diukur | tidak diukur |")
    if pages is not None:
        pages["model_hidden"] = probabilities(model, pages["text"])
        pages["model_full"] = probabilities(model, pages["full_text"])
        pages["lite_hidden"] = pages["text"].map(keyword_score)
        pages["lite_full"] = pages["full_text"].map(keyword_score)
        for name, column in (("Web / anchor tersembunyi atau teks penuh / model", "model_hidden"),
                             ("Web / seluruh teks / model", "model_full"),
                             ("Web / anchor tersembunyi atau teks penuh / kata kunci", "lite_hidden"),
                             ("Web / seluruh teks / kata kunci", "lite_full")):
            rows.append(metrics_row(name, pages["label"], pages[column]))

    print("# Evaluasi L3 v1\n")
    print("Ambang positif >= 0.5; precision/recall/F1 untuk kelas 1; zero_division=0.\n")
    print("| Set / metode | n terinfeksi (1) | n bersih (0) | Precision | Recall | F1 |")
    print("| --- | ---: | ---: | ---: | ---: | ---: |")
    print("\n".join(rows))
    print(f"\nDedup sebelum split: {len(frame)} baris. GroupShuffleSplit: test_size=0.2, seed=42; "
          f"latih {len(train)}, uji {len(test)}. Grup dan teks ternormalisasi terpisah. "
          "Holdout Kaggle hanya sumber YouTube pada bagian uji; sumber lain tidak dihitung sebagai Kaggle. "
          "Varian obfuskasi 30% positif hanya ditambahkan sesudah split ke latih; "
          "varian yang bertabrakan dengan teks uji dibuang. "
          "Uji alexis terpisah: latih ulang semua data komentar non-alexis, bukan model utama. "
          "Tidak ada halaman web dalam data latih.")
    if pages is not None:
        print("\n## Skor tingkat halaman (7 terinfeksi, 7 bersih)\n")
        print("| page_id | Kelas | Lokasi berlabel | n anchor tersembunyi | Model anchor/fallback | Model seluruh teks | Kata kunci anchor/fallback | Kata kunci seluruh teks |")
        print("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for row in pages.itertuples(index=False):
            label = "terinfeksi" if row.label else "bersih"
            print(f"| {row.page_id} | {label} | {row.locations} | {row.hidden_count} | {row.model_hidden:.4f} | {row.model_full:.4f} | {row.lite_hidden:.4f} | {row.lite_full:.4f} |")
        print("\nTeks anchor digabung per halaman, bukan dihitung sebagai sampel terpisah. "
              "Jika anchor tersembunyi kosong, gunakan seluruh teks pada kedua metode. "
              "Seleksi anchor sama untuk positif/negatif, tanpa filter kata kunci atau merek. "
              "spam_blocks.csv dipakai untuk memeriksa cakupan teknik/lokasi halaman terinfeksi; "
              "jumlah anchor bukan jumlah tautan spam ground truth. "
              "Ekstraksi lokal memakai style inline/induk (display:none, visibility:hidden, hidden, "
              "offscreen <= -1000px, font <= 1px), bukan computed style CSS eksternal. "
              "Tidak ada request jaringan. Sampel kecil dan empat halaman positif berasal dari situs sama; "
              "hasil bukan estimasi generalisasi semua situs.")
    print("\nSelisih F1 teks asli vs obfuskasi pada set uji: tidak diukur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
