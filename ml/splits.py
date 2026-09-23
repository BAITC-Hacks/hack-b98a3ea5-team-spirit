"""Chronological cross-validation helpers."""

from __future__ import annotations

import numpy as np
from sklearn.model_selection import TimeSeriesSplit


def make_time_splits(
    row_count: int,
    *,
    n_splits: int,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Build expanding time splits and assert that future rows never train the model."""

    if row_count <= n_splits:
        raise ValueError("not enough rows for requested cross-validation splits")
    splits = list(TimeSeriesSplit(n_splits=n_splits).split(np.arange(row_count)))
    for train_indices, validation_indices in splits:
        if train_indices.max() >= validation_indices.min():
            raise AssertionError("time leakage detected in cross-validation")
    return splits
