"""Seed donasi utama (>= 50 baris data utama saat deploy — syarat spesifikasi).

Donasi butuh `donor` (FK ke user dari seed profil), `lokasi` (nama venue dari
seed venue), dan waktu tersedia/akhir pengambilan sekitar "sekarang" supaya
status live saat dibaca. `waktu_tersedia` dihitung dari `timezone.now()` saat
migration dijalankan — wajar untuk data demo yang selalu terlihat aktif.

Idempotent: kunci `donor + nama`, jadi dijalankan berulang tetap 1 set.
"""
from datetime import timedelta

from django.db import migrations
from django.utils import timezone

# (username donor, nama makanan, porsi, nama venue, catatan)
DONASI = [
    ("kantin_fasilkom", "Nasi Ayam Geprek", 40, "Fasilkom UI", "Disingkat stok kantin sore."),
    ("kantin_fasilkom", "Nasi Rendang", 25, "Fasilkom UI", ""),
    ("kantin_fasilkom", "Bakso Kuah", 18, "Fasilkom UI", "Pedas sedang."),
    ("kantin_fasilkom", "Soto Ayam", 22, "Fasilkom UI", ""),
    ("panitia_wisuda", "Nasi Kuning Paket", 60, "Balairung UI", "Sisa persiapan gladi resik."),
    ("panitia_wisuda", "Risoles Mayo", 35, "Balairung UI", "Masih hangat."),
    ("panitia_wisuda", "Bolu Pandan", 20, "Balairung UI", ""),
    ("bem_feb", "Nasi Kotak Ayam Teriyaki", 45, "FEB UI", "Sisa rapat senat mahasiswa."),
    ("bem_feb", "Tahu Tempe Bacem", 30, "FEB UI", ""),
    ("bem_feb", "Uduk Ayam", 26, "FEB UI", "Perlu pemanasan."),
    ("kantin_ft", "Mie Ayam Jumbo", 38, "FT UI", "Penutup kantin."),
    ("kantin_ft", "Nasi Telur Balado", 27, "FT UI", ""),
    ("kantin_ft", "Gado-gado", 15, "FT UI", "Vegetarian."),
    ("kantin_ft", "Lontong Sayur", 20, "FT UI", ""),
    ("himpunan_fmipa", "Pizza Mini Sisa Seminar", 24, "FMIPA UI", "Sisa seminar data science."),
    ("himpunan_fmipa", "Donat Gula", 30, "FMIPA UI", ""),
    ("himpunan_fmipa", "Sandwich Sayur", 16, "FMIPA UI", ""),
    ("katering_makmur", "Nasi Campur Bungkus", 50, "FT UI", "Ujung hari katering."),
    ("katering_makmur", "Sayur Sop Bungkus", 34, "FT UI", ""),
    ("katering_makmur", "Pecel Sayur", 28, "FT UI", "Bumbu kacang terpisah."),
    ("kantin_fk", "Nasi Ikan Bakar", 22, "FK UI", "Sisa kantin pagi."),
    ("kantin_fk", "Ramen Ayam", 14, "FK UI", "Sisa lunch event."),
    ("kantin_fk", "Kwetiau Goreng", 18, "FK UI", ""),
    ("panitia_makrab", "Paket Makrab Sore", 32, "FMIPA UI", "Sisa makrab mahasiswa baru."),
    ("panitia_makrab", "Roti Tawar Selai", 26, "FMIPA UI", "Untuk sarapan."),
    ("panitia_makrab", "Buah Potong", 20, "FMIPA UI", "Fresh, segera diambil."),
    ("ukm_trapesium", "Sisfo Snack Box", 15, "FMIPA UI", "Sisa acara UKM."),
    ("ukm_trapesium", "Kopi dan Croissant", 18, "FMIPA UI", "Bawaan sponsorship."),
    ("ukm_trapesium", "Onigiri Mini", 12, "FMIPA UI", ""),
    ("katering_santai", "Nasi Uduk Komplit", 44, "FEB UI", "Sisa malam katering."),
    ("katering_santai", "Telur Dadar Potong", 22, "FEB UI", ""),
    ("katering_santai", "Kue Tradisional Aneka", 30, "FEB UI", "Kue basah, hari ini."),
    ("katering_santai", "Nasi Uduk Komplit", 44, "FT UI", "Ujung hari katering."),
    ("katering_santai", "Sayur Sop Bungkus", 30, "FT UI", ""),
    ("katering_santai", "Ayam Bakar Bungkus", 22, "FEB UI", ""),
    ("kantin_fasilkom", "Nasi Telur Dadar", 30, "Fasilkom UI", "Stok terakhir."),
    ("kantin_fasilkom", "Capcay Sayur", 20, "Fasilkom UI", ""),
    ("kantin_fasilkom", "Bubur Ayam", 26, "Fasilkom UI", ""),
    ("panitia_wisuda", "Pisang Goreng", 40, "Balairung UI", "Sisa pemberkasan."),
    ("panitia_wisuda", "Perkedel Kentang", 28, "Balairung UI", ""),
    ("panitia_wisuda", "Es Teh Kotak", 55, "Balairung UI", "Masih dingin."),
    ("bem_feb", "Nasi Empal", 32, "FEB UI", "Sisa buka bersama."),
    ("bem_feb", "Bakwan Jagung", 24, "FEB UI", ""),
    ("bem_feb", "Kue Cubit", 36, "FEB UI", ""),
    ("kantin_ft", "Nasi Pecel", 29, "FT UI", "Penutup kantin."),
    ("kantin_ft", "Ketoprak", 21, "FT UI", ""),
    ("kantin_ft", "Nasi Campur Sapi", 17, "FT UI", ""),
    ("himpunan_fmipa", "Roti Isi", 27, "FMIPA UI", "Sisa acara ormat."),
    ("himpunan_fmipa", "Kue Lapis", 33, "FMIPA UI", ""),
    ("himpunan_fmipa", "Sate Ayam Bungkus", 19, "FMIPA UI", ""),
    ("kantin_fk", "Nasi Gurame", 14, "FK UI", "Menu spesial sisa."),
    ("kantin_fk", "Sayur Asem", 23, "FK UI", ""),
    ("panitia_makrab", "Paket Nasi Goreng", 38, "FIB UI", "Sisa makrab."),
    ("panitia_makrab", "Areni Cokelat", 31, "FIB UI", ""),
    ("ukm_trapesium", "Nasi Rames", 25, "FMIPA UI", "Sisa lomba."),
    ("ukm_trapesium", "Cilok Bumbu", 29, "FMIPA UI", ""),
]


