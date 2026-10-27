"""Management command: expire overdue pending claims and return their portions."""
from django.core.management.base import BaseCommand

from klaim.services import expire_overdue_claims


class Command(BaseCommand):
    """Run periodically (e.g. every 5 minutes) so donation stock stays accurate."""

    help = "Expire pending claims whose pickup window has passed and return their portions."

    def handle(self, *args, **options):
        count = expire_overdue_claims()
        self.stdout.write(self.style.SUCCESS(f"{count} claim(s) expired."))