/* Route distance from the viewer to the pickup venue (vanilla JS).
   The viewer picks a travel mode in a dropdown; until then the distance reads
   "Pilih moda". The viewer's position comes from the browser's Geolocation API
   and is read on every page load (the campus center is used when it is not
   available). The route is computed by the OpenStreetMap OSRM service, the same
   one the venue module uses, so the viewer's and the venue's coordinates are
   sent to it. If routing fails, a straight-line distance is shown instead. */
(function () {
    "use strict";

    function toArray(list) {
        return Array.prototype.slice.call(list);
    }

    var valueTargets = toArray(document.querySelectorAll("[data-distance-value]"));
    var inlineTargets = toArray(document.querySelectorAll("[data-distance-inline]"));
    var selects = toArray(document.querySelectorAll("[data-distance-select]"));
    if (!valueTargets.length && !inlineTargets.length) {
        return;
    }

    var ROUTING_BASE = "https://routing.openstreetmap.de/";
    var MODES = {
        foot: { service: "routed-foot" },
        bike: { service: "routed-bike" },
        car: { service: "routed-car" },
    };
    var REMEMBER_MODE = true; // set to false to always start at "Pilih moda"
    var MODE_KEY = "klaim.distance.mode";
    var CACHE_PREFIX = "klaim.route.";
    var CACHE_TTL_MS = 5 * 60 * 1000;
    var REQUEST_TIMEOUT_MS = 8000;
    var EARTH_RADIUS_KM = 6371.0088;

    var mode = null; // "foot" | "bike" | "car" | null (not chosen yet)
    var viewer = null; // null = still locating, false = unavailable, object = {lat, lng, fromUser}
    var renderToken = 0;

    // ---- sessionStorage helpers (may be blocked by the browser) ---------
    function storageGet(key) {
        try {
            return window.sessionStorage.getItem(key);
        } catch (error) {
            return null;
        }
    }

    function storageSet(key, value) {
        try {
            window.sessionStorage.setItem(key, value);
        } catch (error) {
            /* ignore */
        }
    }

    // ---- formatting and math --------------------------------------------
    function toRadians(degrees) {
        return (degrees * Math.PI) / 180;
    }

    function haversineKm(lat1, lng1, lat2, lng2) {
        var dLat = toRadians(lat2 - lat1);
        var dLng = toRadians(lng2 - lng1);
        var a =
            Math.pow(Math.sin(dLat / 2), 2) +
            Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) * Math.pow(Math.sin(dLng / 2), 2);
        return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(a));
    }

    function formatKm(km) {
        return km.toFixed(1).replace(".", ",") + " km";
    }

    function formatDuration(seconds) {
        var minutes = Math.max(1, Math.round(seconds / 60));
        if (minutes < 60) {
            return minutes + " menit";
        }
        var hours = Math.floor(minutes / 60);
        var rest = minutes % 60;
        return hours + " jam" + (rest ? " " + rest + " menit" : "");
    }

    // ---- group targets by venue so one route serves every element -------
    var groups = (function () {
        var byKey = {};

        function add(target, kind) {
            var lat = parseFloat(target.getAttribute("data-lat"));
            var lng = parseFloat(target.getAttribute("data-lng"));
            if (isNaN(lat) || isNaN(lng)) {
                return;
            }
            var key = lat.toFixed(6) + "," + lng.toFixed(6);
            if (!byKey[key]) {
                byKey[key] = { lat: lat, lng: lng, values: [], inlines: [] };
            }
            byKey[key][kind].push(target);
        }

        valueTargets.forEach(function (target) {
            add(target, "values");
        });
        inlineTargets.forEach(function (target) {
            add(target, "inlines");
        });
        return Object.keys(byKey).map(function (key) {
            return byKey[key];
        });
    })();

    // Campus center sent by the server, used when the browser gives no position.
    function readCampus() {
        var all = valueTargets.concat(inlineTargets);
        for (var i = 0; i < all.length; i += 1) {
            var lat = parseFloat(all[i].getAttribute("data-origin-lat"));
            var lng = parseFloat(all[i].getAttribute("data-origin-lng"));
            if (!isNaN(lat) && !isNaN(lng)) {
                return { lat: lat, lng: lng, fromUser: false };
            }
        }
        return null;
    }

    // ---- rendering --------------------------------------------------------
    function setNote(target, text) {
        var note = target.parentNode ? target.parentNode.querySelector("[data-distance-note]") : null;
        if (!note) {
            return;
        }
        note.textContent = text || "";
        note.hidden = !text;
    }

    function noteText(routed) {
        if (!viewer || !viewer.fromUser) {
            return "Perkiraan dari pusat kampus. Izinkan lokasi untuk jarak dari posisimu.";
        }
        if (!routed) {
            return "Rute belum tersedia, ditampilkan garis lurus dari lokasimu.";
        }
        return "Rute dihitung lewat OpenStreetMap dari lokasimu.";
    }

    function showMessage(text) {
        valueTargets.forEach(function (target) {
            target.textContent = text;
            setNote(target, "");
        });
        inlineTargets.forEach(function (target) {
            target.hidden = true;
        });
    }

    function showResult(group, km, seconds, routed) {
        group.values.forEach(function (target) {
            target.textContent = "";
            var strong = document.createElement("strong");
            strong.textContent = formatKm(km);
            target.appendChild(strong);
            target.appendChild(
                document.createTextNode(" (" + (routed ? formatDuration(seconds) : "garis lurus") + ")")
            );
            setNote(target, noteText(routed));
        });
        group.inlines.forEach(function (target) {
            var text = target.querySelector("[data-distance-inline-text]");
            if (text) {
                text.textContent = formatKm(km);
            }
            target.hidden = false;
        });
    }

    // ---- routing ----------------------------------------------------------
    function readCache(key) {
        var raw = storageGet(key);
        if (!raw) {
            return null;
        }
        try {
            var entry = JSON.parse(raw);
            if (entry && Date.now() - entry.at < CACHE_TTL_MS) {
                return entry;
            }
        } catch (error) {
            /* ignore a corrupt entry */
        }
        return null;
    }

    function fetchRoute(routeMode, destination) {
        var key =
            CACHE_PREFIX + routeMode + "." +
            viewer.lat.toFixed(3) + "," + viewer.lng.toFixed(3) + "." +
            destination.lat.toFixed(6) + "," + destination.lng.toFixed(6);
        var cached = readCache(key);
        if (cached) {
            return Promise.resolve({ km: cached.km, seconds: cached.seconds });
        }

        // The OSRM demo server uses "driving" in the path for every profile;
        // the profile itself is chosen by the host prefix (routed-foot, ...).
        var url =
            ROUTING_BASE + MODES[routeMode].service + "/route/v1/driving/" +
            viewer.lng.toFixed(6) + "," + viewer.lat.toFixed(6) + ";" +
            destination.lng.toFixed(6) + "," + destination.lat.toFixed(6) +
            "?overview=false";

        var controller = typeof AbortController === "function" ? new AbortController() : null;
        var timer = controller
            ? window.setTimeout(function () {
                  controller.abort();
              }, REQUEST_TIMEOUT_MS)
            : null;

        return fetch(url, controller ? { signal: controller.signal } : {})
            .then(function (response) {
                if (!response.ok) {
                    throw new Error("routing http " + response.status);
                }
                return response.json();
            })
            .then(function (data) {
                if (data.code !== "Ok" || !data.routes || !data.routes.length) {
                    throw new Error("no route");
                }
                var result = { km: data.routes[0].distance / 1000, seconds: data.routes[0].duration };
                storageSet(
                    key,
                    JSON.stringify({ km: result.km, seconds: result.seconds, at: Date.now() })
                );
                return result;
            })
            .finally(function () {
                if (timer) {
                    window.clearTimeout(timer);
                }
            });
    }

    function renderAll() {
        var token = ++renderToken;
        if (!mode) {
            showMessage("Pilih moda");
            return;
        }
        if (viewer === false) {
            showMessage("Lokasi tidak tersedia");
            return;
        }
        showMessage("Menghitung...");
        if (viewer === null) {
            return; // renderAll runs again as soon as the position is known
        }

        var activeMode = mode;
        // One request at a time: the routing service allows about 1 request per second.
        groups.reduce(function (chain, group) {
            return chain.then(function () {
                if (token !== renderToken) {
                    return null;
                }
                return fetchRoute(activeMode, group)
                    .then(function (result) {
                        if (token === renderToken) {
                            showResult(group, result.km, result.seconds, true);
                        }
                    })
                    .catch(function () {
                        if (token === renderToken) {
                            var km = haversineKm(viewer.lat, viewer.lng, group.lat, group.lng);
                            showResult(group, km, 0, false);
                        }
                    });
            });
        }, Promise.resolve());
    }

    // ---- mode dropdown ----------------------------------------------------
    function syncSelects() {
        selects.forEach(function (select) {
            select.value = mode || "";
        });
    }

    selects.forEach(function (select) {
        select.addEventListener("change", function () {
            mode = MODES[select.value] ? select.value : null;
            if (REMEMBER_MODE) {
                storageSet(MODE_KEY, mode || "");
            }
            syncSelects();
            renderAll();
        });
    });

    if (REMEMBER_MODE) {
        var stored = storageGet(MODE_KEY);
        if (MODES[stored]) {
            mode = stored;
        }
    }
    syncSelects();
    renderAll();

    // ---- geolocation (read on every page load) -----------------------------
    function useCampusOrigin() {
        viewer = readCampus() || false;
        renderAll();
    }

    if (!navigator.geolocation) {
        useCampusOrigin();
    } else {
        navigator.geolocation.getCurrentPosition(
            function (result) {
                viewer = { lat: result.coords.latitude, lng: result.coords.longitude, fromUser: true };
                renderAll();
            },
            useCampusOrigin,
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
        );
    }
})();