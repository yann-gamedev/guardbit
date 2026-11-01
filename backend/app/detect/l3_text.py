"""Calibrated L3 text probability; model loads only on first use."""

from functools import lru_cache
from pathlib import Path

import joblib

from app.detect.normalize import normalize as normalize_text

MODEL_PATH = Path(__file__).with_name("l3_model.joblib")


def normalize(texts) -> list[str]:
    """Batch adapter for FunctionTransformer, importable when unpickling in backend."""
    return [normalize_text(text) for text in texts]


@lru_cache(maxsize=1)
def load_model():
    return joblib.load(MODEL_PATH)


def score_text(text: str) -> float:
    model = load_model()
    positive = list(model.classes_).index(1)
    return float(model.predict_proba([text])[0, positive])
