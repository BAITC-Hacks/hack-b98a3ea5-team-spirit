"""FastAPI entry point and production SPA hosting."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.schemas import (
    ForecastRequest,
    ForecastResponse,
    ReadinessResponse,
    TurbineResponse,
)
from backend.app.service import ForecastService
from backend.app.settings import Settings
from backend.app.weather import WeatherError


def create_app(settings: Settings | None = None, service: ForecastService | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    service = service or ForecastService(settings)
    app = FastAPI(title="Wind Farm Forecast", version="1.0.0")

    @app.get("/api/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/ready", response_model=ReadinessResponse, tags=["system"])
    def ready() -> ReadinessResponse | JSONResponse:
        checks = {
            "turbines": len(settings.turbines) == 2,
            "storage": settings.storage_dir.exists() and settings.storage_dir.is_dir(),
            "models": all(
                (settings.model_dir / turbine_id / "model.joblib").is_file()
                and (settings.model_dir / turbine_id / "manifest.json").is_file()
                for turbine_id in settings.turbines
            ),
        }
        response = ReadinessResponse(ready=all(checks.values()), checks=checks)
        if not response.ready:
            return JSONResponse(status_code=503, content=response.model_dump())
        return response

    @app.get("/api/turbines", response_model=list[TurbineResponse], tags=["forecast"])
    def turbines() -> list[TurbineResponse]:
        return [TurbineResponse(**vars(turbine)) for turbine in settings.turbines.values()]

    @app.post("/api/forecasts", response_model=ForecastResponse, tags=["forecast"])
    def create_forecast(request: ForecastRequest) -> ForecastResponse:
        try:
            return service.forecast(request)
        except WeatherError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except (FileNotFoundError, OSError, ValueError, TypeError) as exc:
            raise HTTPException(status_code=503, detail=f"Forecast is unavailable: {exc}") from exc

    dist = settings.frontend_dist
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False, response_model=None)
    def spa(path: str) -> FileResponse | JSONResponse:
        if path.startswith("api/") or path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Not found")
        index = dist / "index.html"
        if index.is_file():
            return FileResponse(index)
        return JSONResponse({"service": "Wind Farm Forecast API"})

    return app


app = create_app()
