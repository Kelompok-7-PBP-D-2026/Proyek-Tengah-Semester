from django.db import migrations, models


def restore_status_from_stock(apps, schema_editor):
    donations = apps.get_model("donasi", "Donasi").objects.using(schema_editor.connection.alias)
    donations.filter(jumlah_porsi=0).update(status="habis")
    donations.filter(jumlah_porsi__gt=0).update(status="tersedia")


class Migration(migrations.Migration):
    dependencies = [("donasi", "0002_alter_donasi_jumlah_porsi")]

    operations = [
        migrations.RemoveConstraint(model_name="donasi", name="donasi_expiry_after_start"),
        migrations.RemoveConstraint(model_name="donasi", name="donasi_portions_match_status"),
        # Rename preserves every existing pickup deadline and its data.
        migrations.RenameField(model_name="donasi", old_name="waktu_kedaluwarsa", new_name="waktu_akhir_pengambilan"),
        migrations.AlterField(model_name="donasi", name="waktu_akhir_pengambilan", field=models.DateTimeField("Akhir pengambilan")),
        migrations.RunPython(migrations.RunPython.noop, restore_status_from_stock),
        migrations.RemoveField(model_name="donasi", name="status"),
        migrations.AddConstraint(
            model_name="donasi",
            constraint=models.CheckConstraint(
                condition=models.Q(waktu_akhir_pengambilan__gt=models.F("waktu_tersedia")),
                name="donasi_pickup_end_after_start",
            ),
        ),
    ]
