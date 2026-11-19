"""Perhitungan jarak antar koordinat untuk filter radius daftar donor.

Data koordinat datang dari OpenStreetMap (klien di `venue.osm`, modul Venue).
Modul ini hanya menghitung: berapa donor yang jaraknya <= radius dari titik
acuan pengguna. Rumusnya haversine — cukup akurat untuk jarak antar kampus,
dan tidak butuh PostGIS karena semua dihitung di Python setelah query dasar.
"""
import math

RATA_RATA_BUMI_KM = 6371.0


def jarak_km(lat1, lng1, lat2, lng2):
    """Jarak antara dua titik koordinat dalam kilometer (rumus haversine)."""
    dlat = math.radians(float(lat2) - float(lat1))
    dlng = math.radians(float(lng2) - float(lng1))
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(float(lat1)))
        * math.cos(math.radians(float(lat2)))
        * math.sin(dlng / 2) ** 2
    )
    return RATA_RATA_BUMI_KM * 2 * math.asin(math.sqrt(a))


def filter_radius(donor_qs, lat, lng, radius_km):
    """Saring queryset donor: hanya yang koordinatnya dalam radius titik (lat, lng).

    Donor tanpa koordinat dianggap tidak relevan untuk pencarian berbasis
    jarak, jadi dikeluarkan dari hasil.
    """
    radius = float(radius_km)
    hasil = []
    for donor in donor_qs:
        if donor.latitude is None or donor.longitude is None:
            continue
        if jarak_km(lat, lng, donor.latitude, donor.longitude) <= radius:
            hasil.append(donor.pk)
    return donor_qs.filter(pk__in=hasil)
