const ForecastUI = (() => {
  const panelId = "forecast-panel";
  const state = {
    forecast: null,
    spotId: null,
    selectedSpecies: "general",
    selectedDay: "all",
    intervalHours: 3,
    fishingContext: {
      fishingMethod: "float",
      castingDistanceM: 20
    },
    requestId: 0,
    refreshTimer: null,
    backgroundRefreshAttempts: 0,
    loadingTimers: []
  };
  const averageFields = {
    wind_speed_ms: 1,
    wind_gust_ms: 1,
    temperature_c: 1,
    precipitation_mm: 1,
    precipitation_probability: 0,
    pressure_hpa: 0,
    pressure_trend_hpa: 1,
    cloud_cover_percent: 0,
    wave_height_m: 1,
    wave_period_s: 0,
    sea_surface_temperature_c: 1,
    tide_height_m: 2,
    fishing_score: 0
  };
  const directionFields = ["wind_direction_deg", "wave_direction_deg"];

  async function loadForecast(spotId, options = {}) {
    const requestId = state.requestId + 1;
    state.requestId = requestId;
    state.spotId = spotId;
    clearRefreshTimer();
    const panel = document.getElementById(panelId);
    if (!options.keepExisting) {
      state.backgroundRefreshAttempts = 0;
      renderLoading(options.forceRefresh);
    }
    try {
      const params = forecastQueryParams();
      if (options.forceRefresh) {
        params.set("force_refresh", "true");
      }
      const response = await fetch(`/api/spots/${spotId}/forecast?${params.toString()}`);
      if (requestId !== state.requestId) {
        return null;
      }
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: "No se pudo obtener el pronostico." }));
        throw new Error(error.detail || "No se pudo obtener el pronostico.");
      }
      clearLoadingTimers();
      state.forecast = await response.json();
      if (!options.preserveView) {
        state.selectedSpecies = "general";
        state.selectedDay = "all";
      }
      renderForecast();
      scheduleRefreshPoll();
      return state.forecast;
    } catch (error) {
      if (requestId !== state.requestId) {
        return null;
      }
      clearLoadingTimers();
      if (options.keepExisting && state.forecast) {
        scheduleRefreshPoll();
        return null;
      }
      panel.innerHTML = `<div class="forecast-error">${escapeHtml(error.message)}</div>`;
      return null;
    }
  }

  function renderLoading(forceRefresh = false) {
    clearLoadingTimers();
    const panel = document.getElementById(panelId);
    const text = forceRefresh ? "Actualizando pronostico..." : "Cargando prevision...";
    panel.innerHTML = `
      <div class="forecast-empty">
        <h2>Pronostico</h2>
        <p id="forecast-loading-text">${text}</p>
      </div>
    `;
    state.loadingTimers = [
      window.setTimeout(() => updateLoadingText("Pidiendo datos meteorologicos y marinos..."), 3500),
      window.setTimeout(() => updateLoadingText("La primera carga puede tardar si no hay cache disponible."), 9000)
    ];
  }

  function updateLoadingText(text) {
    const element = document.getElementById("forecast-loading-text");
    if (element) {
      element.textContent = text;
    }
  }

  function clearLoadingTimers() {
    for (const timer of state.loadingTimers) {
      window.clearTimeout(timer);
    }
    state.loadingTimers = [];
  }

  function clearRefreshTimer() {
    if (state.refreshTimer) {
      window.clearTimeout(state.refreshTimer);
      state.refreshTimer = null;
    }
  }

  function scheduleRefreshPoll() {
    clearRefreshTimer();
    if (!state.forecast?.meta?.refreshing || !state.spotId) {
      state.backgroundRefreshAttempts = 0;
      return;
    }
    if (state.backgroundRefreshAttempts >= 6) {
      return;
    }
    state.backgroundRefreshAttempts += 1;
    state.refreshTimer = window.setTimeout(() => {
      loadForecast(state.spotId, { preserveView: true, keepExisting: true });
    }, 5000);
  }

  function clear() {
    state.requestId += 1;
    clearRefreshTimer();
    clearLoadingTimers();
    state.forecast = null;
    state.spotId = null;
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
    const stale = forecast.meta?.stale ? `<span class="meta-pill warning">Cache caducada</span>` : "";
    const refreshing = forecast.meta?.refreshing ? `<span class="meta-pill refresh">Actualizando</span>` : "";

    const panel = document.getElementById(panelId);
    panel.innerHTML = `
      <div class="forecast-layout">
        <div class="forecast-main">
          <div class="forecast-title">
            <div>
              <h2>${escapeHtml(forecast.spot.name)}</h2>
              <div class="small-muted">${forecast.spot.latitude.toFixed(4)}, ${forecast.spot.longitude.toFixed(4)}</div>
              <div class="small-muted">Prediccion cargada: ${forecast.meta.forecast_days} dias - Base del indice: proximas 24 h</div>
              ${renderProviderMeta(forecast)}
            </div>
            <div class="forecast-actions">
              <div class="forecast-badges">${cached}${stale}${refreshing}<span class="quality-badge ${quality}">${escapeHtml(summary.category)}</span></div>
              <button class="icon-button" id="refresh-forecast" type="button" title="Actualizar pronostico" aria-label="Actualizar pronostico">&#8635;</button>
            </div>
          </div>

          ${renderForecastWarning(forecast)}
          ${renderFishingContextControls(forecast)}
          ${renderSpeciesSelect(forecast)}

          <div class="summary-grid">
            <div class="score-tile ${quality}">
              <div class="score-eyebrow">${escapeHtml(summaryLabel())}</div>
              <div class="score-value">${summary.score}</div>
              <div class="score-label">${escapeHtml(summary.category)}</div>
            </div>
            <div class="summary-copy">
              <p><strong>${escapeHtml(summary.recommendation)}</strong></p>
              ${summary.best_explanation ? `<p class="summary-detail">${escapeHtml(summary.best_explanation)}</p>` : ""}
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
    bindSpeciesSelect();
    bindRefreshButton();
    bindFishingContextControls();
    bindDayButtons();
    bindIntervalControl();
    bindExportButtons();
  }

  function renderForecastWarning(forecast) {
    const messages = [];
    if (forecast.meta?.warning) {
      messages.push(forecast.meta.warning);
    }
    for (const failure of forecast.meta?.weather_provider_failures || []) {
      messages.push(`${failure.provider}: ${failure.error}`);
    }
    if (!messages.length) return "";
    return `<p class="forecast-warning">${messages.map(escapeHtml).join("<br>")}</p>`;
  }

  function renderProviderMeta(forecast) {
    const providers = forecast.meta?.weather_providers || [];
    const weatherProvider = forecast.meta?.weather_provider || providers[0];
    const weatherText = forecast.meta?.weather_ensemble
      ? `Meteo: media de ${providers.length} proveedores`
      : `Meteo: ${weatherProvider || "s/d"}`;
    const marineText = forecast.meta?.marine_provider ? `Mar: ${forecast.meta.marine_provider}` : "";
    return `<div class="small-muted">${escapeHtml([weatherText, marineText].filter(Boolean).join(" - "))}</div>`;
  }

  function bindRefreshButton() {
    const button = document.getElementById("refresh-forecast");
    if (!button) return;
    button.addEventListener("click", () => {
      if (!state.spotId) return;
      loadForecast(state.spotId, { preserveView: true, forceRefresh: true });
    });
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

  function renderSpeciesSelect(forecast) {
    const profiles = forecast.meta?.species_profiles || [];
    const generalSelected = state.selectedSpecies === "general" ? " selected" : "";
    const options = [
      `<option value="general"${generalSelected}>General costa - ${forecast.summary.score} (${escapeHtml(forecast.summary.category)})</option>`
    ];
    for (const profile of profiles) {
      const speciesSummary = forecast.summary.species[profile.id];
      if (!speciesSummary) continue;
      const selected = state.selectedSpecies === profile.id ? " selected" : "";
      options.push(
        `<option value="${escapeHtml(profile.id)}"${selected}>${escapeHtml(profile.name)} - ${speciesSummary.score} (${escapeHtml(speciesSummary.category)})</option>`
      );
    }
    return `
      <section class="species-select-panel" aria-label="Seleccion de especie">
        <label class="field-control" for="species-select">
          <span>Especie</span>
          <select id="species-select">
            ${options.join("")}
          </select>
        </label>
      </section>
    `;
  }

  function renderFishingContextControls(forecast) {
    const context = forecast.fishing_context || forecast.meta?.fishing_context || {};
    const distance = Number(context.casting_distance_m ?? state.fishingContext.castingDistanceM);
    return `
      <section class="fishing-context-panel" aria-label="Contexto de pesca">
        <div class="fishing-context-grid">
          <label class="field-control" for="fishing-method">
            <span>Modalidad</span>
            <select id="fishing-method">
              ${option("float", "Boya", state.fishingContext.fishingMethod)}
              ${option("bottom", "Fondo", state.fishingContext.fishingMethod)}
              ${option("spinning", "Spinning / rockfishing", state.fishingContext.fishingMethod)}
            </select>
          </label>

          <label class="field-control" for="casting-distance">
            <span>Distancia de lance desde costa</span>
            <select id="casting-distance">
              ${renderDistanceOptions(distance)}
            </select>
          </label>

        </div>

        <div class="context-reading">
          <p>${escapeHtml(context.interpretation || fishingContextMessage())}</p>
          <div class="summary-stats">
            <span class="meta-pill">Zona ${escapeHtml(context.target_zone_label || "s/d")}</span>
            <span class="meta-pill">Columna ${escapeHtml(waterColumnLabel(context.water_column))}</span>
            <span class="meta-pill">Lance ${escapeHtml(String(context.casting_distance_m ?? distance))} m</span>
            ${context.spot_type ? `<span class="meta-pill">${escapeHtml(spotTypeLabel(context.spot_type))}</span>` : ""}
            ${context.spot_exposure ? `<span class="meta-pill">${escapeHtml(exposureLabel(context.spot_exposure))}</span>` : ""}
            ${context.water_depth_estimate_m !== null && context.water_depth_estimate_m !== undefined ? `<span class="meta-pill">Prof. ${escapeHtml(String(context.water_depth_estimate_m))} m</span>` : ""}
          </div>
        </div>
      </section>
    `;
  }

  function bindFishingContextControls() {
    const method = document.getElementById("fishing-method");
    const distance = document.getElementById("casting-distance");
    if (!method || !distance) return;

    const reload = () => reloadForecastWithContext();
    method.addEventListener("change", () => {
      state.fishingContext.fishingMethod = method.value;
      applyMethodDistanceDefault(method.value);
      reload();
    });
    distance.addEventListener("change", () => {
      state.fishingContext.castingDistanceM = clampDistance(distance.value);
      reload();
    });
  }

  function reloadForecastWithContext() {
    if (!state.spotId) return;
    loadForecast(state.spotId, { preserveView: true });
  }

  function bindSpeciesButtons() {
    for (const button of document.querySelectorAll("[data-species-id]")) {
      button.addEventListener("click", () => {
        state.selectedSpecies = button.dataset.speciesId || "general";
        renderForecast();
      });
    }
  }

  function bindSpeciesSelect() {
    const select = document.getElementById("species-select");
    if (!select) return;
    select.addEventListener("change", () => {
      state.selectedSpecies = select.value || "general";
      renderForecast();
    });
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

  function forecastQueryParams() {
    const params = new URLSearchParams({
      fishing_method: state.fishingContext.fishingMethod,
      casting_distance_m: String(state.fishingContext.castingDistanceM)
    });
    return params;
  }

  function option(value, label, selectedValue) {
    return `<option value="${escapeHtml(value)}"${value === selectedValue ? " selected" : ""}>${escapeHtml(label)}</option>`;
  }

  function renderDistanceOptions(selectedDistance) {
    const selected = clampDistance(selectedDistance);
    const values = [...new Set([0, 10, 20, 30, 35, 40, 50, 60, 80, 100, 120, 150, 200, selected])]
      .sort((first, second) => first - second);
    return values.map((distance) => option(String(distance), `${distance} m`, String(selected))).join("");
  }

  function applyMethodDistanceDefault(method) {
    const current = Number(state.fishingContext.castingDistanceM);
    if (method === "float" && (current > 30 || current < 0)) {
      state.fishingContext.castingDistanceM = 20;
    } else if (method === "bottom" && current < 50) {
      state.fishingContext.castingDistanceM = 80;
    } else if (method === "spinning" && current > 80) {
      state.fishingContext.castingDistanceM = 35;
    }
  }

  function clampDistance(value) {
    const parsed = Number.parseFloat(value);
    if (Number.isNaN(parsed)) return 20;
    return Math.min(200, Math.max(0, Math.round(parsed)));
  }

  function fishingContextMessage() {
    if (state.fishingContext.fishingMethod === "bottom") {
      return "Estas pescando a fondo. Los lances largos favorecen especies de zonas exteriores y dependen mas de marea, corriente, fondo y profundidad estimada.";
    }
    return "Estas pescando cerca de costa. La distancia de lance se mide desde la orilla, no como profundidad.";
  }

  function spotTypeLabel(value) {
    const labels = { rocky: "Roca", mixed: "Mixto", sandy: "Arena", reef: "Arrecife", harbor: "Puerto" };
    return labels[value] || value;
  }

  function exposureLabel(value) {
    const labels = { sheltered: "Resguardado", semi_exposed: "Semi expuesto", exposed: "Expuesto" };
    return labels[value] || value;
  }

  function waterColumnLabel(value) {
    if (value === "surface") return "superficie";
    if (value === "mid_water") return "media agua";
    if (value === "bottom") return "fondo";
    return "s/d";
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
    const currentRowDatetime = currentVisibleRowDatetime(visibleRows);
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
            ${visibleRows.map((row) => renderRow(row, row.datetime === currentRowDatetime)).join("")}
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

  function renderRow(row, isCurrent = false) {
    const scoreBlock = getRowScore(row);
    const quality = qualityClass(scoreBlock.category);
    const wind = `${value(row.wind_speed_ms, "m/s")} - ${compass(row.wind_direction_deg)}<br><span class="small-muted">Racha ${value(row.wind_gust_ms, "m/s")}</span>`;
    const rain = `${value(row.precipitation_mm, "mm")}<br><span class="small-muted">${value(row.precipitation_probability, "%")}</span>`;
    const sea = `${value(row.wave_height_m, "m")} - ${value(row.wave_period_s, "s")}<br><span class="small-muted">Agua ${value(row.sea_surface_temperature_c, "C")}</span>`;
    const tide = `${escapeHtml(row.tide_state || "sin datos")}<br><span class="small-muted">${value(row.tide_height_m, "m")}</span>`;
    const pressure = `${value(row.pressure_hpa, "hPa")}${row.pressure_trend_hpa === null ? "" : ` (${row.pressure_trend_hpa > 0 ? "+" : ""}${row.pressure_trend_hpa})`}`;
    const currentBadge = isCurrent ? `<span class="current-row-pill">Ahora</span> ` : "";
    const reading = state.selectedSpecies === "general"
      ? humanReading(row)
      : (scoreBlock.explanation || humanReading(row));

    return `
      <tr class="${isCurrent ? "current-forecast-row" : ""}"${isCurrent ? ` aria-current="time"` : ""}>
        <td>${currentBadge}${formatDateTime(row.datetime, row.period_end_datetime)}</td>
        <td>${escapeHtml(row.weather_description || "Sin datos")}<br><span class="small-muted">${pressure}</span></td>
        <td><span class="hour-score ${quality}">${scoreBlock.score}</span></td>
        <td>${wind}</td>
        <td>${rain}</td>
        <td>${value(row.temperature_c, "C")}</td>
        <td>${sea}</td>
        <td>${tide}</td>
        <td>${escapeHtml(row.moon_phase || "sin datos")}</td>
        <td>${escapeHtml(reading)}</td>
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
    return aggregateRows(scopedRows, clampInterval(state.intervalHours));
  }

  function currentVisibleRowDatetime(rows) {
    if (!rows.length) return null;
    const now = new Date();
    if (Number.isNaN(now.getTime())) return null;
    for (let index = 0; index < rows.length; index += 1) {
      const rowStart = new Date(rows[index].datetime);
      const rowEnd = rows[index].period_end_datetime
        ? new Date(rows[index].period_end_datetime)
        : rows[index + 1] ? new Date(rows[index + 1].datetime) : null;
      if (Number.isNaN(rowStart.getTime())) continue;
      if (now < rowStart) {
        return sameLocalDate(now, rowStart) ? rows[index].datetime : null;
      }
      if (rowEnd && Number.isNaN(rowEnd.getTime())) continue;
      if (now >= rowStart && (!rowEnd || now < rowEnd)) {
        return rows[index].datetime;
      }
    }
    return null;
  }

  function sameLocalDate(first, second) {
    return first.getFullYear() === second.getFullYear()
      && first.getMonth() === second.getMonth()
      && first.getDate() === second.getDate();
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

  function aggregateRows(rows, interval) {
    if (interval <= 1) return rows;
    const groups = new Map();
    for (const row of rows) {
      const start = intervalStart(row.datetime, interval);
      if (!start) continue;
      const key = toLocalIso(start);
      if (!groups.has(key)) {
        groups.set(key, { start, rows: [] });
      }
      groups.get(key).rows.push(row);
    }
    return [...groups.values()]
      .sort((a, b) => a.start - b.start)
      .map((group) => aggregateInterval(group.start, group.rows, interval));
  }

  function intervalStart(value, interval) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return null;
    const start = new Date(date);
    start.setMinutes(0, 0, 0);
    start.setHours(Math.floor(start.getHours() / interval) * interval);
    return start;
  }

  function aggregateInterval(start, rows, interval) {
    const first = rows[0] || {};
    const end = new Date(start);
    end.setHours(end.getHours() + interval);
    const aggregate = {
      ...first,
      datetime: toLocalIso(start),
      period_end_datetime: toLocalIso(end),
      period_hours: interval,
      sample_count: rows.length,
      is_aggregate: true
    };

    for (const [field, digits] of Object.entries(averageFields)) {
      aggregate[field] = roundedAverage(rows, field, digits);
    }
    for (const field of directionFields) {
      aggregate[field] = roundedDirection(rows, field);
    }

    aggregate.weather_code = mostCommon(rows, "weather_code");
    aggregate.weather_description = mostCommon(rows, "weather_description") || first.weather_description;
    aggregate.tide_state = mostCommon(rows, "tide_state") || first.tide_state;
    aggregate.moon_phase = mostCommon(rows, "moon_phase") || first.moon_phase;
    aggregate.is_day = mostCommon(rows, "is_day");
    aggregate.fishing_category = categoryForScore(aggregate.fishing_score);
    aggregate.explanation = `Media del tramo calculada con ${rows.length} hora(s).`;
    aggregate.safety_alerts = uniqueItems(rows, "safety_alerts");
    aggregate.missing_fields = uniqueItems(rows, "missing_fields");
    aggregate.factor_scores = averageMapping(rows, "factor_scores", 3);
    aggregate.species_scores = aggregateSpeciesScores(rows);
    return aggregate;
  }

  function roundedAverage(rows, field, digits) {
    const values = rows
      .map((row) => row[field])
      .filter((value) => typeof value === "number" && Number.isFinite(value));
    if (!values.length) return null;
    const factor = 10 ** digits;
    const average = values.reduce((total, value) => total + value, 0) / values.length;
    const rounded = Math.round(average * factor) / factor;
    return digits === 0 ? Math.round(rounded) : rounded;
  }

  function roundedDirection(rows, field) {
    const values = rows
      .map((row) => row[field])
      .filter((value) => typeof value === "number" && Number.isFinite(value));
    if (!values.length) return null;
    const x = values.reduce((total, value) => total + Math.cos(value * Math.PI / 180), 0) / values.length;
    const y = values.reduce((total, value) => total + Math.sin(value * Math.PI / 180), 0) / values.length;
    if (Math.abs(x) < 1e-9 && Math.abs(y) < 1e-9) return null;
    const degrees = Math.round((Math.atan2(y, x) * 180 / Math.PI + 360) % 360);
    return degrees >= 360 ? 0 : degrees;
  }

  function mostCommon(rows, field) {
    const counts = new Map();
    for (const row of rows) {
      const value = row[field];
      if (value === null || value === undefined) continue;
      const key = String(value);
      const item = counts.get(key) || { value, count: 0 };
      item.count += 1;
      counts.set(key, item);
    }
    let best = null;
    for (const item of counts.values()) {
      if (!best || item.count > best.count) best = item;
    }
    return best ? best.value : null;
  }

  function uniqueItems(rows, field) {
    const seen = new Set();
    const items = [];
    for (const row of rows) {
      for (const value of row[field] || []) {
        if (seen.has(value)) continue;
        seen.add(value);
        items.push(value);
      }
    }
    return items;
  }

  function averageMapping(rows, field, digits) {
    const keys = new Set();
    for (const row of rows) {
      const values = row[field] || {};
      for (const [key, value] of Object.entries(values)) {
        if (typeof value === "number" && Number.isFinite(value)) keys.add(key);
      }
    }
    return [...keys].sort().reduce((result, key) => {
      result[key] = roundedAverage(rows.map((row) => row[field] || {}), key, digits);
      return result;
    }, {});
  }

  function aggregateSpeciesScores(rows) {
    const speciesIds = new Set();
    for (const row of rows) {
      for (const speciesId of Object.keys(row.species_scores || {})) {
        speciesIds.add(speciesId);
      }
    }
    return [...speciesIds].sort().reduce((result, speciesId) => {
      const scoreRows = rows
        .filter((row) => row.species_scores?.[speciesId])
        .map((row) => row.species_scores[speciesId]);
      if (!scoreRows.length) return result;
      const score = roundedAverage(scoreRows, "score", 0);
      result[speciesId] = {
        ...scoreRows[0],
        score,
        category: categoryForScore(score),
        base_score: roundedAverage(scoreRows, "base_score", 0),
        seasonality_factor: roundedAverage(scoreRows, "seasonality_factor", 2),
        method_factor: roundedAverage(scoreRows, "method_factor", 3),
        distance_factor: roundedAverage(scoreRows, "distance_factor", 3),
        target_zone_factor: roundedAverage(scoreRows, "target_zone_factor", 3),
        spot_factor: roundedAverage(scoreRows, "spot_factor", 3),
        factor_scores: averageMapping(scoreRows, "factor_scores", 3),
        safety_alerts: uniqueItems(scoreRows, "safety_alerts"),
        missing_fields: uniqueItems(scoreRows, "missing_fields"),
        explanation: `Score medio del tramo calculado con ${scoreRows.length} hora(s).`
      };
      return result;
    }, {});
  }

  function categoryForScore(score) {
    if (score === null || score === undefined || Number.isNaN(score)) return "Mala";
    if (score <= 39) return "Mala";
    if (score <= 59) return "Regular";
    if (score <= 79) return "Buena";
    return "Muy buena";
  }

  function toLocalIso(date) {
    const pad = (value) => String(value).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
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
    for (const [key, value] of forecastQueryParams()) {
      params.set(key, value);
    }
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

  function formatDateTime(value, endValue = null) {
    if (!value) return "s/d";
    const start = new Date(value);
    const formattedStart = new Intl.DateTimeFormat("es-ES", {
      weekday: "short",
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit"
    }).format(start);
    if (!endValue) return formattedStart;
    const end = new Date(endValue);
    if (Number.isNaN(end.getTime())) return formattedStart;
    const formattedEnd = new Intl.DateTimeFormat("es-ES", {
      hour: "2-digit",
      minute: "2-digit"
    }).format(end);
    return `${formattedStart}-${formattedEnd}`;
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
