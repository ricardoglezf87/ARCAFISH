const MapApp = (() => {
  const config = window.ARCAFISH_CONFIG;
  const state = {
    map: null,
    spots: [],
    markers: new Map(),
    selectedSpotId: null,
    pendingMarker: null
  };

  function init() {
    state.map = L.map("map", { zoomControl: true }).setView(config.mapCenter, config.mapZoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap"
    }).addTo(state.map);

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
      setStatus("Error");
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
        icon: markerIcon("neutral")
      }).addTo(state.map);
      marker.bindTooltip(spot.name);
      marker.on("click", () => selectSpot(spot.id));
      state.markers.set(spot.id, marker);
    }
  }

  function markerIcon(quality) {
    return L.divIcon({
      className: "",
      html: `<div class="spot-marker ${quality}"></div>`,
      iconSize: [20, 20],
      iconAnchor: [10, 10]
    });
  }

  function setMarkerQuality(spotId, category) {
    const marker = state.markers.get(spotId);
    if (!marker) return;
    marker.setIcon(markerIcon(ForecastUI.qualityClass(category)));
  }

  function openSpotForm(latlng) {
    if (!insideBounds(latlng.lat, latlng.lng)) {
      setStatus("Fuera de Canarias");
      return;
    }
    if (state.pendingMarker) {
      state.pendingMarker.remove();
    }
    state.pendingMarker = L.marker(latlng, { icon: markerIcon("neutral") }).addTo(state.map);
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

    setStatus("Guardando");
    const response = await fetch("/api/spots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "No se pudo guardar." }));
      setStatus(error.detail || "Error");
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
    setStatus("Calculando");
    const forecast = await ForecastUI.loadForecast(spotId);
    if (forecast?.summary) {
      setMarkerQuality(spotId, forecast.summary.category);
    }
    setStatus("Listo");
  }

  async function deleteSpot(spotId) {
    setStatus("Eliminando");
    const response = await fetch(`/api/spots/${spotId}`, { method: "DELETE" });
    if (!response.ok) {
      setStatus("Error");
      return;
    }
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
    document.getElementById("app-status").textContent = text;
  }

  return { init, loadSpots };
})();

document.addEventListener("DOMContentLoaded", MapApp.init);

