from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse

# Create your models here.


class Laporan(models.Model):
    class Status(models.TextChoices):
        DRAF = "draf", "Draf — menunggu data"
        SIAP = "siap", "Siap — sudah dihitung"

    judul = models.CharField(max_length=160)
    periode_mulai = models.DateField()
    periode_selesai = models.DateField()
    catatan = models.TextField(blank=True, max_length=3000)
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="laporan_dampak"
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.DRAF)
    total_porsi = models.PositiveBigIntegerField(null=True, blank=True)
    jumlah_donor = models.PositiveBigIntegerField(null=True, blank=True)
    jumlah_penerima = models.PositiveBigIntegerField(null=True, blank=True)
    dihitung_pada = models.DateTimeField(null=True, blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-dibuat_pada", "-pk"]
        verbose_name_plural = "laporan dampak"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(periode_selesai__gte=models.F("periode_mulai")),
                name="laporan_periode_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="draf", total_porsi__isnull=True,
                             jumlah_donor__isnull=True, jumlah_penerima__isnull=True,
                             dihitung_pada__isnull=True)
                    | models.Q(status="siap", total_porsi__isnull=False,
                               jumlah_donor__isnull=False, jumlah_penerima__isnull=False,
                               dihitung_pada__isnull=False)
                ),
                name="laporan_status_data_consistent",
            ),
        ]

    def __str__(self):
        return self.judul

    def get_absolute_url(self):
        return reverse("laporan:detail", args=[self.pk])

    def clean(self):
        super().clean()
        self.judul = self.judul.strip()
        if not self.judul:
            raise ValidationError({"judul": "Judul laporan wajib diisi."})
        if self.periode_mulai and self.periode_selesai and self.periode_selesai < self.periode_mulai:
            raise ValidationError({"periode_selesai": "Tanggal akhir tidak boleh sebelum tanggal mulai."})

    def reset_hasil(self):
        self.status = self.Status.DRAF
        self.total_porsi = self.jumlah_donor = self.jumlah_penerima = None
        self.dihitung_pada = None
