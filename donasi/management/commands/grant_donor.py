from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from profil.models import JenisDonor, ProfilDonor


class Command(BaseCommand):
    help = (
        "Berikan akses donor ke akun Django yang sudah ada dengan membuat ProfilDonor "
        "bila akun tersebut belum punya. Tidak membuat akun atau kata sandi baru."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--nama-unit",
            default=None,
            help="Nama unit penyelenggara. Default: username.",
        )
        parser.add_argument(
            "--jenis",
            default=JenisDonor.PANITIA,
            help=f"Jenis donor: {', '.join(JenisDonor.values)}. Default: {JenisDonor.PANITIA}.",
        )

    def handle(self, *args, **options):
        user_model = get_user_model()
        try:
            user = user_model.objects.get(username=options["username"])
        except user_model.DoesNotExist:
            raise CommandError("Akun tidak ditemukan. Buat akun terlebih dahulu.")

        jenis = options["jenis"]
        if jenis not in JenisDonor.values:
            raise CommandError(
                f"Jenis donor tidak dikenal: {jenis}. Pilihan: {', '.join(JenisDonor.values)}."
            )

        profil, dibuat = ProfilDonor.objects.get_or_create(
            user=user,
            defaults={
                "nama_unit": options["nama_unit"] or user.get_username(),
                "jenis": jenis,
                "kontak": "",
            },
        )
        if dibuat:
            self.stdout.write(
                self.style.SUCCESS(f"Akses donor diberikan kepada {user.get_username()}.")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"{user.get_username()} sudah punya profil donor.")
            )
