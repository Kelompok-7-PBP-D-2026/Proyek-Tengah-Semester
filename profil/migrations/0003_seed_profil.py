"""Seed profil donor dan penerima untuk deployment.

Data ini prasyarat seeding modul lain: `Donasi.donor` dan `Claim.recipient`
menunjuk user yang dibuat di sini. Semua `get_or_create` dengan kunci unik
(username / nim / nama_unit), jadi migration aman dijalankan berulang.

Koordinat memakai titik-titik sekitar kampus UI Depok supaya filter radius
(?radius=) langsung punya data untuk didemokan.
"""
from django.db import migrations

DONOR = [
    # username, nama_unit, jenis, kontak, alamat, lat, lng
    ("kantin_fasilkom", "Kantin Fasilkom", "kantin", "0812-1000-0001",
     "Fakultas Ilmu Komputer, Universitas Indonesia, Depok", -6.361900, 106.824300),
    ("panitia_wisuda", "Panitia Wisuda 2026", "panitia_acara", "0812-1000-0002",
     "Balairung Universitas Indonesia, Depok", -6.361500, 106.832600),
    ("bem_feb", "BEM Fakultas Ekonomi", "himpunan", "0812-1000-0003",
     "Fakultas Ekonomi dan Bisnis, Universitas Indonesia, Depok", -6.359000, 106.831000),
    ("kantin_ft", "Kantin Teknik", "kantin", "0812-1000-0004",
     "Fakultas Teknik, Universitas Indonesia, Depok", -6.363600, 106.827600),
    ("himpunan_fmipa", "Himpunan Matematika FMIPA", "himpunan", "0812-1000-0005",
     "Fakultas MIPA, Universitas Indonesia, Depok", -6.358200, 106.833600),
    ("katering_makmur", "Katering Makmur", "katering", "0812-1000-0006",
     "Jalan Margonda Raya, Depok", -6.390000, 106.823000),
    ("kantin_fk", "Kantin Kedokteran", "kantin", "0812-1000-0007",
     "Fakultas Kedokteran, Universitas Indonesia, Depok", -6.348000, 106.827000),
    ("panitia_makrab", "Panitia Makrab FIB", "panitia_acara", "0812-1000-0008",
     "Fakultas Ilmu Pengetahuan Budaya, Universitas Indonesia, Depok", -6.357000, 106.832000),
    ("ukm_trapesium", "UKM Trapesium FMIPA", "himpunan", "0812-1000-0009",
     "Fakultas MIPA, Universitas Indonesia, Depok", -6.358200, 106.833600),
    ("katering_santai", "Katering Santai Margonda", "katering", "0812-1000-0010",
     "Jalan Margonda Raya 50, Depok", -6.385000, 106.822000),
]

PENERIMA = [
    # username, nama, nim, fakultas, kontak
    ("riki_mhs", "Riki Pratama", "2506100001", "fasilkom", "0813-2000-0001"),
    ("sara_mhs", "Sara Amelia", "2506100002", "feb", "0813-2000-0002"),
    ("dedi_mhs", "Dedi Kurniawan", "2506100003", "ft", "0813-2000-0003"),
    ("maya_mhs", "Maya Putri", "2506100004", "fmipa", "0813-2000-0004"),
    ("bimo_mhs", "Bimo Saputra", "2506100005", "fh", "0813-2000-0005"),
    ("cahya_mhs", "Cahya Wijaya", "2506100006", "fk", "0813-2000-0006"),
    ("nina_mhs", "Nina Ramadhani", "2506100007", "fisip", "0813-2000-0007"),
    ("agus_mhs", "Agus Setiawan", "2506100008", "fib", "0813-2000-0008"),
    ("lia_mhs", "Lia Halimah", "2506100009", "fpsi", "0813-2000-0009"),
    ("tomi_mhs", "Tomi Hartanto", "2506100010", "vokasi", "0813-2000-0010"),
]


def seed(apps, schema_editor):
    # Seed hanya jalan di deployment nyata (env var di-set di PWS Environs).
    # Di test dan lokal, env var tidak ada supaya suite modul teman tetap
    # mengasumsikan database kosong.
    import os

    if not os.environ.get("MBG_SEED_DEMO"):
        return

    user_model = apps.get_model("auth", "User")
    donor_model = apps.get_model("profil", "ProfilDonor")
    penerima_model = apps.get_model("profil", "ProfilPenerima")

    for username, nama_unit, jenis, kontak, alamat, lat, lng in DONOR:
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@ui.ac.id"},
        )
        donor_model.objects.get_or_create(
            user=user,
            defaults={
                "nama_unit": nama_unit,
                "jenis": jenis,
                "kontak": kontak,
                "alamat": alamat,
                "latitude": lat,
                "longitude": lng,
            },
        )

    for username, nama, nim, fakultas, kontak in PENERIMA:
        user, _ = user_model.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@ui.ac.id"},
        )
        penerima_model.objects.get_or_create(
            user=user,
            defaults={"nama_lengkap": nama, "nim": nim, "fakultas": fakultas, "kontak": kontak},
        )


def unseed(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    user_model.objects.filter(
        username__in=[baris[0] for baris in DONOR + PENERIMA]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("profil", "0002_profildonor_alamat_profildonor_latitude_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
