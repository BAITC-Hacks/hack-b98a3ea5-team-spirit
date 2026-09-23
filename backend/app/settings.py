"""Small, environment-driven application configuration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Turbine:
    id: str
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    model_dir: Path
    frontend_dist: Path
    turbines: dict[str, Turbine]
    weather_cache_ttl_seconds: int = 900
    weather_timeout_seconds: float = 20.0

    @classmethod
    def from_env(cls) -> Settings:
        storage = Path(os.getenv("STORAGE_DIR", ROOT / "storage")).resolve()
        config_path = Path(os.getenv("TURBINES_CONFIG", ROOT / "config/turbines.json"))
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        turbines = {item["id"]: Turbine(**item) for item in raw["turbines"]}
        return cls(
            storage_dir=storage,
            model_dir=storage / "models" / "production",
            frontend_dist=Path(os.getenv("FRONTEND_DIST", ROOT / "frontend/dist")).resolve(),
            turbines=turbines,
            weather_cache_ttl_seconds=int(os.getenv("WEATHER_CACHE_TTL_SECONDS", "900")),
            weather_timeout_seconds=float(os.getenv("WEATHER_TIMEOUT_SECONDS", "20")),
        )
