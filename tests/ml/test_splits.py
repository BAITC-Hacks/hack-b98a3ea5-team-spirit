from ml.splits import make_time_splits


def test_time_splits_are_expanding_and_never_use_future_rows() -> None:
    splits = make_time_splits(60, n_splits=5)

    assert len(splits) == 5
    previous_train_size = 0
    for train_indices, validation_indices in splits:
        assert len(train_indices) > previous_train_size
        assert train_indices.max() < validation_indices.min()
        previous_train_size = len(train_indices)
