from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from ml.data import DataError, load_training_data


def _write_source(path: Path, timestamps: list[str]) -> None:
    frame = pd.DataFrame(
        {
            "ID": range(1, len(timestamps) + 1),
            "Статистическое время": timestamps,
            "Средняя скорость ветра(m/s)": [5.0] * len(timestamps),
            "Нормализованная активная мощность": [0.4] * len(timestamps),
            "Средняя температура окружающей среды(°C)": [12.0] * len(timestamps),
        }
    )
    frame.to_csv(path, index=False)


def test_loads_unpadded_hour_and_drops_id_and_incomplete_hour(tmp_path: Path) -> None:
    source = tmp_path / "turbine.csv"
    timestamps = [f"2025-01-01 0:{minute:02d}:00" for minute in range(0, 60, 10)]
    timestamps += [f"2025-01-01 1:{minute:02d}:00" for minute in range(0, 50, 10)]
    _write_source(source, timestamps)

    hourly, summary = load_training_data(source, turbine_id="turbine_1")

    assert len(hourly) == 1
    assert "id" not in hourly.columns
    assert hourly.loc[0, "timestamp"] == pd.Timestamp("2025-01-01 00:00:00")
    assert summary.dropped_incomplete_hours == 1


def test_rejects_duplicate_timestamps(tmp_path: Path) -> None:
    source = tmp_path / "duplicate.csv"
    _write_source(source, ["2025-01-01 0:00:00", "2025-01-01 0:00:00"])

    with pytest.raises(DataError, match="duplicate timestamps"):
        load_training_data(source, turbine_id="turbine_1")
