"""Public API contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TurbineSelection(StrEnum):
    turbine_1 = "turbine_1"
    turbine_2 = "turbine_2"
    both = "both"


class ForecastRequest(BaseModel):
    turbine_id: TurbineSelection
    issue_time: datetime
    horizon_hours: Literal[24, 48]

    @field_validator("issue_time")
    @classmethod
    def validate_issue_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("issue_time must include a timezone")
        value = value.astimezone(UTC)
        if value.minute or value.second or value.microsecond:
            raise ValueError("issue_time must be on an exact UTC hour")
        if value < datetime(2024, 3, 15, tzinfo=UTC):
            raise ValueError("ECMWF single-run archive is unavailable before 2024-03-15")
        return value


class TurbineResponse(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float


class ForecastPoint(BaseModel):
    valid_time: datetime
    lead_hours: int = Field(ge=1, le=48)
    power_normalized: float
    forecast_wind_speed_ms: float
    forecast_temperature_c: float


class Provenance(BaseModel):
    provider: str
    model: str
    run_time: datetime
    available_at: datetime
    availability_basis: str
    retrieved_at: datetime
    cache_status: str
    response_sha256: str


class ForecastSeries(BaseModel):
    turbine_id: str
    turbine_name: str
    model_version: str
    provenance: Provenance
    hourly: list[ForecastPoint]


class FarmPoint(BaseModel):
    valid_time: datetime
    lead_hours: int
    mean_power_normalized: float


class ForecastResponse(BaseModel):
    turbine_id: TurbineSelection
    issue_time: datetime
    horizon_hours: Literal[24, 48]
    series: list[ForecastSeries]
    farm_mean_normalized: list[FarmPoint] | None = None
    warnings: list[str] = Field(default_factory=list)


class ReadinessResponse(BaseModel):
    ready: bool
    checks: dict[str, bool]
