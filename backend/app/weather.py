"""Issue-time-safe Open-Meteo ECMWF retrieval with a 15-minute file cache."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from backend.app.settings import Settings, Turbine

SINGLE_RUNS_URL = "https://single-runs-api.open-meteo.com/v1/forecast"
AVAILABILITY_DELAY = timedelta(hours=6)


class WeatherError(RuntimeError):
    """Weather data cannot safely cover the requested forecast."""


@dataclass(frozen=True)
class WeatherPoint:
    valid_time: datetime
    wind_speed_ms: float
    temperature_c: float


@dataclass(frozen=True)
class WeatherResult:
    points: list[WeatherPoint]
    run_time: datetime
    available_at: datetime
    retrieved_at: datetime
    cache_status: str
    response_sha256: str


class WeatherClient:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        now: Callable[[], datetime] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.weather_timeout_seconds)
        self.now = now or (lambda: datetime.now(UTC))
        self.sleep = sleep
        self.cache_dir = settings.storage_dir / "weather"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, turbine: Turbine, issue_time: datetime, horizon: int) -> WeatherResult:
        preferred = self._available_run(issue_time)
        errors: list[str] = []
        for index, run_time in enumerate((preferred, preferred - timedelta(hours=6))):
            try:
                return self._fetch_run(turbine, issue_time, horizon, run_time, index > 0)
            except WeatherError as exc:
                errors.append(str(exc))
        raise WeatherError("Open-Meteo ECMWF and older-run fallback failed: " + "; ".join(errors))

    @staticmethod
    def _available_run(issue_time: datetime) -> datetime:
        cutoff = issue_time.astimezone(UTC) - AVAILABILITY_DELAY
        return cutoff.replace(hour=(cutoff.hour // 6) * 6, minute=0, second=0, microsecond=0)

    def _fetch_run(
        self,
        turbine: Turbine,
        issue_time: datetime,
        horizon: int,
        run_time: datetime,
        is_older_fallback: bool,
    ) -> WeatherResult:
        hours_from_run = int((issue_time - run_time).total_seconds() // 3600)
        params: dict[str, str | int | float] = {
            "latitude": turbine.latitude,
            "longitude": turbine.longitude,
            "hourly": "temperature_2m,wind_speed_10m",
            "models": "ecmwf_ifs",
            "run": run_time.strftime("%Y-%m-%dT%H:%M"),
            "forecast_hours": hours_from_run + horizon + 1,
            "temperature_unit": "celsius",
            "wind_speed_unit": "ms",
            "timezone": "GMT",
        }
        cache_key = hashlib.sha256(
            json.dumps([SINGLE_RUNS_URL, params], sort_keys=True).encode()
        ).hexdigest()
        cache_path = self.cache_dir / f"{cache_key}.json"
        cached = self._read_cache(cache_path)
        now = self.now().astimezone(UTC)
        if (
            cached
            and (now - cached["stored_at"]).total_seconds()
            < self.settings.weather_cache_ttl_seconds
        ):
            return self._parse(
                cached["payload"],
                issue_time,
                horizon,
                run_time,
                cached["stored_at"],
                "fresh-cache",
                cached["sha256"],
            )

        last_error = "request failed"
        for attempt in range(3):
            try:
                response = self.client.get(SINGLE_RUNS_URL, params=params)
                if response.status_code == 429 or response.status_code >= 500:
                    last_error = f"HTTP {response.status_code}"
                    if attempt < 2:
                        retry_after = float(response.headers.get("Retry-After", "1"))
                        self.sleep(min(retry_after, 2.0))
                        continue
                response.raise_for_status()
                payload = response.json()
                raw = response.content
                digest = hashlib.sha256(raw).hexdigest()
                retrieved_at = self.now().astimezone(UTC)
                parsed = self._parse(
                    payload,
                    issue_time,
                    horizon,
                    run_time,
                    retrieved_at,
                    "older-run-fallback" if is_older_fallback else "network",
                    digest,
                )
                self._write_cache(cache_path, payload, digest, retrieved_at)
                return parsed
            except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
                last_error = str(exc)
                if attempt < 2:
                    self.sleep(0.25 * (2**attempt))

        if cached:
            return self._parse(
                cached["payload"],
                issue_time,
                horizon,
                run_time,
                cached["stored_at"],
                "stale-cache-fallback",
                cached["sha256"],
            )
        raise WeatherError(f"run {run_time.isoformat()}: {last_error}")

    @staticmethod
    def _parse(
        payload: dict[str, Any],
        issue_time: datetime,
        horizon: int,
        run_time: datetime,
        retrieved_at: datetime,
        cache_status: str,
        digest: str,
    ) -> WeatherResult:
        units = payload.get("hourly_units", {})
        if units.get("temperature_2m") != "°C" or units.get("wind_speed_10m") != "m/s":
            raise WeatherError("Open-Meteo returned unexpected weather units")
        hourly = payload["hourly"]
        times = hourly["time"]
        winds = hourly["wind_speed_10m"]
        temperatures = hourly["temperature_2m"]
        if not (len(times) == len(winds) == len(temperatures)):
            raise WeatherError("Open-Meteo returned misaligned hourly arrays")

        by_time: dict[datetime, tuple[float, float]] = {}
        for raw_time, raw_wind, raw_temperature in zip(times, winds, temperatures, strict=True):
            timestamp = datetime.fromisoformat(raw_time).replace(tzinfo=UTC)
            wind = float(raw_wind)
            temperature = float(raw_temperature)
            if not math.isfinite(wind) or not math.isfinite(temperature):
                raise WeatherError("Open-Meteo returned a non-finite value")
            by_time[timestamp] = (wind, temperature)

        points: list[WeatherPoint] = []
        for lead in range(1, horizon + 1):
            valid_time = issue_time + timedelta(hours=lead)
            if valid_time not in by_time:
                raise WeatherError(f"Open-Meteo response is missing {valid_time.isoformat()}")
            wind, temperature = by_time[valid_time]
            points.append(WeatherPoint(valid_time, wind, temperature))
        return WeatherResult(
            points=points,
            run_time=run_time,
            available_at=run_time + AVAILABILITY_DELAY,
            retrieved_at=retrieved_at,
            cache_status=cache_status,
            response_sha256=digest,
        )

    @staticmethod
    def _read_cache(path: Path) -> dict[str, Any] | None:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            canonical = json.dumps(
                record["payload"], sort_keys=True, separators=(",", ":")
            ).encode()
            if hashlib.sha256(canonical).hexdigest() != record["payload_sha256"]:
                return None
            return {
                "payload": record["payload"],
                "sha256": record["response_sha256"],
                "stored_at": datetime.fromisoformat(record["stored_at"]),
            }
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @staticmethod
    def _write_cache(path: Path, payload: dict[str, Any], digest: str, stored_at: datetime) -> None:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        record = {
            "stored_at": stored_at.isoformat(),
            "response_sha256": digest,
            "payload_sha256": hashlib.sha256(canonical).hexdigest(),
            "payload": payload,
        }
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        temporary.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, path)
