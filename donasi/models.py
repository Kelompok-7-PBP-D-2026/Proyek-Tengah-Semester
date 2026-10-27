from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

MAX_PORSI = 2_147_483_647  # Batas aman PositiveIntegerField, termasuk di PostgreSQL.


def foto_donasi_path(instance, filename):
    """Membuat nama file foto yang unik di folder media/donasi."""
    # Nama acak mencegah bentrok dan tidak memakai nama file dari pengguna secara langsung.
    extension = filename.rsplit(".", 1)[-1].lower()
    return f"donasi/{uuid4().hex}.{extension}"


class Donasi(models.Model):
    """Makanan surplus yang ditawarkan donor untuk diambil penerima."""

    class Status(models.TextChoices):
        TERSEDIA = "tersedia", "Tersedia"
        HABIS = "habis", "Habis"

    donor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="donasi"
    )
    nama = models.CharField("Nama makanan", max_length=140)
    jumlah_porsi = models.PositiveIntegerField(
        "Jumlah porsi", validators=[MinValueValidator(0), MaxValueValidator(MAX_PORSI)]
    )
    # Nama Venue disimpan sebagai teks sesuai kontrak integrasi Venue dan Klaim.
    lokasi = models.CharField("Lokasi pengambilan", max_length=200)
    waktu_tersedia = models.DateTimeField("Tersedia mulai")
    waktu_akhir_pengambilan = models.DateTimeField("Akhir pengambilan")
    foto = models.ImageField("Foto makanan", upload_to=foto_donasi_path, blank=True)
    catatan = models.CharField(max_length=200, blank=True)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diperbarui_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-dibuat_pada", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(waktu_akhir_pengambilan__gt=models.F("waktu_tersedia")),
                name="donasi_pickup_end_after_start",
            ),
        ]

    def __str__(self):
        return self.nama

    def get_absolute_url(self):
        return reverse("donasi:detail", args=[self.pk])

    def clean(self):
        super().clean()
        errors = {}
        # Rapikan input teks dan tolak nilai yang hanya berisi spasi.
        for field, label in [("nama", "Nama makanan"), ("lokasi", "Lokasi pengambilan")]:
            value = getattr(self, field)
            if isinstance(value, str):
                setattr(self, field, value.strip())
                if value and not value.strip():
                    errors[field] = f"{label} wajib diisi."
        if isinstance(self.waktu_tersedia, datetime) and isinstance(self.waktu_akhir_pengambilan, datetime):
            # Batas akhir harus benar-benar sesudah waktu makanan mulai tersedia.
            if self.waktu_akhir_pengambilan <= self.waktu_tersedia:
                errors["waktu_akhir_pengambilan"] = "Akhir pengambilan harus setelah waktu mulai pengambilan."
        if errors:
            raise ValidationError(errors)

    @property
    def pengambilan_selesai(self):
        """True jika batas akhir pengambilan sudah lewat."""
        return self.waktu_akhir_pengambilan <= timezone.now()

    @property
    def status(self):
        """Status stok dihitung otomatis, bukan diisi melalui form."""
        return self.Status.TERSEDIA if self.jumlah_porsi > 0 else self.Status.HABIS

    @property
    def status_tampilan(self):
        """Status untuk UI; waktu berakhir lebih utama daripada kondisi stok."""
        if self.pengambilan_selesai:
            return "Pengambilan selesai"
        return self.Status(self.status).label

    @property
    def waktu_tersedia_wib(self):
        """Waktu mulai yang sudah dikonversi dari database ke WIB."""
        return timezone.localtime(self.waktu_tersedia, ZoneInfo("Asia/Jakarta"))

    @property
    def waktu_akhir_pengambilan_wib(self):
        """Waktu akhir yang sudah dikonversi dari database ke WIB."""
        return timezone.localtime(self.waktu_akhir_pengambilan, ZoneInfo("Asia/Jakarta"))
