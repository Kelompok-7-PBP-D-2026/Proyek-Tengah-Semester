"""Adapter tunggal antara modul venue dan modul donasi (milik anggota lain).

Donasi.lokasi masih berupa teks bebas (lihat komentar di donasi/models.py), jadi donasi
dicocokkan ke venue lewat nama gedung (tanpa membedakan huruf besar/kecil). Setelah
Donasi memakai ForeignKey ke Venue, cukup ubah dua fungsi di bawah.
"""
from django.apps import apps
from django.utils import timezone

DONATION_MODEL = "donasi.Donasi"


def _donation_model():
    try:
        return apps.get_model(DONATION_MODEL)
    except (LookupError, ValueError):
        return None


def donasi_di_venue(venue):
    """Donasi yang masa pengambilannya belum selesai di venue ini."""
    model = _donation_model()
    if model is None:
        return []
    return model._default_manager.filter(
        lokasi__iexact=venue.nama,
        waktu_akhir_pengambilan__gt=timezone.now(),
    ).order_by("waktu_akhir_pengambilan", "pk")


def jumlah_donasi_aktif(venue):
    """Donasi yang masih punya stok dan belum lewat batas pengambilan."""
    model = _donation_model()
    if model is None:
        return 0
    return donasi_di_venue(venue).filter(jumlah_porsi__gt=0).count()
