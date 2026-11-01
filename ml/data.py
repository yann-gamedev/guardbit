"""Load raw comment datasets only; page evaluation sets never enter this loader."""

from collections import Counter
from pathlib import Path
import re

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data/raw"
COLUMNS = ["text", "label", "source", "group", "subset"]


def _read_csv(path: Path, columns: list[str], optional: bool = False) -> pd.DataFrame:
    if optional and not path.exists():
        return pd.DataFrame(columns=columns)
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        if optional:
            return pd.DataFrame(columns=columns)
        raise ValueError(f"{path.name}: CSV kosong") from None
    if optional and frame.empty:
        return pd.DataFrame(columns=columns)
    if not set(columns).issubset(frame.columns):
        raise ValueError(f"{path.name}: kolom wajib tidak lengkap")
    return frame.loc[:, columns].copy()


def load_training_frame() -> pd.DataFrame:
    youtube = _read_csv(RAW_DIR / "youtube_judol.csv", ["komentar", "label", "video_id"])
    youtube = youtube.rename(columns={"komentar": "text", "video_id": "group"})
    youtube["source"] = "youtube"
    youtube["subset"] = "komentar"

    indo = _read_csv(RAW_DIR / "indonlu_negatives.csv", ["text", "source", "subset"])
    indo["label"] = "0"
    indo["group"] = indo["subset"]

    tiktok = _read_csv(RAW_DIR / "tiktok_hardneg.csv", ["text", "subset", "group"])
    tiktok["label"] = "0"
    tiktok["source"] = "tiktok_lemah"

    openalex = _read_csv(RAW_DIR / "openalex_negatives.csv", ["text", "subset"], optional=True)
    openalex["label"] = "0"
    openalex["source"] = "openalex"
    openalex["group"] = openalex["subset"]

    frames = []
    empty_rows = 0
    for frame, prefix in ((youtube, "yt:"), (indo, "indo:"), (tiktok, "tt:"), (openalex, "oa:")):
        frame = frame.loc[:, COLUMNS].copy()
        for column in COLUMNS:
            frame[column] = frame[column].str.strip()
        empty_rows += int(frame["text"].eq("").sum())
        frame = frame.loc[frame["text"].ne("")].copy()
        if not frame["label"].isin(["0", "1"]).all():
            raise ValueError(f"Sumber {prefix}: label harus 0 atau 1")
        if frame[["source", "group", "subset"]].eq("").any().any():
            raise ValueError(f"Sumber {prefix}: metadata source/group/subset kosong")
        frame["label"] = frame["label"].astype(int)
        frame["group"] = prefix + frame["group"]
        frames.append(frame)

    combined = pd.concat(frames, ignore_index=True)
    before = combined.groupby(["source", "label"]).size()
    votes = combined.groupby("text")["label"].agg(["sum", "count", "nunique"])
    conflicts = int(votes["nunique"].gt(1).sum())
    tied = votes["sum"].mul(2).eq(votes["count"])
    majority = votes["sum"].mul(2).gt(votes["count"]).astype(int)
    # Keep metadata from the first row with the winning label; ties have no majority.
    keep = ~combined["text"].map(tied) & combined["label"].eq(combined["text"].map(majority))
    result = combined.loc[keep].drop_duplicates("text").reset_index(drop=True)
    result.attrs.update(
        before_dedup=before,
        empty_rows_removed=empty_rows,
        duplicates_removed=len(combined) - combined["text"].nunique(),
        conflicting_texts=conflicts,
        tied_texts_removed=int(tied.sum()),
        rows_removed_dedup=len(combined) - len(result),
    )
    return result


def main() -> int:
    try:
        frame = load_training_frame()
    except (OSError, ValueError, pd.errors.ParserError):
        print("GAGAL: periksa file CSV wajib, kolom, label, dan metadata di data/raw.")
        return 1
    print("Sebelum dedup (setelah teks kosong dibuang):")
    print(frame.attrs["before_dedup"].to_string())
    print("Sesudah dedup:")
    print(frame.groupby(["source", "label"]).size().to_string())
    print(f"Baris teks kosong dibuang: {frame.attrs['empty_rows_removed']}")
    print(f"Duplikat dibuang: {frame.attrs['duplicates_removed']}")
    print(f"Teks konflik label: {frame.attrs['conflicting_texts']}")
    print(f"Teks konflik seri dibuang: {frame.attrs['tied_texts_removed']}")
    print(f"Total baris dibuang pada dedup: {frame.attrs['rows_removed_dedup']}")
    tokens = Counter(
        token
        for text in frame.loc[frame["label"].eq(1), "text"]
        for token in re.findall(r"[a-z]+-?\d{2,3}", text.lower())
    )
    print("5 token merek+angka paling sering di positif (sesudah dedup):")
    for token, count in tokens.most_common(5):
        print(f"{token}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
