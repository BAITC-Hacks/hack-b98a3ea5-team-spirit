"""Forecast orchestration: weather -> ML features -> local predictions."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.pipeline import Pipeline

from backend.app.schemas import (
    FarmPoint,
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    ForecastSeries,
    Provenance,
)
from backend.app.settings import Settings
from backend.app.weather import WeatherClient
from ml.predict import load_model, predict


class ModelRepository:
    def __init__(self, model_dir: Path) -> None:
        self.model_dir = model_dir
        self._models: dict[str, Pipeline] = {}
        self._versions: dict[str, str] = {}

    def get(self, turbine_id: str) -> tuple[Pipeline, str]:
        if turbine_id not in self._models:
            directory = self.model_dir / turbine_id
            self._models[turbine_id] = load_model(directory / "model.joblib")
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            self._versions[turbine_id] = (
                f"{manifest['selected_model']}@{manifest['trained_at_utc']}"
            )
        return self._models[turbine_id], self._versions[turbine_id]


class ForecastService:
    def __init__(
        self,
        settings: Settings,
        *,
        weather: WeatherClient | None = None,
        models: ModelRepository | None = None,
    ) -> None:
        self.settings = settings
        self.weather = weather or WeatherClient(settings)
        self.models = models or ModelRepository(settings.model_dir)

    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        turbine_ids = (
            list(self.settings.turbines)
            if request.turbine_id.value == "both"
            else [request.turbine_id.value]
        )
        series: list[ForecastSeries] = []
        warnings = [
            "Weather run availability uses the documented conservative 6-hour delay assumption."
        ]
        for turbine_id in turbine_ids:
            turbine = self.settings.turbines[turbine_id]
            weather = self.weather.fetch(turbine, request.issue_time, request.horizon_hours)
            frame = pd.DataFrame(
                {
                    "timestamp": pd.to_datetime(
                        [point.valid_time for point in weather.points], utc=True
                    ),
                    "wind_speed_ms": [point.wind_speed_ms for point in weather.points],
                    "temperature_c": [point.temperature_c for point in weather.points],
                }
            )
            model, version = self.models.get(turbine_id)
            predictions = predict(model, frame)
            hourly = [
                ForecastPoint(
                    valid_time=point.valid_time,
                    lead_hours=lead,
                    power_normalized=float(power),
                    forecast_wind_speed_ms=point.wind_speed_ms,
                    forecast_temperature_c=point.temperature_c,
                )
                for lead, (point, power) in enumerate(
                    zip(weather.points, predictions, strict=True), start=1
                )
            ]
            series.append(
                ForecastSeries(
                    turbine_id=turbine.id,
                    turbine_name=turbine.name,
                    model_version=version,
                    provenance=Provenance(
                        provider="Open-Meteo",
                        model="ECMWF IFS HRES",
                        run_time=weather.run_time,
                        available_at=weather.available_at,
                        availability_basis="conservative 6-hour publication-delay assumption",
                        retrieved_at=weather.retrieved_at,
                        cache_status=weather.cache_status,
                        response_sha256=weather.response_sha256,
                    ),
                    hourly=hourly,
                )
            )
            if "fallback" in weather.cache_status:
                warnings.append(f"{turbine.name} used {weather.cache_status} weather data.")

        farm_mean = None
        if len(series) == 2:
            warnings.append(
                "Farm aggregate is the mean of normalized outputs, not total MW; "
                "nominal ratings are unknown."
            )
            farm_mean = [
                FarmPoint(
                    valid_time=left.valid_time,
                    lead_hours=left.lead_hours,
                    mean_power_normalized=(left.power_normalized + right.power_normalized) / 2,
                )
                for left, right in zip(series[0].hourly, series[1].hourly, strict=True)
            ]

        return ForecastResponse(
            turbine_id=request.turbine_id,
            issue_time=request.issue_time,
            horizon_hours=request.horizon_hours,
            series=series,
            farm_mean_normalized=farm_mean,
            warnings=warnings,
        )