def seed(apps, schema_editor):
    # Seed hanya jalan di deployment nyata (env var di-set di PWS Environs).
    # Di test dan lokal, env var tidak ada supaya suite modul teman tetap
    # mengasumsikan database kosong.
    import os

    if not os.environ.get("MBG_SEED_DEMO"):
        return

    user_model = apps.get_model("auth", "User")
    donasi_model = apps.get_model("donasi", "Donasi")
    now = timezone.now()
    for username, nama, porsi, lokasi, catatan in DONASI:
        user = user_model.objects.filter(username=username).first()
        if user is None:
            continue  # Seed profil (0003) belum jalan — jangan buat donasi yatim.
        donasi_model.objects.get_or_create(
            donor=user,
            nama=nama,
            defaults={
                "jumlah_porsi": porsi,
                "lokasi": lokasi,
                "waktu_tersedia": now - timedelta(hours=1),
                "waktu_akhir_pengambilan": now + timedelta(hours=10),
                "catatan": catatan,
            },
        )


def unseed(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    donasi_model = apps.get_model("donasi", "Donasi")
    donasi_model.objects.filter(
        donor__username__in=[d[0] for d in DONASI],
        nama__in=[d[1] for d in DONASI],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("donasi", "0003_pickup_end_and_automatic_stock_status"),
        ("profil", "0003_seed_profil"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
