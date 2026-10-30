"""Seed venue: titik pengambilan makanan di kampus UI Depok.

Koordinat dan alamat nyata di sekitar kampus (dari data OpenStreetMap yang
dipakai modul Venue) supaya peta dan pilihan lokasi punya isi sejak deploy.
Idempotent lewat `get_or_create` berdasarkan nama venue.
"""
from django.db import migrations

VENUE = [
    # nama, fakultas, alamat, lat, lng, deskripsi akses
    ("Fasilkom UI", "fasilkom",
     "Fakultas Ilmu Komputer, Universitas Indonesia, Depok",
     -6.361900, 106.824300,
     "Gerbang utama gedung, sebelah ruang baca perpustakaan."),
    ("Balairung UI", "kampus",
     "Balairung Universitas Indonesia, Depok",
     -6.361500, 106.832600,
     "Lantai dasar, samping sekretariat panitia."),
    ("FEB UI", "feb",
     "Fakultas Ekonomi dan Bisnis, Universitas Indonesia, Depok",
     -6.359000, 106.831000,
     "Lobby A, dekat pos satpam."),
    ("FT UI", "ft",
     "Fakultas Teknik, Universitas Indonesia, Depok",
     -6.363600, 106.827600,
     "Serum kampus, dekat kantin pusat."),
    ("FMIPA UI", "fmipa",
     "Fakultas Matematika dan Ilmu Pengetahuan Alam, Universitas Indonesia, Depok",
     -6.358200, 106.833600,
     "Gedung C lantai 1, samping sekre himpunan."),
    ("FK UI", "fk",
     "Fakultas Kedokteran, Universitas Indonesia, Depok",
     -6.348000, 106.827000,
     "Lobby utama, dekat informasi."),
]


def seed(apps, schema_editor):
    # Seed hanya jalan di deployment nyata (env var di-set di PWS Environs).
    # Di test dan lokal, env var tidak ada supaya suite modul teman tetap
    # mengasumsikan database kosong.
    import os

    if not os.environ.get("MBG_SEED_DEMO"):
        return

    venue_model = apps.get_model("venue", "Venue")
    for nama, fakultas, alamat, lat, lng, akses in VENUE:
        venue_model.objects.get_or_create(
            nama=nama, fakultas=fakultas,
            defaults={
                "fakultas": fakultas,
                "alamat": alamat,
                "latitude": lat,
                "longitude": lng,
                "deskripsi_akses": akses,
            },
        )


def unseed(apps, schema_editor):
    venue_model = apps.get_model("venue", "Venue")
    venue_model.objects.filter(nama__in=[v[0] for v in VENUE]).delete()


class Migration(migrations.Migration):
    dependencies = [("venue", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
