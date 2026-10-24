from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Berikan grup Donor ke akun Django yang sudah ada. Tidak membuat akun baru."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options["username"])
        except get_user_model().DoesNotExist:
            raise CommandError("Akun tidak ditemukan. Buat akun terlebih dahulu.")
        group, _ = Group.objects.get_or_create(name="Donor")
        user.groups.add(group)
        self.stdout.write(self.style.SUCCESS(f"Akses donor diberikan kepada {user.get_username()}."))
