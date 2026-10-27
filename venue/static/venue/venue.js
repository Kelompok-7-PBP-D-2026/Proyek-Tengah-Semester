/* Modul Venue dan Lokasi: peta Leaflet (tile OpenStreetMap), jarak rute dari lokasi pengguna
   (OSRM milik OpenStreetMap, dihitung di browser), dan pencarian alamat (Nominatim lewat server). */
(function () {
  "use strict";

  var ORIGIN_KEY = "venue.origin";
  var MODE_KEY = "venue.mode";
  var ROUTE_KEY = "venue.route";
  var ROUTING_BASE = "https://routing.openstreetmap.de/";
  /* Awalan routed-foot/bike/car adalah susunan FOSSGIS; bagian profil di URL diabaikan server. */
  var MODES = {
    foot: { path: "routed-foot", label: "jalan kaki" },
    bike: { path: "routed-bike", label: "bersepeda" },
    car: { path: "routed-car", label: "berkendara" }
  };
  var current = { map: null, markers: {}, userMarker: null, routeLayer: null };
  var state = { origin: null, job: 0 };

  function haversine(lat1, lng1, lat2, lng2) {
    var r = Math.PI / 180;
    var a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 +
      Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lng2 - lng1) * r) / 2) ** 2;
    return 2 * 6371.0088 * Math.asin(Math.sqrt(a));
  }

  function fmtKm(km) { return km.toFixed(1).replace(".", ","); }

  function icon(kind) {
    return L.divIcon({
      className: "venue-pin venue-pin--" + kind,
      html: "<span></span>",
      iconSize: [28, 28],
      iconAnchor: [14, 14]
    });
  }

  function baseMap(el, center, zoom) {
    var map = L.map(el, { scrollWheelZoom: false }).setView(center, zoom);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri'
    }).addTo(map);


    return map;
  }

  /* ---- jarak rute dari lokasi pengguna ----
     Lokasi tidak dikirim ke server Django kita. Untuk menghitung rute, koordinat pengguna dan
     venue dikirim dari browser ke routing.openstreetmap.de (OSRM). Bila gagal, jarak garis lurus
     tetap ditampilkan. */

  function getMode() {
    var mode = null;
    try { mode = sessionStorage.getItem(MODE_KEY); } catch (e) { mode = null; }
    return MODES[mode] ? mode : "foot";
  }

  function setMode(mode) {
    try { sessionStorage.setItem(MODE_KEY, mode); } catch (e) { /* abaikan */ }
  }

  function fmtMin(min) {
    if (min < 60) return min + " mnt";
    var h = Math.floor(min / 60), m = min % 60;
    return h + " j" + (m ? " " + m + " mnt" : "");
  }

  function coordPair(p) { return p.lng.toFixed(6) + "," + p.lat.toFixed(6); }

  function cacheLoad() {
    try { return JSON.parse(sessionStorage.getItem(ROUTE_KEY)) || {}; } catch (e) { return {}; }
  }

  function cacheSave(cache) {
    try { sessionStorage.setItem(ROUTE_KEY, JSON.stringify(cache)); } catch (e) { /* abaikan */ }
  }

  function cacheKey(mode, origin, point) {
    return [mode, origin.lat.toFixed(4), origin.lng.toFixed(4), point.lat.toFixed(6), point.lng.toFixed(6)].join("|");
  }

  function getJson(url) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 8000);
    return fetch(url, { headers: { Accept: "application/json" }, signal: controller.signal })
      .then(function (response) {
        if (!response.ok) throw new Error("HTTP " + response.status);
        return response.json();
      })
      .then(function (data) {
        if (data.code !== "Ok") throw new Error(data.code || "routing");
        return data;
      })
      .then(function (data) { clearTimeout(timer); return data; },
            function (err) { clearTimeout(timer); throw err; });
  }

  function toResult(meters, seconds) {
    if (typeof meters !== "number" || typeof seconds !== "number") return null;
    return { km: meters / 1000, min: Math.max(1, Math.round(seconds / 60)) };
  }

  /* Satu permintaan untuk banyak venue (daftar). */
  function fetchTable(origin, points, mode) {
    var coords = [origin].concat(points).map(coordPair).join(";");
    var url = ROUTING_BASE + MODES[mode].path + "/table/v1/driving/" + coords +
      "?sources=0&annotations=duration,distance";
    return getJson(url).then(function (data) {
      return points.map(function (_, i) {
        return toResult(data.distances[0][i + 1], data.durations[0][i + 1]);
      });
    });
  }

  /* Satu rute; dengan garis rute bila geometry true (detail). */
  function fetchRoute(origin, point, mode, geometry) {
    var url = ROUTING_BASE + MODES[mode].path + "/route/v1/driving/" +
      coordPair(origin) + ";" + coordPair(point) +
      "?overview=" + (geometry ? "full" : "false") + "&geometries=geojson";
    return getJson(url).then(function (data) {
      var route = data.routes[0];
      var result = toResult(route.distance, route.duration);
      if (result && geometry) {
        result.line = route.geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
      }
      return result;
    });
  }

  function sleep(ms) { return new Promise(function (resolve) { setTimeout(resolve, ms); }); }

  /* Cadangan bila table gagal: satu per satu, jeda >1 detik (batas 1 permintaan/detik OSM). */
  function fetchEach(origin, points, mode, job, onItem) {
    return points.reduce(function (chain, point, i) {
      return chain.then(function () {
        if (job !== state.job) return null;
        return sleep(i ? 1100 : 0)
          .then(function () { return job === state.job ? fetchRoute(origin, point, mode, false) : null; })
          .then(function (result) { if (result) onItem(i, result); })
          .catch(function () { /* venue ini tetap garis lurus */ });
      });
    }, Promise.resolve());
  }

  function showBox(box, km, min, label, mode) {
    var kmEl = box.querySelector("[data-km]");
    var asalEl = box.querySelector("[data-asal]");
    if (kmEl) kmEl.textContent = fmtKm(km) + " km";
    if (asalEl) {
      asalEl.textContent = min == null ? label : fmtMin(min) + " " + MODES[mode].label + " dari lokasimu";
    }
  }

  function setNote(text) {
    var note = document.querySelector("[data-origin-note]");
    if (note) note.textContent = text;
  }

  function syncSwitch() {
    var mode = getMode();
    document.querySelectorAll("[data-mode-switch]").forEach(function (box) {
      box.hidden = !state.origin;
      box.querySelectorAll("[data-mode-btn]").forEach(function (btn) {
        btn.setAttribute("aria-pressed", btn.dataset.modeBtn === mode ? "true" : "false");
      });
    });
  }

  function drawLine(line) {
    if (!current.map) return;
    if (current.routeLayer) current.map.removeLayer(current.routeLayer);
    current.routeLayer = L.polyline(line, { color: "#19532B", weight: 5, opacity: 0.85 }).addTo(current.map);
    current.map.fitBounds(current.routeLayer.getBounds(), { padding: [40, 40], maxZoom: 17 });
  }

  function updateRoutes() {
    var origin = state.origin;
    if (!origin) return;
    var mode = getMode();
    var job = ++state.job;
    var cache = cacheLoad();
    var detailMap = document.querySelector('#venue-map[data-mode="detail"]');
    var items = Array.prototype.map.call(document.querySelectorAll("[data-venue-lat]"), function (box) {
      return { box: box, point: { lat: parseFloat(box.dataset.venueLat), lng: parseFloat(box.dataset.venueLng) } };
    });
    var misses = [];
    var anyRoute = false;

    items.forEach(function (item) {
      var key = cacheKey(mode, origin, item.point);
      var hit = !detailMap && cache[key];
      if (hit) {
        showBox(item.box, hit.km, hit.min, "", mode);
        anyRoute = true;
      } else {
        showBox(item.box, haversine(origin.lat, origin.lng, item.point.lat, item.point.lng),
          null, "menghitung rute…", mode);
        misses.push(item);
      }
    });
    if (anyRoute && !misses.length) setNote(noteRoute(mode));
    if (!misses.length) return;

    function apply(item, result) {
      cache[cacheKey(mode, origin, item.point)] = { km: result.km, min: result.min };
      showBox(item.box, result.km, result.min, "", mode);
      cacheSave(cache);
      setNote(noteRoute(mode));
    }

    function giveUp() {
      misses.forEach(function (item) {
        var el = item.box.querySelector("[data-asal]");
        if (el && el.textContent === "menghitung rute…") el.textContent = "garis lurus dari lokasimu";
      });
      setNote("Rute belum tersedia, jadi jarak yang tampil adalah garis lurus dari lokasimu.");
    }

    if (detailMap) {
      fetchRoute(origin, misses[0].point, mode, true).then(function (result) {
        if (job !== state.job || !result) return;
        apply(misses[0], result);
        if (result.line) drawLine(result.line);
      }).catch(function () { if (job === state.job) giveUp(); });
      return;
    }

    fetchTable(origin, misses.map(function (m) { return m.point; }), mode).then(function (results) {
      if (job !== state.job) return;
      var ok = false;
      results.forEach(function (result, i) { if (result) { apply(misses[i], result); ok = true; } });
      if (!ok) giveUp();
    }).catch(function () {
      if (job !== state.job) return;
      var ok = false;
      fetchEach(origin, misses.map(function (m) { return m.point; }), mode, job, function (i, result) {
        apply(misses[i], result);
        ok = true;
      }).then(function () { if (job === state.job && !ok) giveUp(); });
    });
  }

  function noteRoute(mode) {
    return "Jarak rute " + MODES[mode].label + " dari lokasimu, dihitung OpenStreetMap (OSRM). " +
      "Koordinatmu dikirim ke layanan itu, bukan ke server kami.";
  }

  function applyOrigin(origin) {
    state.origin = origin;
    syncSwitch();
    if (current.map && !current.userMarker) {
      current.userMarker = L.marker([origin.lat, origin.lng], {
        icon: icon("akun"), title: "Lokasimu", interactive: false
      }).addTo(current.map);
    }
    updateRoutes();
  }

  function withOrigin() {
    var cached = null;
    try { cached = JSON.parse(sessionStorage.getItem(ORIGIN_KEY)); } catch (e) { cached = null; }
    if (cached && isFinite(cached.lat) && isFinite(cached.lng)) { applyOrigin(cached); return; }
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(function (pos) {
      var origin = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      try { sessionStorage.setItem(ORIGIN_KEY, JSON.stringify(origin)); } catch (e) { /* abaikan */ }
      applyOrigin(origin);
    }, function () { /* ditolak: tetap pakai jarak dari pusat kampus */ },
    { maximumAge: 600000, timeout: 8000 });
  }

  document.addEventListener("click", function (event) {
    var btn = event.target.closest && event.target.closest("[data-mode-btn]");
    if (!btn || !MODES[btn.dataset.modeBtn]) return;
    setMode(btn.dataset.modeBtn);
    syncSwitch();
    updateRoutes();
  });

  /* ---- peta daftar ---- */

  function initList(el) {
    var dataEl = document.getElementById("venue-data");
    var data = dataEl ? JSON.parse(dataEl.textContent) : [];
    if (!data.length) return;
    var map = baseMap(el, [data[0].lat, data[0].lng], 16);
    var cards = document.querySelectorAll(".venue-card[data-venue-id]");
    var bounds = [];
    current = { map: map, markers: {}, userMarker: null, routeLayer: null };

    function activate(id, scroll) {
      cards.forEach(function (card) {
        var on = card.dataset.venueId === String(id);
        card.classList.toggle("is-active", on);
        if (on && scroll) card.scrollIntoView({ block: "nearest", behavior: "smooth" });
      });
      Object.keys(current.markers).forEach(function (key) {
        var node = current.markers[key].getElement();
        if (node) node.classList.toggle("is-active", key === String(id));
      });
    }

    data.forEach(function (v) {
      var marker = L.marker([v.lat, v.lng], { icon: icon("venue"), title: v.nama + " (" + v.unit + ")", keyboard: true }).addTo(map);
      marker.on("click", function () { activate(v.id, true); });
      current.markers[v.id] = marker;
      bounds.push([v.lat, v.lng]);
    });
    if (bounds.length > 1) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 17 });
    cards.forEach(function (card) {
      card.addEventListener("mouseenter", function () { activate(card.dataset.venueId, false); });
      card.addEventListener("focusin", function () { activate(card.dataset.venueId, false); });
    });
    activate(data[0].id, false);
  }

  /* ---- peta detail ---- */

  function initDetail(el) {
    var pos = [parseFloat(el.dataset.lat), parseFloat(el.dataset.lng)];
    var map = baseMap(el, pos, 17);
    L.marker(pos, { icon: icon("aktif"), interactive: false }).addTo(map);
    current = { map: map, markers: {}, userMarker: null, routeLayer: null };
  }

  /* ---- form: pratinjau peta dan pencarian alamat ---- */

  function initForm(el) {
    var lat = document.getElementById("id_latitude");
    var lng = document.getElementById("id_longitude");
    var nama = document.getElementById("id_nama");
    var alamat = document.getElementById("id_alamat");
    var cari = document.getElementById("alamat-cari");
    var box = document.getElementById("hasil-alamat");
    var status = document.getElementById("alamat-status");
    var map = baseMap(el, [-6.365, 106.828], 15);
    var marker = null;
    var timer = null;
    var controller = null;
    current = { map: null, markers: {}, userMarker: null, routeLayer: null };

    function coords() {
      var la = parseFloat((lat.value || "").replace(",", "."));
      var lo = parseFloat((lng.value || "").replace(",", "."));
      if (isFinite(la) && isFinite(lo) && Math.abs(la) <= 90 && Math.abs(lo) <= 180) return [la, lo];
      return null;
    }

    function sync() {
      var c = coords();
      if (!c) return;
      if (marker) marker.setLatLng(c); else marker = L.marker(c, { icon: icon("aktif"), interactive: false }).addTo(map);
      map.setView(c, Math.max(map.getZoom(), 17));
    }

    lat.addEventListener("change", sync);
    lng.addEventListener("change", sync);
    map.on("click", function (e) {
      lat.value = e.latlng.lat.toFixed(6);
      lng.value = e.latlng.lng.toFixed(6);
      alamat.value = "";
      sync();
    });
    sync();

    function render(items) {
      box.innerHTML = "";
      if (!items.length) {
        status.textContent = "Alamat tidak ditemukan. Coba kata kunci lain atau isi koordinat manual.";
        box.hidden = true;
        return;
      }
      status.textContent = "Hasil dari OpenStreetMap.";
      items.forEach(function (item) {
        var button = document.createElement("button");
        var title = document.createElement("strong");
        var sub = document.createElement("span");
        button.type = "button";
        button.className = "venue-result";
        title.textContent = item.judul;
        sub.textContent = item.subjudul;
        button.appendChild(title);
        button.appendChild(sub);
        button.addEventListener("click", function () {
          lat.value = item.lat;
          lng.value = item.lng;
          alamat.value = item.alamat;
          if (!nama.value.trim()) nama.value = item.judul;
          box.hidden = true;
          status.textContent = "Dipilih: " + item.judul;
          sync();
        });
        box.appendChild(button);
      });
      box.hidden = false;
    }

    function search(q) {
      if (controller) controller.abort();
      controller = new AbortController();
      status.textContent = "Mencari…";
      fetch(cari.dataset.searchUrl + "?q=" + encodeURIComponent(q), {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        signal: controller.signal
      }).then(function (response) {
        return response.json().then(function (body) { return { ok: response.ok, body: body }; });
      }).then(function (result) {
        if (!result.ok) {
          status.textContent = result.body.message || "Pencarian gagal. Isi koordinat secara manual.";
          box.hidden = true;
          return;
        }
        render(result.body.hasil);
      }).catch(function (error) {
        if (error.name !== "AbortError") status.textContent = "Pencarian gagal. Isi koordinat secara manual.";
      });
    }

    cari.addEventListener("input", function () {
      clearTimeout(timer);
      var q = cari.value.trim();
      if (q.length < 3) {
        box.hidden = true;
        status.textContent = "Ketik nama gedung atau alamat di kampus.";
        return;
      }
      timer = setTimeout(function () { search(q); }, 600); /* Nominatim: maksimal 1 permintaan per detik */
    });
    cari.addEventListener("keydown", function (event) {
      if (event.key === "Enter") event.preventDefault();
    });
  }

  function init() {
    var el = document.getElementById("venue-map");
    if (el && !el.dataset.venueReady) {
      el.dataset.venueReady = "1";
      if (typeof L === "undefined") {
        el.textContent = "Peta tidak dapat dimuat. Periksa koneksi internet.";
      } else if (el.dataset.mode === "list") {
        initList(el);
      } else if (el.dataset.mode === "detail") {
        initDetail(el);
      } else if (el.dataset.mode === "form") {
        initForm(el);
      }
    }
    if (document.querySelector("[data-venue-lat]")) withOrigin();
  }

  document.addEventListener("DOMContentLoaded", init);
  document.addEventListener("htmx:afterSettle", init);
})();
