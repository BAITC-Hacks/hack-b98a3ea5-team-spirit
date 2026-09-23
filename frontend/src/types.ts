export type TurbineSelection = "turbine_1" | "turbine_2" | "both";

export interface ForecastPoint {
  valid_time: string;
  lead_hours: number;
  power_normalized: number;
  forecast_wind_speed_ms: number;
  forecast_temperature_c: number;
}

export interface ForecastSeries {
  turbine_id: string;
  turbine_name: string;
  model_version: string;
  provenance: {
    provider: string;
    model: string;
    run_time: string;
    cache_status: string;
  };
  hourly: ForecastPoint[];
}

export interface ForecastResponse {
  turbine_id: TurbineSelection;
  issue_time: string;
  horizon_hours: 24 | 48;
  series: ForecastSeries[];
  farm_mean_normalized: Array<{
    valid_time: string;
    lead_hours: number;
    mean_power_normalized: number;
  }> | null;
  warnings: string[];
}
