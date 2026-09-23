"""Feature engineering required by ML.md."""

from __future__ import annotations

import pandas as pd

from ml.data import DataError

FEATURE_COLUMNS = ("wind_speed_ms", "temperature_c", "month", "season")


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace the date with month and meteorological season features."""

    required = {"timestamp", "wind_speed_ms", "temperature_c"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataError(f"cannot build features; missing columns: {missing}")
    if not pd.api.types.is_datetime64_any_dtype(frame["timestamp"]):
        raise DataError("timestamp must be datetime")

    features = frame.loc[:, ["wind_speed_ms", "temperature_c"]].copy()
    features["month"] = frame["timestamp"].dt.month.astype("int8")
    # DJF=1, MAM=2, JJA=3, SON=4.
    features["season"] = ((features["month"] % 12) // 3 + 1).astype("int8")
    return features.loc[:, list(FEATURE_COLUMNS)]
