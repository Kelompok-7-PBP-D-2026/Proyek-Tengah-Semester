"""Klien kecil untuk Nominatim (pencarian alamat OpenStreetMap).

Kebijakan penggunaan Nominatim: maksimal 1 permintaan per detik, wajib User-Agent
yang jelas, dan hasil sebaiknya di-cache. Frontend menunda pencarian (debounce) dan
hasil di-cache di sini.
"""
import hashlib

import requests
from django.core.cache import cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = (
    "MBG-PTS-Kelompok7/1.0 "
    "(+https://github.com/Kelompok-7-PBP-D-2026/Proyek-Tengah-Semester)"
)
# Kotak pencarian di sekitar kampus UI Depok: kiri, atas, kanan, bawah (lon, lat).
VIEWBOX = "106.78,-6.32,106.87,-6.42"
CACHE_SECONDS = 60 * 60


class OSMError(Exception):
    """Pencarian alamat OpenStreetMap gagal."""


def _parse(item):
    display = item.get("display_name", "")
    segments = [s.strip() for s in display.split(",") if s.strip()]
    judul = item.get("name") or (segments[0] if segments else "Tanpa nama")
    rest = segments[1:4] if segments and segments[0] == judul else segments[:3]
    return {
        "judul": judul,
        "subjudul": ", ".join(rest),
        "alamat": display[:255],
        "lat": round(float(item["lat"]), 6),
        "lng": round(float(item["lon"]), 6),
    }


def cari_alamat(query, limit=5):
    query = query.strip()[:150]
    key = "venue:osm:" + hashlib.sha1(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        response = requests.get(
            NOMINATIM_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "countrycodes": "id",
                "viewbox": VIEWBOX,
            },
            headers={"User-Agent": USER_AGENT, "Accept-Language": "id"},
            timeout=5,
        )
        response.raise_for_status()
        hasil = [_parse(item) for item in response.json()]
    except (requests.RequestException, ValueError, KeyError) as exc:
        raise OSMError(str(exc)) from exc
    cache.set(key, hasil, CACHE_SECONDS)
    return hasil
