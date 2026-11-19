"""Seed klaim untuk data laporan: beberapa donasi sudah diklaim/diambil.

Klaim men-snapshot data donasi (donation_id, nama, donor, lokasi, deadline),
jadi seed ini membuat klaim yang menunjuk donasi dari seed donasi 0004.
Status: sebagian `picked_up` (sudah diambil) dan sisanya `pending` — kombinasi
yang membuat angka laporan modul Joshua tidak nol.

Idempotent: kunci `recipient + donation_id + food_name`.
"""
from datetime import timedelta

from django.db import migrations
from django.utils import timezone

# (username penerima, username donor, nama makanan, porsi, status)
KLAIM = [
    ("riki_mhs", "kantin_fasilkom", "Nasi Ayam Geprek", 2, "picked_up"),
    ("sara_mhs", "panitia_wisuda", "Nasi Kuning Paket", 3, "picked_up"),
    ("dedi_mhs", "bem_feb", "Nasi Kotak Ayam Teriyaki", 2, "picked_up"),
    ("maya_mhs", "kantin_ft", "Mie Ayam Jumbo", 1, "picked_up"),
    ("bimo_mhs", "himpunan_fmipa", "Pizza Mini Sisa Seminar", 2, "picked_up"),
    ("cahya_mhs", "katering_makmur", "Nasi Campur Bungkus", 3, "pending"),
    ("nina_mhs", "kantin_fk", "Nasi Ikan Bakar", 2, "pending"),
    ("agus_mhs", "katering_santai", "Nasi Uduk Komplit", 3, "pending"),
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
    klaim_model = apps.get_model("klaim", "Claim")
    now = timezone.now()
    for i, (username_penerima, username_donor, nama, porsi, status) in enumerate(KLAIM):
        penerima = user_model.objects.filter(username=username_penerima).first()
        donor = user_model.objects.filter(username=username_donor).first()
        if penerima is None or donor is None:
            continue  # Seed profil belum jalan.
        donasi = donasi_model.objects.filter(donor=donor, nama=nama).first()
        if donasi is None:
            continue  # Seed donasi belum jalan.
        klaim_model.objects.get_or_create(
            recipient=penerima,
            donation_id=donasi.pk,
            food_name=nama,
            defaults={
                "donor": donor,
                "donor_name": donor.username,
                "pickup_location": donasi.lokasi,
                "pickup_deadline": donasi.waktu_akhir_pengambilan,
                "portions": porsi,
                "pickup_time": now,
                "expires_at": now + timedelta(hours=6),
                "status": status,
                "picked_up_at": now - timedelta(hours=1) if status == "picked_up" else None,
                # Model historis di migration tidak menjalankan save() override
                # yang memuat kode ambil, jadi seed set kode unik di sini.
                "pickup_code": f"MBG-SEED{i:02d}",
            },
        )


def unseed(apps, schema_editor):
    user_model = apps.get_model("auth", "User")
    klaim_model = apps.get_model("klaim", "Claim")
    klaim_model.objects.filter(
        recipient__username__in=[k[0] for k in KLAIM],
        food_name__in=[k[2] for k in KLAIM],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("klaim", "0001_initial"),
        ("donasi", "0004_seed_donasi"),
        ("profil", "0003_seed_profil"),
    ]
    operations = [migrations.RunPython(seed, unseed)]
