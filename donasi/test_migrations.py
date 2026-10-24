from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class PickupEndMigrationTests(TransactionTestCase):
    before = [("donasi", "0002_alter_donasi_jumlah_porsi")]
    after = [("donasi", "0003_pickup_end_and_automatic_stock_status")]

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.after)
        super().tearDown()

    def test_preserves_deadlines_and_stock_in_both_directions(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        donor = apps.get_model("auth", "User").objects.create(username="migration-donor", password="!")
        old_model = apps.get_model("donasi", "Donasi")
        start = timezone.now().replace(microsecond=0)
        end = start + timedelta(hours=3)
        ids = []
        for stock, status in [(0, "habis"), (6, "hampir_habis")]:
            item = old_model.objects.create(donor_id=donor.pk, nama=f"Donasi {stock}", jumlah_porsi=stock, lokasi="UI", waktu_tersedia=start, waktu_kedaluwarsa=end, status=status)
            ids.append(item.pk)
        executor = MigrationExecutor(connection)
        executor.migrate(self.after)
        apps = executor.loader.project_state(self.after).apps
        new_model = apps.get_model("donasi", "Donasi")
        for item_id, stock in zip(ids, [0, 6]):
            item = new_model.objects.get(pk=item_id)
            self.assertEqual(item.jumlah_porsi, stock)
            self.assertEqual(item.waktu_akhir_pengambilan, end)
        self.assertNotIn("status", [field.name for field in new_model._meta.fields])
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        apps = executor.loader.project_state(self.before).apps
        restored = apps.get_model("donasi", "Donasi")
        self.assertEqual(restored.objects.get(pk=ids[0]).status, "habis")
        self.assertEqual(restored.objects.get(pk=ids[1]).status, "tersedia")
        self.assertEqual(restored.objects.get(pk=ids[1]).waktu_kedaluwarsa, end)
