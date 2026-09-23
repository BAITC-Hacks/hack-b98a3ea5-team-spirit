import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const response = {
  turbine_id: "turbine_1",
  issue_time: "2026-01-31T00:00:00Z",
  horizon_hours: 24,
  series: [{
    turbine_id: "turbine_1",
    turbine_name: "Turbine 1",
    model_version: "test",
    provenance: { provider: "Open-Meteo", model: "ECMWF IFS HRES", run_time: "2026-01-30T18:00:00Z", cache_status: "network" },
    hourly: [{ valid_time: "2026-01-31T01:00:00Z", lead_hours: 1, power_normalized: 0.42, forecast_wind_speed_ms: 7.2, forecast_temperature_c: -4 }],
  }],
  farm_mean_normalized: null,
  warnings: [],
};

afterEach(() => vi.restoreAllMocks());

describe("forecast UI", () => {
  it("shows loading and the returned prediction", async () => {
    let resolveFetch!: (value: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => { resolveFetch = resolve; })));
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Run forecast" }));
    expect(screen.getByRole("status")).toHaveTextContent("running local models");
    resolveFetch(new Response(JSON.stringify(response), { status: 200, headers: { "Content-Type": "application/json" } }));

    expect(await screen.findByRole("heading", { name: "24-hour forecast" })).toBeInTheDocument();
    expect(screen.getByText("0.420")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows a useful API error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "Weather unavailable" }), { status: 503 })));
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Run forecast" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Weather unavailable"));
  });
});
