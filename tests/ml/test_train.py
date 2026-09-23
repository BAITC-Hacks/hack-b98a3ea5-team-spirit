from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ml.train import MODEL_NAMES, build_models, train_all


def _training_csv(path: Path, hours: int = 96) -> None:
    timestamps = pd.date_range("2025-12-29", periods=hours * 6, freq="10min")
    frame = pd.DataFrame(
        {
            "ID": range(1, len(timestamps) + 1),
            "Статистическое время": timestamps.strftime("%Y-%m-%d %-H:%M:%S"),
            "Средняя скорость ветра(m/s)": [
                3.0 + index % 30 / 10 for index in range(len(timestamps))
            ],
            "Нормализованная активная мощность": [
                0.1 + index % 30 / 40 for index in range(len(timestamps))
            ],
            "Средняя температура окружающей среды(°C)": [
                5.0 + index % 20 / 5 for index in range(len(timestamps))
            ],
        }
    )
    frame.to_csv(path, index=False)


def test_registry_contains_exactly_fifteen_models_and_decision_tree() -> None:
    models = build_models(random_state=42)

    assert tuple(models) == MODEL_NAMES
    assert len(models) == 15
    assert "decision_tree" in models


def test_production_config_has_coarse_and_fine_grids_for_all_models() -> None:
    project_root = Path(__file__).parents[2]
    config = json.loads(
        (project_root / "config" / "training.json").read_text(encoding="utf-8")
    )

    models = build_models(random_state=42)
    assert tuple(config["models"]) == MODEL_NAMES
    for name, settings in config["models"].items():
        assert settings["coarse_grid"]
        assert settings["fine_grid"]
        valid_parameters = set(models[name].get_params(deep=True))
        assert set(settings["coarse_grid"]) <= valid_parameters
        assert set(settings["fine_grid"]) <= valid_parameters


def test_smoke_training_creates_model_and_honest_manifest(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    data_dir.mkdir()
    config_dir.mkdir()
    source = data_dir / "turbine.csv"
    _training_csv(source)
    config = {
        "turbines": [{"id": "turbine_1", "path": "data/turbine.csv"}],
        "output_dir": "artifacts",
        "samples_per_hour": 6,
        "test_start": "2026-01-01 00:00:00",
        "cv_splits": 3,
        "shortlist_size": 1,
        "n_jobs": 1,
        "random_state": 42,
        "smoke_models": ["decision_tree", "ridge"],
        "smoke_max_rows": 1000,
        "models": {
            "decision_tree": {
                "coarse_grid": {"model__max_depth": [3]},
                "fine_grid": {"model__max_depth": [3, 5]},
            },
            "ridge": {
                "coarse_grid": {"model__alpha": [1.0]},
                "fine_grid": {"model__alpha": [0.1, 1.0]},
            },
        },
    }
    config_path = config_dir / "training.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = train_all(config_path, smoke=True, n_jobs_override=1)

    artifact_dir = tmp_path / "artifacts" / "smoke" / "turbine_1"
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert (artifact_dir / "model.joblib").is_file()
    assert result["results"][0]["selected_model"] in config["smoke_models"]
    assert manifest["test_period"]["role"].startswith("independent")
    assert "not a demonstrated 24/48-hour" in manifest["limitation"]
    assert len(manifest["coarse_results"]) == 2
    assert manifest["smoke"] is True
