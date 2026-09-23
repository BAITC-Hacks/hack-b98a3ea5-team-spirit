from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.pipeline import Pipeline

from backend.app.schemas import ForecastRequest
from backend.app.service import ForecastService, ModelRepository
from backend.app.settings import Settings, Turbine
from backend.app.weather import WeatherPoint, WeatherResult


class FakeModels:
    def __init__(self) -> None:
        features = pd.DataFrame(
            {"wind_speed_ms": [1.0], "temperature_c": [2.0], "month": [1], "season": [1]}
        )
        self.model = Pipeline([("model", DummyRegressor(strategy="constant", constant=0.4))])
        self.model.fit(features, np.array([0.4]))

    def get(self, turbine_id: str) -> tuple[Pipeline, str]:
        return self.model, f"test-{turbine_id}"


class FakeWeather:
    cache_status = "network"

    def fetch(self, turbine: Turbine, issue_time: datetime, horizon: int) -> WeatherResult:
        offset = 0.1 if turbine.id == "turbine_2" else 0.0
        return WeatherResult(
            points=[
                WeatherPoint(issue_time + timedelta(hours=lead), 8.0 + offset, -2.0)
                for lead in range(1, horizon + 1)
            ],
            run_time=issue_time - timedelta(hours=6),
            available_at=issue_time,
            retrieved_at=issue_time + timedelta(days=1),
            cache_status=self.cache_status,
            response_sha256="abc",
        )


def test_both_turbines_returns_48_points_and_honest_farm_mean(tmp_path: Path) -> None:
    turbines = {
        "turbine_1": Turbine("turbine_1", "Turbine 1", 43.64515, 78.535604),
        "turbine_2": Turbine("turbine_2", "Turbine 2", 43.643198, 78.538828),
    }
    settings = Settings(tmp_path, tmp_path / "models", tmp_path / "dist", turbines)
    service = ForecastService(settings, weather=FakeWeather(), models=FakeModels())

    result = service.forecast(
        ForecastRequest(turbine_id="both", issue_time="2026-01-31T00:00:00Z", horizon_hours=48)
    )

    assert [len(item.hourly) for item in result.series] == [48, 48]
    assert len(result.farm_mean_normalized or []) == 48
    assert result.farm_mean_normalized is not None
    assert result.farm_mean_normalized[0].mean_power_normalized == 0.4
    assert any("not total MW" in warning for warning in result.warnings)


def test_single_turbine_propagates_fallback_warning(tmp_path: Path) -> None:
    turbine = Turbine("turbine_1", "Turbine 1", 43.64515, 78.535604)
    settings = Settings(tmp_path, tmp_path / "models", tmp_path / "dist", {turbine.id: turbine})
    weather = FakeWeather()
    weather.cache_status = "stale-cache-fallback"
    result = ForecastService(settings, weather=weather, models=FakeModels()).forecast(
        ForecastRequest(
            turbine_id="turbine_1",
            issue_time="2026-01-31T00:00:00Z",
            horizon_hours=24,
        )
    )

    assert result.farm_mean_normalized is None
    assert any("stale-cache-fallback" in warning for warning in result.warnings)


def test_model_repository_loads_once_and_reads_manifest(tmp_path: Path) -> None:
    directory = tmp_path / "turbine_1"
    directory.mkdir()
    model = FakeModels().model
    joblib.dump(model, directory / "model.joblib")
    (directory / "manifest.json").write_text(
        '{"selected_model":"dummy","trained_at_utc":"2026-01-01T00:00:00Z"}'
    )
    repository = ModelRepository(tmp_path)

    first, version = repository.get("turbine_1")
    second, _ = repository.get("turbine_1")

    assert first is second
    assert version == "dummy@2026-01-01T00:00:00Z"
