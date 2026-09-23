from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml.features import build_features
from ml.predict import load_model, predict


def test_predictions_are_identical_after_save_and_load(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-01-01", periods=12, freq="h"),
            "wind_speed_ms": np.linspace(2.0, 10.0, 12),
            "temperature_c": np.linspace(-5.0, 15.0, 12),
        }
    )
    target = np.linspace(0.05, 0.9, 12)
    model = Pipeline([("scaler", StandardScaler()), ("model", Ridge(alpha=1.0))])
    model.fit(build_features(frame), target)
    before = predict(model, frame)
    path = tmp_path / "model.joblib"
    joblib.dump(model, path)

    after = predict(load_model(path), frame)

    np.testing.assert_allclose(before, after)
