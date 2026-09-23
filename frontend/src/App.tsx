import { FormEvent, useState } from "react";

import { requestForecast } from "./api";
import type { ForecastResponse, TurbineSelection } from "./types";

function formatUtc(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(new Date(value));
}

export default function App() {
  const [turbine, setTurbine] = useState<TurbineSelection>("turbine_1");
  const [issueTime, setIssueTime] = useState("2026-01-31T00:00");
  const [horizon, setHorizon] = useState<24 | 48>(24);
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const forecast = await requestForecast({
        turbine_id: turbine,
        issue_time: new Date(`${issueTime}:00Z`).toISOString(),
        horizon_hours: horizon,
      });
      setResult(forecast);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Forecast failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">ECMWF · LOCAL ML</p>
        <h1>Wind farm forecast</h1>
        <p className="intro">Hourly normalized power from issue-time-safe weather runs.</p>
      </header>

      <form onSubmit={submit} aria-label="Forecast controls">
        <label>
          <span>Turbine</span>
          <select value={turbine} onChange={(event) => setTurbine(event.target.value as TurbineSelection)}>
            <option value="turbine_1">Turbine 1</option>
            <option value="turbine_2">Turbine 2</option>
            <option value="both">Both / Farm mean</option>
          </select>
        </label>

        <label>
          <span>Forecast issue time <small>UTC</small></span>
          <input
            type="datetime-local"
            step="3600"
            required
            value={issueTime}
            onChange={(event) => setIssueTime(event.target.value)}
          />
        </label>

        <label>
          <span>Horizon</span>
          <select value={horizon} onChange={(event) => setHorizon(Number(event.target.value) as 24 | 48)}>
            <option value={24}>24 hours</option>
            <option value={48}>48 hours</option>
          </select>
        </label>

        <button type="submit" disabled={loading}>
          {loading ? "Forecasting…" : "Run forecast"}
        </button>
      </form>

      {loading && (
        <div className="status" role="status">
          <span className="spinner" aria-hidden="true" />
          Fetching ECMWF weather and running local models…
        </div>
      )}
      {error && <div className="error" role="alert">{error}</div>}

      {result && (
        <section className="results" aria-live="polite">
          <div className="result-heading">
            <div>
              <p className="eyebrow">ISSUED {formatUtc(result.issue_time)} UTC</p>
              <h2>{result.horizon_hours}-hour forecast</h2>
            </div>
            <span className="pill">{result.series[0].provenance.model}</span>
          </div>

          {result.warnings.map((warning) => (
            <p className="warning" key={warning}>{warning}</p>
          ))}

          {result.series.map((series) => (
            <article key={series.turbine_id}>
              <div className="series-title">
                <h3>{series.turbine_name}</h3>
                <span>run {formatUtc(series.provenance.run_time)} UTC · {series.provenance.cache_status}</span>
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Valid time (UTC)</th><th>Lead</th><th>Power (norm.)</th><th>Wind m/s</th><th>Temp °C</th></tr>
                  </thead>
                  <tbody>
                    {series.hourly.map((point) => (
                      <tr key={point.valid_time}>
                        <td>{formatUtc(point.valid_time)}</td>
                        <td>+{point.lead_hours}h</td>
                        <td>{point.power_normalized.toFixed(3)}</td>
                        <td>{point.forecast_wind_speed_ms.toFixed(1)}</td>
                        <td>{point.forecast_temperature_c.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          ))}

          {result.farm_mean_normalized && (
            <article>
              <div className="series-title"><h3>Farm mean</h3><span>normalized, not MW</span></div>
              <div className="table-wrap compact">
                <table>
                  <thead><tr><th>Valid time (UTC)</th><th>Lead</th><th>Mean power (norm.)</th></tr></thead>
                  <tbody>
                    {result.farm_mean_normalized.map((point) => (
                      <tr key={point.valid_time}>
                        <td>{formatUtc(point.valid_time)}</td><td>+{point.lead_hours}h</td><td>{point.mean_power_normalized.toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </article>
          )}
        </section>
      )}
    </main>
  );
}
