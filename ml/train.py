"""Train L3 on grouped comments only; real web pages remain evaluation-only."""

import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer
from sklearn.svm import LinearSVC

from app.detect.l3_text import MODEL_PATH, normalize
from ml.data import load_training_frame
from ml.obfuscate import make_variants

SEED = 42
MAX_MODEL_BYTES = 50_000_000


def training_frame() -> pd.DataFrame:
    frame = load_training_frame()
    frame["normalized"] = normalize(frame["text"])
    # Remove ambiguous normalized texts, then dedup before any split.
    conflicts = frame.groupby("normalized")["label"].nunique().gt(1)
    frame = frame.loc[~frame["normalized"].map(conflicts) & frame["normalized"].ne("")]
    return frame.drop_duplicates("normalized").reset_index(drop=True)


def split_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=SEED)
    train_index, test_index = next(splitter.split(frame, frame["label"], frame["group"]))
    train, test = frame.iloc[train_index].copy(), frame.iloc[test_index].copy()
    assert set(train["group"]).isdisjoint(test["group"])
    assert set(train["normalized"]).isdisjoint(test["normalized"])
    if train["label"].nunique() != 2 or test["label"].nunique() != 2:
        raise ValueError("Split harus memiliki kedua kelas")
    return train, test


def augment_training(train: pd.DataFrame, excluded=()) -> pd.DataFrame:
    positives = train.loc[train["label"].eq(1), "text"].tolist()
    variants = make_variants(positives, n=round(0.3 * len(positives)), seed=SEED)
    extra = pd.DataFrame({"text": variants, "label": 1})
    extra["normalized"] = normalize(extra["text"])
    extra = extra.loc[~extra["normalized"].isin(excluded)]
    return pd.concat([train, extra], ignore_index=True)


def build_model() -> Pipeline:
    return Pipeline([
        ("normalize", FunctionTransformer(normalize)),
        ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)),
        ("classifier", CalibratedClassifierCV(LinearSVC(C=0.5, random_state=SEED), cv=3)),
    ])


def main() -> int:
    frame = training_frame()
    train, test = split_frame(frame)
    augmented = augment_training(train, excluded=test["normalized"])
    model = build_model().fit(augmented["text"], augmented["label"])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=MODEL_PATH.parent, suffix=".joblib", delete=False) as output:
            temporary = Path(output.name)
        joblib.dump(model, temporary, compress=3)
        size = temporary.stat().st_size
        if size >= MAX_MODEL_BYTES:
            raise ValueError("Model harus lebih kecil dari 50 MB; model lama tidak ditimpa")
        os.replace(temporary, MODEL_PATH)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print(f"Dedup: {len(frame)}; latih: {len(train)}; uji: {len(test)}; varian positif: {len(augmented) - len(train)}")
    print(f"Model: backend/app/detect/l3_model.joblib ({size / 1_000_000:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
