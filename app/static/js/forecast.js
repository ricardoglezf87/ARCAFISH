const ForecastUI = (() => {
  const panelId = "forecast-panel";
  const state = {
    forecast: null,
    selectedSpecies: "general"
  };

  async function loadForecast(spotId) {
    const panel = document.getElementById(panelId);
    panel.innerHTML = `<div class="forecast-empty"><h2>Pronostico</h2><p>Cargando prevision...</p></div>`;
    try {
      const response = await fetch(`/api/spots/${spotId}/forecast`);
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "No se pudo obtener el pronostico." }));
        throw new Error(error.detail || "No se pudo obtener el pronostico.");
      }
      const forecast = await response.json();
      state.forecast = forecast;
      state.selectedSpecies = "general";
      renderForecast();
      return forecast;
    } catch (error) {
      panel.innerHTML = `<div class="forecast-error">${escapeHtml(error.message)}</div>`;
      return null;
    }
  }

  function clear() {
    state.forecast = null;
    state.selectedSpecies = "general";
    const panel = document.getElementById(panelId);
    panel.innerHTML = `
      <div class="forecast-empty">
        <h2>Pronostico</h2>
        <p>Selecciona un punto para ver la prevision horaria, el score general y el score por especie.</p>
      </div>
    `;
  }

  function renderForecast() {
    if (!state.forecast) {
      clear();
      return;
    }
    const forecast = state.forecast;
    const summary = currentSummary();
    const quality = qualityClass(summary.category);
    const alerts = summary.safety_alerts?.length
      ? summary.safety_alerts.map((alert) => `<span class="alert-pill">${escapeHtml(alert)}</span>`).join("")
      : `<span class="meta-pill">Sin alertas principales</span>`;
    const cached = forecast.meta?.cached ? `<span class="meta-pill">Cache</span>` : "";

    const panel = document.getElementById(panelId);
    panel.innerHTML = `
      <div class="forecast-layout">
        <div class="forecast-main">
          <div class="forecast-title">
            <div>
              <h2>${escapeHtml(forecast.spot.name)}</h2>
              <div class="small-muted">${forecast.spot.latitude.toFixed(4)}, ${forecast.spot.longitude.toFixed(4)}</div>
              <div class="small-muted">Base del indice: proximas 24 h desde ${formatDateTime(forecast.summary.current_datetime)}</div>
            </div>
            <div class="forecast-badges">${cached}<span class="quality-badge ${quality}">${escapeHtml(summary.category)}</span></div>
          </div>

          <div class="summary-grid">
            <div class="score-tile ${quality}">
              <div class="score-eyebrow">${escapeHtml(summaryLabel())}</div>
              <div class="score-value">${summary.score}</div>
              <div class="score-label">${escapeHtml(summary.category)}</div>
            </div>
            <div class="summary-copy">
              <p><strong>${escapeHtml(summary.recommendation)}</strong></p>
              <p>${escapeHtml(summary.best_explanation || "")}</p>
              <div class="summary-stats">
                <span class="meta-pill">Ahora ${forecast.summary.current_score}</span>
                <span class="meta-pill">Mejor ventana ${summary.best_score ?? summary.score}</span>
              </div>
              <div class="alert-list">${alerts}</div>
            </div>
          </div>

          ${renderLimitations(forecast)}
          ${renderTable(forecast.hourly)}
        </div>

        <aside class="species-panel">
          <div class="species-section">
            <h3>Score general</h3>
            <button class="species-card ${state.selectedSpecies === "general" ? "active" : ""}" data-species-id="general">
              <span class="species-card-name">General costa</span>
              <span class="species-card-score ${qualityClass(forecast.summary.category)}">${forecast.summary.score}</span>
              <span class="species-card-meta">${escapeHtml(forecast.summary.category)}</span>
            </button>
          </div>
          <div class="species-section">
            <h3>Especies</h3>
            <div class="species-list">
              ${renderSpeciesCards(forecast)}
            </div>
          </div>
        </aside>
      </div>
    `;

    bindSpeciesButtons();
  }

  function renderSpeciesCards(forecast) {
    const profiles = forecast.meta?.species_profiles || [];
    return profiles.map((profile) => {
      const speciesSummary = forecast.summary.species[profile.id];
      const quality = qualityClass(speciesSummary.category);
      return `
        <button class="species-card ${state.selectedSpecies === profile.id ? "active" : ""}" data-species-id="${escapeHtml(profile.id)}">
          <span class="species-card-name">${escapeHtml(profile.name)}</span>
          <span class="species-card-score ${quality}">${speciesSummary.score}</span>
          <span class="species-card-meta">${escapeHtml(speciesSummary.category)}</span>
        </button>
      `;
    }).join("");
  }

  function bindSpeciesButtons() {
    for (const button of document.querySelectorAll("[data-species-id]")) {
      button.addEventListener("click", () => {
        state.selectedSpecies = button.dataset.speciesId || "general";
        renderForecast();
      });
    }
  }

  function currentSummary() {
    if (state.selectedSpecies === "general") {
      return state.forecast.summary;
    }
    return state.forecast.summary.species[state.selectedSpecies];
  }

  function summaryLabel() {
    if (state.selectedSpecies === "general") {
      return "Score general";
    }
    const species = state.forecast.summary.species[state.selectedSpecies];
    return species?.name || "Especie";
  }

  function renderLimitations(forecast) {
    const limitations = forecast.meta?.limitations || [];
    if (!limitations.length) return "";
    return `<p class="small-muted">${limitations.map(escapeHtml).join(" ")}</p>`;
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
              <th>${escapeHtml(summaryLabel())}</th>
              <th>Viento</th>
              <th>Lluvia</th>
              <th>Temp.</th>
              <th>Mar</th>
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
    const scoreBlock = getRowScore(row);
    const quality = qualityClass(scoreBlock.category);
    const wind = `${value(row.wind_speed_ms, "m/s")} · ${compass(row.wind_direction_deg)}<br><span class="small-muted">Racha ${value(row.wind_gust_ms, "m/s")}</span>`;
    const rain = `${value(row.precipitation_mm, "mm")}<br><span class="small-muted">${value(row.precipitation_probability, "%")}</span>`;
    const mar = `${value(row.wave_height_m, "m")} · ${value(row.wave_period_s, "s")}<br><span class="small-muted">Agua ${value(row.sea_surface_temperature_c, "°C")}</span>`;
    const tide = `${escapeHtml(row.tide_state || "sin datos")}<br><span class="small-muted">${value(row.tide_height_m, "m")}</span>`;
    const pressure = `${value(row.pressure_hpa, "hPa")}${row.pressure_trend_hpa === null ? "" : ` (${row.pressure_trend_hpa > 0 ? "+" : ""}${row.pressure_trend_hpa})`}`;

    return `
      <tr>
        <td>${formatDateTime(row.datetime)}</td>
        <td>${escapeHtml(row.weather_description || "Sin datos")}<br><span class="small-muted">${pressure}</span></td>
        <td><span class="hour-score ${quality}">${scoreBlock.score}</span></td>
        <td>${wind}</td>
        <td>${rain}</td>
        <td>${value(row.temperature_c, "°C")}</td>
        <td>${mar}</td>
        <td>${tide}</td>
        <td>${escapeHtml(row.moon_phase || "sin datos")}</td>
        <td>${escapeHtml(scoreBlock.explanation || "")}</td>
      </tr>
    `;
  }

  function getRowScore(row) {
    if (state.selectedSpecies === "general") {
      return {
        score: row.fishing_score,
        category: row.fishing_category,
        explanation: row.explanation
      };
    }
    return row.species_scores[state.selectedSpecies];
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
    if (!value) return "s/d";
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
