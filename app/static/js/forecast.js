const ForecastUI = (() => {
  const panelId = "forecast-panel";

  async function loadForecast(spotId) {
    const panel = document.getElementById(panelId);
    panel.innerHTML = `<div class="forecast-empty"><h2>Pronóstico</h2><p>Cargando previsión...</p></div>`;
    try {
      const response = await fetch(`/api/spots/${spotId}/forecast`);
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "No se pudo obtener el pronóstico." }));
        throw new Error(error.detail || "No se pudo obtener el pronóstico.");
      }
      const forecast = await response.json();
      renderForecast(forecast);
      return forecast;
    } catch (error) {
      panel.innerHTML = `<div class="forecast-error">${escapeHtml(error.message)}</div>`;
      return null;
    }
  }

  function clear() {
    const panel = document.getElementById(panelId);
    panel.innerHTML = `
      <div class="forecast-empty">
        <h2>Pronóstico</h2>
        <p>Selecciona un punto para ver la previsión horaria.</p>
      </div>
    `;
  }

  function renderForecast(forecast) {
    const panel = document.getElementById(panelId);
    const summary = forecast.summary;
    const quality = qualityClass(summary.category);
    const alerts = summary.safety_alerts?.length
      ? summary.safety_alerts.map((alert) => `<span class="alert-pill">${escapeHtml(alert)}</span>`).join("")
      : `<span class="meta-pill">Sin alertas principales</span>`;
    const cached = forecast.meta?.cached ? `<span class="meta-pill">Cache</span>` : "";

    panel.innerHTML = `
      <div class="forecast-title">
        <div>
          <h2>${escapeHtml(forecast.spot.name)}</h2>
          <div class="small-muted">${forecast.spot.latitude.toFixed(4)}, ${forecast.spot.longitude.toFixed(4)}</div>
        </div>
        <div>${cached}<span class="quality-badge ${quality}">${escapeHtml(summary.category)}</span></div>
      </div>
      <div class="summary-grid">
        <div class="score-tile ${quality}">
          <div class="score-value">${summary.score}</div>
          <div class="score-label">${escapeHtml(summary.category)}</div>
        </div>
        <div class="summary-copy">
          <p><strong>${escapeHtml(summary.recommendation)}</strong></p>
          <p>${escapeHtml(summary.best_explanation || "")}</p>
          <div class="alert-list">${alerts}</div>
        </div>
      </div>
      ${renderLimitations(forecast)}
      ${renderTable(forecast.hourly)}
    `;
  }

  function renderLimitations(forecast) {
    const limitations = forecast.meta?.limitations || [];
    if (!limitations.length) return "";
    return `
      <p class="small-muted">
        ${limitations.map(escapeHtml).join(" ")}
      </p>
    `;
  }

  function renderTable(rows) {
    if (!rows.length) {
      return `<div class="forecast-error">No hay datos horarios suficientes.</div>`;
    }
    return `
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hora</th>
              <th>Cielo</th>
              <th>Score</th>
              <th>Viento</th>
              <th>Lluvia</th>
              <th>Temp.</th>
              <th>Presión</th>
              <th>Ola</th>
              <th>Marea</th>
              <th>Luna</th>
              <th>Lectura</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(renderRow).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderRow(row) {
    const quality = qualityClass(row.fishing_category);
    const wind = `${value(row.wind_speed_ms, "m/s")} · ${compass(row.wind_direction_deg)}<br><span class="small-muted">Racha ${value(row.wind_gust_ms, "m/s")}</span>`;
    const rain = `${value(row.precipitation_mm, "mm")}<br><span class="small-muted">${value(row.precipitation_probability, "%")}</span>`;
    const pressureTrend = row.pressure_trend_hpa === null ? "" : ` (${row.pressure_trend_hpa > 0 ? "+" : ""}${row.pressure_trend_hpa})`;
    const wave = `${value(row.wave_height_m, "m")} · ${value(row.wave_period_s, "s")}<br><span class="small-muted">${compass(row.wave_direction_deg)}</span>`;
    const tide = `${escapeHtml(row.tide_state || "sin datos")}<br><span class="small-muted">${value(row.tide_height_m, "m")}</span>`;

    return `
      <tr>
        <td>${formatDateTime(row.datetime)}</td>
        <td>${escapeHtml(row.weather_description || "Sin datos")}</td>
        <td><span class="hour-score ${quality}">${row.fishing_score}</span></td>
        <td>${wind}</td>
        <td>${rain}</td>
        <td>${value(row.temperature_c, "°C")}</td>
        <td>${value(row.pressure_hpa, "hPa")}${pressureTrend}</td>
        <td>${wave}</td>
        <td>${tide}</td>
        <td>${escapeHtml(row.moon_phase || "sin datos")}</td>
        <td>${escapeHtml(row.explanation)}</td>
      </tr>
    `;
  }

  function qualityClass(category) {
    const normalized = String(category || "").toLowerCase();
    if (normalized.includes("muy")) return "great";
    if (normalized.includes("buena")) return "good";
    if (normalized.includes("regular")) return "regular";
    return "bad";
  }

  function value(raw, unit) {
    if (raw === null || raw === undefined || Number.isNaN(raw)) return "s/d";
    return `${raw}${unit ? ` ${unit}` : ""}`;
  }

  function formatDateTime(value) {
    return new Intl.DateTimeFormat("es-ES", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(new Date(value));
  }

  function compass(degrees) {
    if (degrees === null || degrees === undefined || Number.isNaN(degrees)) return "s/d";
    const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    return `${directions[Math.round(degrees / 45) % 8]} ${Math.round(degrees)}°`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  return { loadForecast, clear, qualityClass };
})();

