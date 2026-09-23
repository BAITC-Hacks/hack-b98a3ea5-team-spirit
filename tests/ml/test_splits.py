import numpy as np
import pytest

import ml.splits
from ml.splits import make_time_splits


def test_time_splits_are_expanding_and_never_use_future_rows() -> None:
    splits = make_time_splits(60, n_splits=5)

    assert len(splits) == 5
    previous_train_size = 0
    for train_indices, validation_indices in splits:
        assert len(train_indices) > previous_train_size
        assert train_indices.max() < validation_indices.min()
        previous_train_size = len(train_indices)


def test_time_splits_reject_too_few_rows_and_detect_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValueError, match="not enough rows"):
        make_time_splits(5, n_splits=5)

    class LeakySplit:
        def __init__(self, n_splits: int) -> None:
            self.n_splits = n_splits

        def split(self, rows: np.ndarray):
            return [(np.array([0, 2]), np.array([1, 3]))]

    monkeypatch.setattr(ml.splits, "TimeSeriesSplit", LeakySplit)
    with pytest.raises(AssertionError, match="time leakage"):
        make_time_splits(4, n_splits=2)
