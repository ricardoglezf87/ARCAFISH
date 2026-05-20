const ForecastUI = (() => {
  const panelId = "forecast-panel";
  const state = {
    forecast: null,
    selectedSpecies: "general",
    selectedDay: "all",
    intervalHours: 3
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
      state.forecast = await response.json();
      state.selectedSpecies = "general";
      state.selectedDay = "all";
      renderForecast();
      return state.forecast;
    } catch (error) {
      panel.innerHTML = `<div class="forecast-error">${escapeHtml(error.message)}</div>`;
      return null;
    }
  }

  function clear() {
    state.forecast = null;
    state.selectedSpecies = "general";
    state.selectedDay = "all";
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
              <div class="small-muted">Prediccion cargada: ${forecast.meta.forecast_days} dias - Base del indice: proximas 24 h</div>
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
              <div class="summary-stats">
                <span class="meta-pill">Ahora ${forecast.summary.current_score}</span>
                <span class="meta-pill">Mejor ventana ${summary.best_score ?? summary.score}</span>
                ${renderSeasonalityPill(summary)}
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
    bindDayButtons();
    bindIntervalControl();
    bindExportButtons();
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
          <span class="species-card-meta">${escapeHtml(speciesSummary.category)} - mes ${Math.round((speciesSummary.seasonality_factor || 0) * 100)}%</span>
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

  function bindDayButtons() {
    for (const button of document.querySelectorAll("[data-day-key]")) {
      button.addEventListener("click", () => {
        state.selectedDay = button.dataset.dayKey || "all";
        renderForecast();
      });
    }
  }

  function bindIntervalControl() {
    const input = document.getElementById("interval-hours");
    if (!input) return;
    const updateInterval = () => {
      const nextValue = clampInterval(input.value);
      input.value = String(nextValue);
      state.intervalHours = nextValue;
      renderForecast();
    };
    input.addEventListener("change", updateInterval);
    input.addEventListener("blur", updateInterval);
  }

  function bindExportButtons() {
    for (const button of document.querySelectorAll("[data-export-scope]")) {
      button.addEventListener("click", () => {
        downloadPdf(button.dataset.exportScope || "selected");
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
    const visibleRows = filteredRows(rows);
    return `
      <div class="table-toolbar">
        <div class="day-tabs">${renderDayTabs(rows)}</div>
        <div class="table-tools">
          <label class="interval-control" for="interval-hours">
            Intervalo
            <input id="interval-hours" type="number" min="1" max="12" step="1" value="${state.intervalHours}">
            <span>h</span>
          </label>
          <div class="export-actions">
            <button class="ghost-button" type="button" data-export-scope="selected">PDF vista actual</button>
            <button class="ghost-button" type="button" data-export-scope="all">PDF todas las especies</button>
          </div>
          <div class="small-muted">${visibleRows.length} tramos visibles de ${rows.length}</div>
        </div>
      </div>
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
            ${visibleRows.map(renderRow).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  function renderDayTabs(rows) {
    const tabs = [{ key: "all", label: "Toda la semana" }];
    for (const day of listForecastDays(rows)) {
      tabs.push({ key: day, label: formatDayLabel(day) });
    }
    return tabs.map((tab) => `
      <button class="day-tab ${state.selectedDay === tab.key ? "active" : ""}" type="button" data-day-key="${tab.key}">
        ${escapeHtml(tab.label)}
      </button>
    `).join("");
  }

  function renderRow(row) {
    const scoreBlock = getRowScore(row);
    const quality = qualityClass(scoreBlock.category);
    const wind = `${value(row.wind_speed_ms, "m/s")} - ${compass(row.wind_direction_deg)}<br><span class="small-muted">Racha ${value(row.wind_gust_ms, "m/s")}</span>`;
    const rain = `${value(row.precipitation_mm, "mm")}<br><span class="small-muted">${value(row.precipitation_probability, "%")}</span>`;
    const sea = `${value(row.wave_height_m, "m")} - ${value(row.wave_period_s, "s")}<br><span class="small-muted">Agua ${value(row.sea_surface_temperature_c, "C")}</span>`;
    const tide = `${escapeHtml(row.tide_state || "sin datos")}<br><span class="small-muted">${value(row.tide_height_m, "m")}</span>`;
    const pressure = `${value(row.pressure_hpa, "hPa")}${row.pressure_trend_hpa === null ? "" : ` (${row.pressure_trend_hpa > 0 ? "+" : ""}${row.pressure_trend_hpa})`}`;

    return `
      <tr>
        <td>${formatDateTime(row.datetime)}</td>
        <td>${escapeHtml(row.weather_description || "Sin datos")}<br><span class="small-muted">${pressure}</span></td>
        <td><span class="hour-score ${quality}">${scoreBlock.score}</span></td>
        <td>${wind}</td>
        <td>${rain}</td>
        <td>${value(row.temperature_c, "C")}</td>
        <td>${sea}</td>
        <td>${tide}</td>
        <td>${escapeHtml(row.moon_phase || "sin datos")}</td>
        <td>${escapeHtml(humanReading(row))}</td>
      </tr>
    `;
  }

  function getRowScore(row) {
    if (state.selectedSpecies === "general") {
      return {
        score: row.fishing_score,
        category: row.fishing_category
      };
    }
    return row.species_scores[state.selectedSpecies];
  }

  function humanReading(row) {
    const parts = [];
    parts.push(row.weather_description || "Tiempo variable");
    parts.push(simpleWind(row));
    parts.push(simpleSea(row));
    parts.push(simpleRain(row));
    parts.push(simpleTide(row));
    return `${parts.filter(Boolean).join(". ")}.`;
  }

  function filteredRows(rows) {
    const scopedRows = state.selectedDay === "all"
      ? rows
      : rows.filter((row) => rowDayKey(row.datetime) === state.selectedDay);
    return scopedRows.filter((row) => rowMatchesInterval(row));
  }

  function listForecastDays(rows) {
    return [...new Set(rows.map((row) => rowDayKey(row.datetime)))];
  }

  function rowDayKey(value) {
    return String(value || "").slice(0, 10);
  }

  function formatDayLabel(value) {
    const date = new Date(`${value}T00:00:00`);
    return new Intl.DateTimeFormat("es-ES", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit"
    }).format(date);
  }

  function rowMatchesInterval(row) {
    const interval = clampInterval(state.intervalHours);
    if (interval <= 1) return true;
    const date = new Date(row.datetime);
    return date.getHours() % interval === 0;
  }

  function clampInterval(value) {
    const parsed = Number.parseInt(value, 10);
    if (Number.isNaN(parsed)) return 3;
    return Math.min(12, Math.max(1, parsed));
  }

  function downloadPdf(scope) {
    if (!state.forecast?.spot?.id) return;
    const params = new URLSearchParams({
      day: state.selectedDay,
      species_scope: scope,
      species_id: state.selectedSpecies,
      interval_hours: String(clampInterval(state.intervalHours))
    });
    const url = `/api/spots/${state.forecast.spot.id}/forecast/export?${params.toString()}`;
    const link = document.createElement("a");
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  function simpleWind(row) {
    if (row.wind_speed_ms === null || row.wind_speed_ms === undefined) return "Sin dato claro de viento";
    if (row.wind_speed_ms >= 11) return `Viento fuerte del ${compassShort(row.wind_direction_deg)}`;
    if (row.wind_speed_ms >= 7) return `Viento moderado tirando a vivo del ${compassShort(row.wind_direction_deg)}`;
    if (row.wind_speed_ms >= 3) return `Viento moderado del ${compassShort(row.wind_direction_deg)}`;
    return `Viento flojo del ${compassShort(row.wind_direction_deg)}`;
  }

  function simpleSea(row) {
    if (row.wave_height_m === null || row.wave_height_m === undefined) return "Mar sin dato suficiente";
    if (row.wave_height_m >= 2.5) return `Mar muy dura con olas de ${row.wave_height_m} m`;
    if (row.wave_height_m >= 1.8) return `Mar movida con olas de ${row.wave_height_m} m`;
    if (row.wave_height_m >= 0.8) return `Mar manejable con olas de ${row.wave_height_m} m`;
    return `Mar bastante calmada con olas de ${row.wave_height_m} m`;
  }

  function simpleRain(row) {
    if (row.precipitation_mm === null || row.precipitation_mm === undefined) return "";
    if (row.precipitation_mm >= 4) return "Lluvia intensa prevista";
    if (row.precipitation_mm >= 1.5) return "Algo de lluvia";
    if (row.precipitation_mm > 0) return "Posible lluvia debil";
    return "Sin lluvia prevista";
  }

  function simpleTide(row) {
    if (!row.tide_state || row.tide_state === "sin datos") return "";
    return `Marea ${row.tide_state}`;
  }

  function renderSeasonalityPill(summary) {
    if (state.selectedSpecies === "general" || summary.seasonality_factor === undefined) return "";
    return `<span class="meta-pill">Mes ${Math.round(summary.seasonality_factor * 100)}%</span>`;
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
    return `${directions[Math.round(degrees / 45) % 8]} ${Math.round(degrees)} deg`;
  }

  function compassShort(degrees) {
    if (degrees === null || degrees === undefined || Number.isNaN(degrees)) return "direccion desconocida";
    const directions = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    return directions[Math.round(degrees / 45) % 8];
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
