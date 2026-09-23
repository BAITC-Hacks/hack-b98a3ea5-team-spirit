"""Loading and inference for saved training artifacts."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from ml.features import build_features


def load_model(path: str | Path) -> Pipeline:
    model = joblib.load(Path(path))
    if not isinstance(model, Pipeline):
        raise TypeError("saved artifact is not a scikit-learn Pipeline")
    return model


def predict(model: Pipeline, frame: pd.DataFrame) -> np.ndarray:
    values = np.asarray(model.predict(build_features(frame)), dtype=float)
    if values.shape != (len(frame),) or not np.isfinite(values).all():
        raise ValueError("model returned invalid predictions")
    return values
