"""Extract local snapshots without fetching links or printing raw text/URLs."""

import os
from pathlib import Path
import tempfile

from bs4 import BeautifulSoup
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LABELS_PATH = ROOT / "data/labels/labels.csv"
SNAPSHOT_DIR = ROOT / "data/snapshots"
SETS = {"uji_nyata", "latih_negatif", "uji_negatif", "uji_negatif_sulit"}
COLUMNS = ["page_id", "alias", "set", "label", "text"]


def extract_pages() -> pd.DataFrame:
    labels = pd.read_csv(LABELS_PATH, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    if not set(COLUMNS[:-1]).issubset(labels.columns):
        raise ValueError("Kolom label halaman tidak lengkap")
    selected = labels.loc[labels["set"].isin(SETS), COLUMNS[:-1]].copy()
    if selected["page_id"].duplicated().any():
        raise ValueError("page_id terpilih duplikat")
    if not selected["label"].isin(["infected", "clean"]).all():
        raise ValueError("Label halaman terpilih harus infected atau clean")
    texts = []
    for row in selected.itertuples(index=False):
        for component in (row.alias, row.page_id):
            if not component or component in {".", ".."} or any(char in component for char in '/\\:'):
                raise ValueError("Komponen path snapshot tidak valid")
        path = (SNAPSHOT_DIR / row.alias / row.page_id / "browser_1.html").resolve()
        if not path.is_relative_to(SNAPSHOT_DIR.resolve()):
            raise ValueError("Path snapshot di luar direktori yang diizinkan")
        soup = BeautifulSoup(path.read_bytes(), "lxml")
        for element in soup.find_all(["script", "style", "noscript"]):
            element.decompose()
        if soup.body is None:
            raise ValueError("Snapshot terpilih tidak memiliki body")
        text = soup.body.get_text(" ", strip=True)
        if not text:
            raise ValueError("Teks body snapshot terpilih kosong")
        texts.append(text)
    selected["text"] = texts
    return selected.reset_index(drop=True)


def main() -> int:
    temporary = None
    try:
        frame = extract_pages()
        # Replace only after every selected snapshot succeeds; preserve previous output on failure.
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", suffix=".csv", dir=SNAPSHOT_DIR, delete=False) as output:
            temporary = Path(output.name)
            frame.to_csv(output, index=False)
        os.replace(temporary, SNAPSHOT_DIR / "_pages_text.csv")
    except (OSError, ValueError, pd.errors.ParserError):
        print("GAGAL: periksa label dan snapshot lokal; keluaran lama tidak ditimpa jika ekstraksi gagal.")
        return 1
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print("Tersimpan: data/snapshots/_pages_text.csv (lokal, jangan commit)")
    print(frame.groupby(["set", "label"]).size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
