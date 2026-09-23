"""Dataset loading and hourly preparation for turbine model training."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SOURCE_COLUMNS = {
    "ID": "id",
    "Статистическое время": "timestamp",
    "Средняя скорость ветра(m/s)": "wind_speed_ms",
    "Нормализованная активная мощность": "power_normalized",
    "Средняя температура окружающей среды(°C)": "temperature_c",
}


class DataError(ValueError):
    """The source data does not satisfy the training contract."""


@dataclass(frozen=True)
class DataSummary:
    source_rows: int
    hourly_rows: int
    dropped_incomplete_hours: int
    first_timestamp: str
    last_timestamp: str


def load_training_data(
    path: str | Path,
    *,
    turbine_id: str,
    samples_per_hour: int = 6,
) -> tuple[pd.DataFrame, DataSummary]:
    """Load one CSV, remove ID, and aggregate only complete hours."""

    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)

    frame = pd.read_csv(source_path, encoding="utf-8-sig")
    missing = sorted(set(SOURCE_COLUMNS) - set(frame.columns))
    if missing:
        raise DataError(f"missing columns in {source_path}: {missing}")

    frame = frame.loc[:, list(SOURCE_COLUMNS)].rename(columns=SOURCE_COLUMNS)
    try:
        frame["timestamp"] = pd.to_datetime(
            frame["timestamp"],
            format="%Y-%m-%d %H:%M:%S",
            errors="raise",
        )
        for column in ("wind_speed_ms", "power_normalized", "temperature_c"):
            frame[column] = pd.to_numeric(frame[column], errors="raise")
    except (TypeError, ValueError) as exc:
        raise DataError(f"invalid value in {source_path}: {exc}") from exc

    if frame.empty:
        raise DataError(f"empty dataset: {source_path}")
    if frame["timestamp"].duplicated().any():
        raise DataError(f"duplicate timestamps in {source_path}")

    frame = frame.sort_values("timestamp", kind="stable")
    frame = frame.drop(columns="id")
    frame["hour"] = frame["timestamp"].dt.floor("h")

    values = ("wind_speed_ms", "power_normalized", "temperature_c")
    grouped = frame.groupby("hour", sort=True)
    hourly = grouped[list(values)].mean()
    counts = grouped[list(values)].count()
    complete = counts.eq(samples_per_hour).all(axis=1)
    dropped = int((~complete).sum())
    hourly = hourly.loc[complete].reset_index().rename(columns={"hour": "timestamp"})
    hourly.insert(1, "turbine_id", turbine_id)

    if hourly.empty:
        raise DataError(f"no complete hours in {source_path}")

    summary = DataSummary(
        source_rows=len(frame),
        hourly_rows=len(hourly),
        dropped_incomplete_hours=dropped,
        first_timestamp=hourly["timestamp"].iloc[0].isoformat(),
        last_timestamp=hourly["timestamp"].iloc[-1].isoformat(),
    )
    return hourly, summary
