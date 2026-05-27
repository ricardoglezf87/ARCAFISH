const MapApp = (() => {
  const config = window.ARCAFISH_CONFIG;
  const methodLabels = {
    float: "Boya",
    bottom: "Fondo",
    spinning: "Spinning / rockfishing"
  };
  const defaultMethodContexts = {
    float: { shore_type: "volcanic", spot_type: "rocky", spot_exposure: "semi_exposed", water_depth_estimate_m: null },
    bottom: { shore_type: "volcanic", spot_type: "rocky", spot_exposure: "semi_exposed", water_depth_estimate_m: null },
    spinning: { shore_type: "volcanic", spot_type: "rocky", spot_exposure: "semi_exposed", water_depth_estimate_m: null }
  };
  const state = {
    map: null,
    spots: [],
    markers: new Map(),
    markerMeta: new Map(),
    selectedSpotId: null,
    pendingMarker: null,
    mapVisible: false,
    spotConfigVisible: false
  };

  function init() {
    state.map = L.map("map", { zoomControl: true }).setView(config.mapCenter, config.mapZoom);

    const streetLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    });
    const satelliteLayer = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution: "Tiles &copy; Esri"
      }
    );

    streetLayer.addTo(state.map);
    L.control.layers(
      {
        Callejero: streetLayer,
        Satelite: satelliteLayer
      },
      {},
      { position: "topleft" }
    ).addTo(state.map);

    state.map.on("click", (event) => openSpotForm(event.latlng));
    document.getElementById("spot-form").addEventListener("submit", saveSpot);
    document.getElementById("spot-config-form").addEventListener("submit", saveSpotConfig);
    document.getElementById("cancel-spot").addEventListener("click", closeSpotForm);
    document.getElementById("refresh-spots").addEventListener("click", loadSpots);
    document.getElementById("toggle-map").addEventListener("click", toggleMapVisibility);
    document.getElementById("spot-select").addEventListener("change", handleSpotSelectChange);
    document.getElementById("toggle-spot-config").addEventListener("click", toggleSpotConfigPanel);
    document.getElementById("close-spot-config").addEventListener("click", () => setSpotConfigVisible(false));
    document.getElementById("delete-selected-spot").addEventListener("click", () => {
      if (state.selectedSpotId) {
        deleteSpot(state.selectedSpotId);
      }
    });
    loadSpots();
  }

  async function loadSpots() {
    setStatus("Cargando puntos");
    const response = await fetch("/api/spots");
    if (!response.ok) {
      setStatus("Error al cargar puntos");
      return;
    }
    state.spots = await response.json();
    if (state.selectedSpotId && !selectedSpot()) {
      state.selectedSpotId = null;
      state.spotConfigVisible = false;
      ForecastUI.clear();
    }
    renderSpotList();
    renderSpotConfigPanel();
    renderMarkers();
    setStatus("Listo");
  }

  function renderSpotList() {
    const list = document.getElementById("spots-list");
    const empty = document.getElementById("spots-empty");
    list.innerHTML = "";
    empty.hidden = state.spots.length > 0;

    for (const spot of state.spots) {
      const item = document.createElement("li");
      item.className = `spot-item ${spot.id === state.selectedSpotId ? "active" : ""}`;
      item.dataset.spotId = spot.id;

      const main = document.createElement("div");
      const button = document.createElement("button");
      button.className = "spot-name";
      button.textContent = spot.name;
      button.addEventListener("click", () => selectSpot(spot.id));

      const meta = document.createElement("div");
      meta.className = "spot-meta";
      meta.textContent = `${spot.latitude.toFixed(4)}, ${spot.longitude.toFixed(4)}`;
      main.append(button, meta);

      if (spot.notes) {
        const notes = document.createElement("div");
        notes.className = "spot-meta";
        notes.textContent = spot.notes;
        main.appendChild(notes);
      }

      const del = document.createElement("button");
      del.className = "danger-button";
      del.textContent = "Eliminar";
      del.addEventListener("click", () => deleteSpot(spot.id));
      item.append(main, del);
      list.appendChild(item);
    }
    renderSpotSelect();
    renderSpotConfigPanel();
  }

  function renderSpotSelect() {
    const select = document.getElementById("spot-select");
    const deleteButton = document.getElementById("delete-selected-spot");
    if (!select) return;

    if (!state.spots.length) {
      select.innerHTML = `<option value="">Sin puntos guardados</option>`;
      select.disabled = true;
    } else {
      select.disabled = false;
      select.innerHTML = [
        `<option value="">Selecciona un punto</option>`,
        ...state.spots.map((spot) => (
          `<option value="${spot.id}"${spot.id === state.selectedSpotId ? " selected" : ""}>${escapeHtml(spot.name)}</option>`
        ))
      ].join("");
    }

    if (deleteButton) {
      deleteButton.hidden = !state.selectedSpotId;
    }
  }

  function renderSpotConfigPanel() {
    const panel = document.getElementById("spot-config-panel");
    const form = document.getElementById("spot-config-form");
    const spot = selectedSpot();
    if (!panel || !form) return;
    if (!spot) {
      state.spotConfigVisible = false;
    }
    panel.hidden = !spot || !state.spotConfigVisible;
    syncSpotConfigButton();
    if (!spot || !state.spotConfigVisible) {
      form.innerHTML = "";
      return;
    }
    const contexts = normalizedMethodContexts(spot.method_contexts);
    form.innerHTML = `
      ${Object.keys(methodLabels).map((method) => renderMethodContext(method, contexts[method])).join("")}
      <button type="submit" class="primary-button">Guardar configuracion</button>
    `;
  }

  function syncSpotConfigButton() {
    const button = document.getElementById("toggle-spot-config");
    if (!button) return;
    const hasSpot = Boolean(selectedSpot());
    button.hidden = !hasSpot;
    button.textContent = state.spotConfigVisible ? "Ocultar config." : "Configurar";
    button.setAttribute("aria-controls", "spot-config-panel");
    button.setAttribute("aria-expanded", hasSpot && state.spotConfigVisible ? "true" : "false");
  }

  function renderMethodContext(method, context) {
    return `
      <fieldset class="method-config-group">
        <legend>${escapeHtml(methodLabels[method])}</legend>
        <label for="shore-type-${method}">Costa</label>
        <select id="shore-type-${method}" data-method="${method}" data-context-field="shore_type">
          ${option("volcanic", "Volcanica", context.shore_type)}
          ${option("beach", "Playa", context.shore_type)}
          ${option("pier", "Espigon", context.shore_type)}
          ${option("cliff", "Acantilado", context.shore_type)}
        </select>
        <label for="spot-type-${method}">Fondo</label>
        <select id="spot-type-${method}" data-method="${method}" data-context-field="spot_type">
          ${option("rocky", "Roca", context.spot_type)}
          ${option("mixed", "Mixto", context.spot_type)}
          ${option("sandy", "Arena", context.spot_type)}
          ${option("reef", "Arrecife", context.spot_type)}
          ${option("harbor", "Puerto", context.spot_type)}
        </select>
        <label for="spot-exposure-${method}">Exposicion</label>
        <select id="spot-exposure-${method}" data-method="${method}" data-context-field="spot_exposure">
          ${option("sheltered", "Resguardado", context.spot_exposure)}
          ${option("semi_exposed", "Semi expuesto", context.spot_exposure)}
          ${option("exposed", "Expuesto", context.spot_exposure)}
        </select>
        <label for="water-depth-${method}">Profundidad estimada</label>
        <input id="water-depth-${method}" data-method="${method}" data-context-field="water_depth_estimate_m" type="number" min="0" max="200" step="1" placeholder="Opcional" value="${context.water_depth_estimate_m ?? ""}">
      </fieldset>
    `;
  }

  async function handleSpotSelectChange(event) {
    const spotId = Number.parseInt(event.target.value, 10);
    if (!spotId) {
      state.selectedSpotId = null;
      state.spotConfigVisible = false;
      ForecastUI.clear();
      renderSpotList();
      return;
    }
    await selectSpot(spotId);
  }

  function toggleSpotConfigPanel() {
    if (!selectedSpot()) return;
    setSpotConfigVisible(!state.spotConfigVisible);
  }

  function setSpotConfigVisible(visible) {
    state.spotConfigVisible = Boolean(visible) && Boolean(selectedSpot());
    renderSpotConfigPanel();
  }

  function renderMarkers() {
    for (const marker of state.markers.values()) {
      marker.remove();
    }
    state.markers.clear();

    for (const spot of state.spots) {
      const marker = L.marker([spot.latitude, spot.longitude], {
        icon: markerIcon(state.markerMeta.get(spot.id))
      }).addTo(state.map);
      marker.bindTooltip(buildTooltip(spot.id, spot.name), { direction: "top" });
      marker.on("click", () => selectSpot(spot.id));
      state.markers.set(spot.id, marker);
    }
  }

  function markerIcon(meta) {
    const quality = meta?.quality || "neutral";
    return L.divIcon({
      className: "",
      html: `<div class="spot-marker-wrap"><div class="spot-marker ${quality}"></div></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });
  }

  function buildTooltip(spotId, name) {
    return name;
  }

  function setMarkerForecast(spotId, forecast) {
    state.markerMeta.set(spotId, {
      quality: ForecastUI.qualityClass(forecast.summary.category)
    });

    const marker = state.markers.get(spotId);
    const spot = state.spots.find((item) => item.id === spotId);
    if (marker && spot) {
      marker.setIcon(markerIcon(state.markerMeta.get(spotId)));
      marker.setTooltipContent(buildTooltip(spotId, spot.name));
    }
    renderSpotList();
  }

  function openSpotForm(latlng) {
    if (!insideBounds(latlng.lat, latlng.lng)) {
      setStatus("Fuera del ambito inicial de Canarias");
      return;
    }
    if (state.pendingMarker) {
      state.pendingMarker.remove();
    }
    state.pendingMarker = L.marker(latlng, { icon: markerIcon() }).addTo(state.map);
    document.getElementById("spot-lat").value = latlng.lat;
    document.getElementById("spot-lon").value = latlng.lng;
    document.getElementById("form-coordinates").textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
    document.getElementById("spot-form").hidden = false;
    document.getElementById("spot-name").focus();
  }

  function closeSpotForm() {
    document.getElementById("spot-form").reset();
    document.getElementById("spot-form").hidden = true;
    if (state.pendingMarker) {
      state.pendingMarker.remove();
      state.pendingMarker = null;
    }
  }

  async function saveSpot(event) {
    event.preventDefault();
    const payload = {
      name: document.getElementById("spot-name").value,
      latitude: Number(document.getElementById("spot-lat").value),
      longitude: Number(document.getElementById("spot-lon").value),
      notes: document.getElementById("spot-notes").value || null
    };

    setStatus("Guardando punto");
    const response = await fetch("/api/spots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "No se pudo guardar." }));
      setStatus(error.detail || "Error al guardar");
      return;
    }
    const spot = await response.json();
    closeSpotForm();
    await loadSpots();
    await selectSpot(spot.id);
  }

  async function selectSpot(spotId) {
    state.selectedSpotId = spotId;
    state.spotConfigVisible = false;
    renderSpotList();
    renderSpotConfigPanel();
    const spot = state.spots.find((item) => item.id === spotId);
    if (spot) {
      state.map.setView([spot.latitude, spot.longitude], Math.max(state.map.getZoom(), 12));
    }
    setStatus("Calculando pronostico");
    const forecast = await ForecastUI.loadForecast(spotId);
    if (forecast?.summary) {
      setMarkerForecast(spotId, forecast);
    }
    setStatus("Listo");
  }

  async function deleteSpot(spotId) {
    setStatus("Eliminando punto");
    const response = await fetch(`/api/spots/${spotId}`, { method: "DELETE" });
    if (!response.ok) {
      setStatus("Error al eliminar");
      return;
    }
    state.markerMeta.delete(spotId);
    if (state.selectedSpotId === spotId) {
      state.selectedSpotId = null;
      state.spotConfigVisible = false;
      ForecastUI.clear();
      renderSpotConfigPanel();
    }
    await loadSpots();
  }

  function insideBounds(lat, lon) {
    const b = config.bounds;
    return lat >= b.min_lat && lat <= b.max_lat && lon >= b.min_lon && lon <= b.max_lon;
  }

  function setStatus(text) {
    const element = document.getElementById("app-status");
    if (element) {
      element.textContent = text;
    }
  }

  async function saveSpotConfig(event) {
    event.preventDefault();
    if (!state.selectedSpotId) return;
    const payload = { method_contexts: readMethodContextsFromForm() };
    setStatus("Guardando configuracion");
    const response = await fetch(`/api/spots/${state.selectedSpotId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "No se pudo guardar la configuracion." }));
      setStatus(error.detail || "Error al guardar configuracion");
      return;
    }
    const updatedSpot = await response.json();
    state.spots = state.spots.map((spot) => spot.id === updatedSpot.id ? updatedSpot : spot);
    renderSpotList();
    renderSpotConfigPanel();
    await ForecastUI.loadForecast(state.selectedSpotId, { preserveView: true });
    setStatus("Listo");
  }

  function readMethodContextsFromForm() {
    const contexts = normalizedMethodContexts({});
    for (const method of Object.keys(methodLabels)) {
      for (const field of ["shore_type", "spot_type", "spot_exposure", "water_depth_estimate_m"]) {
        const input = document.querySelector(`[data-method="${method}"][data-context-field="${field}"]`);
        if (!input) continue;
        if (field === "water_depth_estimate_m") {
          contexts[method][field] = input.value === "" ? null : Number(input.value);
        } else {
          contexts[method][field] = input.value;
        }
      }
    }
    return contexts;
  }

  function normalizedMethodContexts(raw) {
    const contexts = JSON.parse(JSON.stringify(defaultMethodContexts));
    for (const method of Object.keys(contexts)) {
      Object.assign(contexts[method], raw?.[method] || {});
    }
    return contexts;
  }

  function selectedSpot() {
    return state.spots.find((item) => item.id === state.selectedSpotId) || null;
  }

  function option(value, label, selectedValue) {
    return `<option value="${escapeHtml(value)}"${value === selectedValue ? " selected" : ""}>${escapeHtml(label)}</option>`;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toggleMapVisibility() {
    state.mapVisible = !state.mapVisible;
    const section = document.getElementById("map-section");
    const workspace = document.querySelector(".workspace");
    const button = document.getElementById("toggle-map");
    section.classList.toggle("is-hidden", !state.mapVisible);
    workspace.classList.toggle("map-hidden", !state.mapVisible);
    button.textContent = state.mapVisible ? "Ocultar mapa" : "Mostrar mapa";
    if (state.mapVisible) {
      setTimeout(() => state.map.invalidateSize(), 50);
    }
  }

  return { init, loadSpots };
})();

document.addEventListener("DOMContentLoaded", MapApp.init);
