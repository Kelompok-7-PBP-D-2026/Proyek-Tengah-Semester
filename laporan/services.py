from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone
from django.utils.module_loading import import_string

from .models import Laporan


class SumberDataBelumTersedia(Exception):
    pass


class HasilAgregasiTidakValid(ValueError):
    pass


@dataclass(frozen=True)
class RingkasanDampak:
    total_porsi: int
    jumlah_donor: int
    jumlah_penerima: int

    def validate(self):
        for value in (self.total_porsi, self.jumlah_donor, self.jumlah_penerima):
            if type(value) is not int or not 0 <= value <= 9_223_372_036_854_775_807:
                raise HasilAgregasiTidakValid("Ringkasan harus berisi bilangan bulat nonnegatif.")


def sumber_terhubung():
    return bool(getattr(settings, "LAPORAN_AGGREGATOR", ""))


def ringkasan_periode(periode_mulai, periode_selesai):
    provider_path = getattr(settings, "LAPORAN_AGGREGATOR", "")
    if not provider_path:
        raise SumberDataBelumTersedia(
            "Data Klaim belum terhubung. Laporan tetap tersimpan; angka dampak belum tersedia."
        )
    provider = import_string(provider_path)
    result = provider(periode_mulai, periode_selesai)
    if not isinstance(result, RingkasanDampak):
        raise HasilAgregasiTidakValid("Sumber data harus mengembalikan RingkasanDampak.")
    result.validate()
    return result


def hitung_laporan(laporan):
    result = ringkasan_periode(laporan.periode_mulai, laporan.periode_selesai)
    laporan.total_porsi = result.total_porsi
    laporan.jumlah_donor = result.jumlah_donor
    laporan.jumlah_penerima = result.jumlah_penerima
    laporan.status = Laporan.Status.SIAP
    laporan.dihitung_pada = timezone.now()
    laporan.full_clean()
    laporan.save()
    return laporan
