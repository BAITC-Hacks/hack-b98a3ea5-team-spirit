import type { ForecastResponse, TurbineSelection } from "./types";

export async function requestForecast(input: {
  turbine_id: TurbineSelection;
  issue_time: string;
  horizon_hours: 24 | 48;
}): Promise<ForecastResponse> {
  const response = await fetch("/api/forecasts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? `Forecast failed (${response.status})`);
  }
  return (await response.json()) as ForecastResponse;
}
