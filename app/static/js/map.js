const MapApp = (() => {
  const config = window.ARCAFISH_CONFIG;
  const state = {
    map: null,
    spots: [],
    markers: new Map(),
    markerMeta: new Map(),
    selectedSpotId: null,
    pendingMarker: null
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
    document.getElementById("cancel-spot").addEventListener("click", closeSpotForm);
    document.getElementById("refresh-spots").addEventListener("click", loadSpots);
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
    renderSpotList();
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

      const markerMeta = state.markerMeta.get(spot.id);
      if (markerMeta?.windMs !== undefined) {
        const wind = document.createElement("div");
        wind.className = "spot-meta spot-wind";
        wind.textContent = `Viento prox. 3 h: ${markerMeta.windMs.toFixed(1)} m/s`;
        main.appendChild(wind);
      }

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
    const windLabel = Number.isFinite(meta?.windMs) ? `<div class="wind-chip">${meta.windMs.toFixed(1)} m/s</div>` : "";
    return L.divIcon({
      className: "",
      html: `<div class="spot-marker-wrap"><div class="spot-marker ${quality}"></div>${windLabel}</div>`,
      iconSize: [82, 28],
      iconAnchor: [14, 14]
    });
  }

  function buildTooltip(spotId, name) {
    const meta = state.markerMeta.get(spotId);
    const wind = Number.isFinite(meta?.windMs) ? ` · ${meta.windMs.toFixed(1)} m/s` : "";
    return `${name}${wind}`;
  }

  function setMarkerForecast(spotId, forecast) {
    state.markerMeta.set(spotId, {
      quality: ForecastUI.qualityClass(forecast.summary.category),
      windMs: forecast.summary.current_wind_ms
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
    renderSpotList();
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
      ForecastUI.clear();
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

  return { init, loadSpots };
})();

document.addEventListener("DOMContentLoaded", MapApp.init);
