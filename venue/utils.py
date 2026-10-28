from math import asin, cos, radians, sin, sqrt

# Titik acuan jarak bila pengguna tidak membagikan lokasinya (perkiraan pusat kampus UI Depok).
CAMPUS_CENTER = (-6.3650, 106.8280)
EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1, lon1, lat2, lon2):
    """Jarak garis lurus antara dua koordinat, dalam kilometer."""
    lat1, lon1, lat2, lon2 = (radians(float(v)) for v in (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def format_km(km):
    """0.84 -> '0,8' (pemisah desimal koma, satu angka di belakang koma)."""
    return f"{float(km):.1f}".replace(".", ",")


def origin_from_request(request):
    """Titik asal jarak: ?lat=&lng= bila valid, selain itu pusat kampus.

    Mengembalikan (lat, lng, dari_pengguna).
    """
    try:
        lat = float(request.GET.get("lat", ""))
        lng = float(request.GET.get("lng", ""))
    except ValueError:
        return (*CAMPUS_CENTER, False)
    if -90 <= lat <= 90 and -180 <= lng <= 180:
        return lat, lng, True
    return (*CAMPUS_CENTER, False)
