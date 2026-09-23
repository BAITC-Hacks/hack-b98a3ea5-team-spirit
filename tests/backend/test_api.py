from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import create_app
from backend.app.schemas import (
    ForecastPoint,
    ForecastRequest,
    ForecastResponse,
    ForecastSeries,
    Provenance,
)
from backend.app.settings import Settings, Turbine
from backend.app.weather import WeatherError


def settings(tmp_path: Path, *, models: bool = True) -> Settings:
    model_dir = tmp_path / "models"
    turbines = {
        "turbine_1": Turbine("turbine_1", "Turbine 1", 43.64515, 78.535604),
        "turbine_2": Turbine("turbine_2", "Turbine 2", 43.643198, 78.538828),
    }
    if models:
        for turbine_id in turbines:
            directory = model_dir / turbine_id
            directory.mkdir(parents=True)
            (directory / "model.joblib").touch()
            (directory / "manifest.json").write_text("{}")
    return Settings(
        storage_dir=tmp_path,
        model_dir=model_dir,
        frontend_dist=tmp_path / "dist",
        turbines=turbines,
    )


class FakeService:
    def forecast(self, request: ForecastRequest) -> ForecastResponse:
        if request.turbine_id.value == "turbine_2":
            raise WeatherError("weather unavailable")
        timestamp = datetime(2026, 1, 31, 1, tzinfo=UTC)
        point = ForecastPoint(
            valid_time=timestamp,
            lead_hours=1,
            power_normalized=0.42,
            forecast_wind_speed_ms=7.2,
            forecast_temperature_c=-4.0,
        )
        return ForecastResponse(
            turbine_id=request.turbine_id,
            issue_time=request.issue_time,
            horizon_hours=request.horizon_hours,
            series=[
                ForecastSeries(
                    turbine_id="turbine_1",
                    turbine_name="Turbine 1",
                    model_version="test",
                    provenance=Provenance(
                        provider="Open-Meteo",
                        model="ECMWF IFS HRES",
                        run_time=datetime(2026, 1, 30, 18, tzinfo=UTC),
                        available_at=datetime(2026, 1, 31, tzinfo=UTC),
                        availability_basis="test",
                        retrieved_at=datetime(2026, 1, 31, tzinfo=UTC),
                        cache_status="network",
                        response_sha256="abc",
                    ),
                    hourly=[point],
                )
            ],
        )


def test_system_and_turbine_routes(tmp_path: Path) -> None:
    client = TestClient(create_app(settings(tmp_path), FakeService()))

    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/openapi.json").status_code == 200
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json()["ready"] is True
    turbines = client.get("/api/turbines")
    assert turbines.status_code == 200
    assert turbines.json() == [
        {"id": "turbine_1", "name": "Turbine 1", "latitude": 43.64515, "longitude": 78.535604},
        {"id": "turbine_2", "name": "Turbine 2", "latitude": 43.643198, "longitude": 78.538828},
    ]


def test_ready_returns_503_without_models(tmp_path: Path) -> None:
    response = TestClient(create_app(settings(tmp_path, models=False), FakeService())).get(
        "/api/ready"
    )
    assert response.status_code == 503
    assert response.json()["checks"]["models"] is False


def test_forecast_success_and_schema(tmp_path: Path) -> None:
    response = TestClient(create_app(settings(tmp_path), FakeService())).post(
        "/api/forecasts",
        json={
            "turbine_id": "turbine_1",
            "issue_time": "2026-01-31T00:00:00Z",
            "horizon_hours": 24,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["series"][0]["hourly"][0]["power_normalized"] == 0.42
    assert body["series"][0]["provenance"]["provider"] == "Open-Meteo"


def test_forecast_validates_input_and_maps_weather_failure(tmp_path: Path) -> None:
    client = TestClient(create_app(settings(tmp_path), FakeService()))
    invalid = client.post(
        "/api/forecasts",
        json={
            "turbine_id": "missing",
            "issue_time": "2026-01-31T00:30:00",
            "horizon_hours": 12,
        },
    )
    assert invalid.status_code == 422

    failed = client.post(
        "/api/forecasts",
        json={
            "turbine_id": "turbine_2",
            "issue_time": "2026-01-31T00:00:00Z",
            "horizon_hours": 48,
        },
    )
    assert failed.status_code == 503
    assert "weather unavailable" in failed.json()["detail"]


def test_unknown_api_route_is_not_spa(tmp_path: Path) -> None:
    response = TestClient(create_app(settings(tmp_path), FakeService())).get("/api/unknown")
    assert response.status_code == 404


def test_spa_fallback_and_missing_asset(tmp_path: Path) -> None:
    app_settings = settings(tmp_path)
    assets = app_settings.frontend_dist / "assets"
    assets.mkdir(parents=True)
    (app_settings.frontend_dist / "index.html").write_text("<h1>Wind UI</h1>")
    client = TestClient(create_app(app_settings, FakeService()))

    assert "Wind UI" in client.get("/forecast").text
    assert client.get("/assets/missing.js").status_code == 404


def test_root_explains_api_when_frontend_is_not_built(tmp_path: Path) -> None:
    response = TestClient(create_app(settings(tmp_path), FakeService())).get("/")
    assert response.json() == {"service": "Wind Farm Forecast API"}


def test_issue_time_validation_has_specific_errors() -> None:
    common = {"turbine_id": "turbine_1", "horizon_hours": 24}
    with pytest.raises(ValidationError, match="include a timezone"):
        ForecastRequest(issue_time="2026-01-31T00:00:00", **common)
    with pytest.raises(ValidationError, match="exact UTC hour"):
        ForecastRequest(issue_time="2026-01-31T00:30:00Z", **common)
    with pytest.raises(ValidationError, match="unavailable"):
        ForecastRequest(issue_time="2024-03-14T00:00:00Z", **common)
