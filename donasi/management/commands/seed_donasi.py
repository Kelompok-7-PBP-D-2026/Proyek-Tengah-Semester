from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from donasi.models import Donasi
from donasi.permissions import is_donor


class Command(BaseCommand):
    help = "Buat data donasi sintetis berlabel [Contoh]. Aman dijalankan ulang tanpa duplikat."

    def add_arguments(self, parser):
        parser.add_argument("--donor", required=True, help="Username akun donor yang sudah ada.")
        parser.add_argument("--count", type=int, default=50)

    def handle(self, *args, **options):
        if not 1 <= options["count"] <= 500:
            raise CommandError("Jumlah data harus antara 1 dan 500.")
        try:
            donor = get_user_model().objects.get(username=options["donor"])
        except get_user_model().DoesNotExist:
            raise CommandError("Akun donor tidak ditemukan.")
        if not is_donor(donor):
            raise CommandError("Akun harus aktif dan memiliki grup Donor atau akses superuser.")
        foods = ["Nasi ayam bakar box", "Roti isi dan snack", "Nasi goreng kantin", "Salad dan buah potong", "Kue basah seminar"]
        locations = ["Lobi Gedung A, Fasilkom UI", "Gedung Pusat Kegiatan", "Kantin Teknik", "Lobi FEB UI", "Lobi FMIPA UI"]
        created = 0
        now = timezone.now().replace(second=0, microsecond=0)
        for index in range(options["count"]):
            _, added = Donasi.objects.get_or_create(
                donor=donor, nama=f"[Contoh {index + 1:02d}] {foods[index % len(foods)]}",
                defaults={
                    "jumlah_porsi": 0 if index % 4 == 3 else 25 + index,
                    "lokasi": locations[index % len(locations)],
                    "waktu_tersedia": now + timedelta(days=index % 3, hours=-1),
                    "waktu_akhir_pengambilan": now + timedelta(days=index % 3, hours=6),
                    "catatan": "Data sintetis untuk demonstrasi tugas. Bukan donasi makanan sungguhan.",
                },
            )
            created += added
        self.stdout.write(self.style.SUCCESS(f"{created} donasi contoh dibuat; data yang sudah ada tidak diubah."))
