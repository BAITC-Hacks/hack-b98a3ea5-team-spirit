from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from backend.app.settings import Settings, Turbine
from backend.app.weather import WeatherClient, WeatherError

ISSUE = datetime(2026, 1, 31, tzinfo=UTC)
TURBINE = Turbine("turbine_1", "Turbine 1", 43.5381, 79.4658)


def settings(tmp_path: Path) -> Settings:
    return Settings(
        storage_dir=tmp_path,
        model_dir=tmp_path / "models",
        frontend_dist=tmp_path / "dist",
        turbines={TURBINE.id: TURBINE},
    )


def payload(*, missing_hour: int | None = None, units: str = "m/s") -> dict[str, object]:
    run = datetime(2026, 1, 30, 18, tzinfo=UTC)
    times = [run + timedelta(hours=index) for index in range(55)]
    if missing_hour is not None:
        times.remove(ISSUE + timedelta(hours=missing_hour))
    return {
        "hourly_units": {"temperature_2m": "°C", "wind_speed_10m": units},
        "hourly": {
            "time": [value.strftime("%Y-%m-%dT%H:%M") for value in times],
            "temperature_2m": [-5.0 + index / 10 for index in range(len(times))],
            "wind_speed_10m": [7.0 + index / 100 for index in range(len(times))],
        },
    }


def test_weather_uses_fresh_cache_for_15_minutes(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.url.params["run"] == "2026-01-30T18:00"
        assert request.url.params["forecast_hours"] == "31"
        return httpx.Response(200, json=payload())

    now = datetime(2026, 2, 1, tzinfo=UTC)
    weather = WeatherClient(
        settings(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: now,
        sleep=lambda _: None,
    )
    first = weather.fetch(TURBINE, ISSUE, 24)
    second = weather.fetch(TURBINE, ISSUE, 24)

    assert calls == 1
    assert len(first.points) == 24
    assert first.points[0].valid_time == ISSUE + timedelta(hours=1)
    assert second.cache_status == "fresh-cache"
    assert second.retrieved_at == first.retrieved_at


def test_weather_uses_stale_cache_after_network_failure(tmp_path: Path) -> None:
    state = {"now": datetime(2026, 2, 1, tzinfo=UTC), "online": True}

    def handler(_: httpx.Request) -> httpx.Response:
        if not state["online"]:
            raise httpx.ConnectError("offline")
        return httpx.Response(200, json=payload())

    weather = WeatherClient(
        settings(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: state["now"],
        sleep=lambda _: None,
    )
    weather.fetch(TURBINE, ISSUE, 24)
    state["now"] += timedelta(minutes=16)
    state["online"] = False

    result = weather.fetch(TURBINE, ISSUE, 24)
    assert result.cache_status == "stale-cache-fallback"
    assert len(result.points) == 24


def test_weather_retries_rate_limit_and_then_succeeds(tmp_path: Path) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=payload())

    weather = WeatherClient(
        settings(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )

    assert weather.fetch(TURBINE, ISSUE, 24).cache_status == "network"
    assert calls == 2


def test_weather_falls_back_to_previous_run(tmp_path: Path) -> None:
    requested_runs: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        run = request.url.params["run"]
        requested_runs.append(run)
        if run == "2026-01-30T18:00":
            return httpx.Response(500)
        return httpx.Response(200, json=payload())

    weather = WeatherClient(
        settings(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )

    result = weather.fetch(TURBINE, ISSUE, 24)
    assert result.cache_status == "older-run-fallback"
    assert requested_runs[-1] == "2026-01-30T12:00"


@pytest.mark.parametrize(
    ("bad_payload", "message"),
    [(payload(missing_hour=4), "missing"), (payload(units="km/h"), "units")],
)
def test_weather_rejects_invalid_response(
    tmp_path: Path, bad_payload: dict[str, object], message: str
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=bad_payload)

    weather = WeatherClient(
        settings(tmp_path),
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _: None,
    )
    with pytest.raises(WeatherError, match=message):
        weather.fetch(TURBINE, ISSUE, 24)
