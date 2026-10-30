from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('laporan', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='laporan',
            name='jumlah_klaim',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='laporan',
            name='rincian_donor',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
