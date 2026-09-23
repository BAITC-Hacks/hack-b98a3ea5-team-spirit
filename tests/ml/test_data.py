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


def test_rejects_missing_file_columns_invalid_empty_and_incomplete(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_training_data(tmp_path / "missing.csv", turbine_id="turbine_1")

    missing_column = tmp_path / "missing-column.csv"
    pd.DataFrame({"ID": [1]}).to_csv(missing_column, index=False)
    with pytest.raises(DataError, match="missing columns"):
        load_training_data(missing_column, turbine_id="turbine_1")

    invalid = tmp_path / "invalid.csv"
    _write_source(invalid, ["not-a-time"])
    with pytest.raises(DataError, match="invalid value"):
        load_training_data(invalid, turbine_id="turbine_1")

    empty = tmp_path / "empty.csv"
    _write_source(empty, [])
    with pytest.raises(DataError, match="empty dataset"):
        load_training_data(empty, turbine_id="turbine_1")

    incomplete = tmp_path / "incomplete.csv"
    _write_source(incomplete, ["2025-01-01 0:00:00"])
    with pytest.raises(DataError, match="no complete hours"):
        load_training_data(incomplete, turbine_id="turbine_1")
