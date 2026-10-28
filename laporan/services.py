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
    jumlah_klaim: int | None = None
    rincian_donor: list[dict] | None = None

    def validate(self):
        for value in (self.total_porsi, self.jumlah_donor, self.jumlah_penerima):
            if type(value) is not int or not 0 <= value <= 9_223_372_036_854_775_807:
                raise HasilAgregasiTidakValid(
                    "Ringkasan harus berisi bilangan bulat nonnegatif."
                )
        if self.jumlah_klaim is not None:
            if (
                type(self.jumlah_klaim) is not int
                or not 0 <= self.jumlah_klaim <= 9_223_372_036_854_775_807
            ):
                raise HasilAgregasiTidakValid("Jumlah klaim tidak valid.")
        if self.rincian_donor is not None:
            if not isinstance(self.rincian_donor, list) or self.jumlah_klaim is None:
                raise HasilAgregasiTidakValid("Rincian donor memerlukan jumlah klaim.")
            ids = set()
            portions = 0
            for donor in self.rincian_donor:
                if not isinstance(donor, dict) or not {
                    "donor_id",
                    "nama",
                    "jenis",
                    "total_porsi",
                    "jumlah_penerima",
                }.issubset(donor):
                    raise HasilAgregasiTidakValid("Struktur rincian donor tidak valid.")
                donor_id = donor["donor_id"]
                if (
                    donor_id is not None
                    and (type(donor_id) is not int or donor_id <= 0)
                ) or donor_id in ids:
                    raise HasilAgregasiTidakValid("Identitas donor tidak valid.")
                ids.add(donor_id)
                for key in ("total_porsi", "jumlah_penerima"):
                    if (
                        type(donor[key]) is not int
                        or not 0 <= donor[key] <= 9_223_372_036_854_775_807
                    ):
                        raise HasilAgregasiTidakValid("Rincian donor tidak valid.")
                if not all(
                    isinstance(donor[key], str) and donor[key].strip()
                    for key in ("nama", "jenis")
                ):
                    raise HasilAgregasiTidakValid("Nama dan jenis donor wajib diisi.")
                if donor["jumlah_penerima"] > self.jumlah_penerima:
                    raise HasilAgregasiTidakValid(
                        "Jumlah penerima donor melebihi total."
                    )
                portions += donor["total_porsi"]
            if portions != self.total_porsi or len(ids - {None}) != self.jumlah_donor:
                raise HasilAgregasiTidakValid("Rincian donor tidak sesuai ringkasan.")


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
        raise HasilAgregasiTidakValid(
            "Sumber data harus mengembalikan RingkasanDampak."
        )
    result.validate()
    return result


def hitung_laporan(laporan):
    result = ringkasan_periode(laporan.periode_mulai, laporan.periode_selesai)
    laporan.total_porsi = result.total_porsi
    laporan.jumlah_donor = result.jumlah_donor
    laporan.jumlah_penerima = result.jumlah_penerima
    laporan.jumlah_klaim = result.jumlah_klaim
    laporan.rincian_donor = result.rincian_donor
    laporan.status = Laporan.Status.SIAP
    laporan.dihitung_pada = timezone.now()
    laporan.full_clean()
    laporan.save()
    return laporan
