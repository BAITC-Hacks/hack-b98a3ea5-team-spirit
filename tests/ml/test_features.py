import pandas as pd
import pytest

from ml.data import DataError
from ml.features import FEATURE_COLUMNS, build_features


def test_builds_month_and_meteorological_season_without_id_date_or_target() -> None:
    frame = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "timestamp": pd.to_datetime(["2025-01-15", "2025-04-15", "2025-07-15", "2025-10-15"]),
            "wind_speed_ms": [3.0, 4.0, 5.0, 6.0],
            "temperature_c": [0.0, 10.0, 20.0, 12.0],
            "power_normalized": [0.1, 0.2, 0.3, 0.4],
        }
    )

    features = build_features(frame)

    assert tuple(features.columns) == FEATURE_COLUMNS
    assert features["month"].tolist() == [1, 4, 7, 10]
    assert features["season"].tolist() == [1, 2, 3, 4]
    assert "timestamp" not in features
    assert "id" not in features
    assert "power_normalized" not in features


def test_features_reject_missing_columns_and_non_datetime_timestamp() -> None:
    with pytest.raises(DataError, match="missing columns"):
        build_features(pd.DataFrame({"timestamp": []}))
    with pytest.raises(DataError, match="must be datetime"):
        build_features(
            pd.DataFrame(
                {"timestamp": ["2026-01-01"], "wind_speed_ms": [5.0], "temperature_c": [1.0]}
            )
        )
