from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse


class UnitVenue(models.TextChoices):
    """Fakultas atau unit pemilik venue. Kode sama dengan profil.models.Fakultas."""

    FASILKOM = "fasilkom", "Fasilkom UI"
    FT = "ft", "Fakultas Teknik"
    FEB = "feb", "Fakultas Ekonomi"
    FMIPA = "fmipa", "FMIPA UI"
    FH = "fh", "Fakultas Hukum"
    FK = "fk", "Fakultas Kedokteran"
    FIK = "fik", "Fakultas Ilmu Keperawatan"
    FISIP = "fisip", "FISIP UI"
    FPSI = "fpsi", "Fakultas Psikologi"
    FIB = "fib", "Fakultas Ilmu Pengetahuan Budaya"
    FF = "ff", "Fakultas Farmasi"
    VOKASI = "vokasi", "Vokasi UI"
    KAMPUS = "kampus", "Gedung Pusat"


# Nama pendek untuk chip filter dan badge kartu (sesuai Figma: Fasilkom, Teknik, FEB, Kampus).
SINGKAT = {
    "fasilkom": "Fasilkom",
    "ft": "Teknik",
    "feb": "FEB",
    "fmipa": "FMIPA",
    "fh": "FH",
    "fk": "FK",
    "fik": "FIK",
    "fisip": "FISIP",
    "fpsi": "F.Psi",
    "fib": "FIB",
    "ff": "FF",
    "vokasi": "Vokasi",
    "kampus": "Kampus",
}


class Venue(models.Model):
    """Titik pengambilan makanan di kampus."""

    nama = models.CharField("Nama gedung", max_length=120)
    fakultas = models.CharField("Fakultas", max_length=20, choices=UnitVenue.choices)
    alamat = models.CharField(
        "Alamat dari OpenStreetMap",
        max_length=255,
        blank=True,
        help_text="Terisi otomatis saat memilih hasil pencarian alamat.",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    deskripsi_akses = models.CharField("Deskripsi akses", max_length=300, blank=True)
    dibuat_oleh = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="venue_dibuat",
    )
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diubah_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nama", "pk"]
        verbose_name = "venue"
        verbose_name_plural = "venue"
        constraints = [
            models.UniqueConstraint(
                Lower("nama"), "fakultas", name="venue_nama_fakultas_unik"
            ),
        ]

    def __str__(self):
        return f"{self.nama} ({self.get_fakultas_display()})"

    def get_absolute_url(self):
        return reverse("venue:detail", args=[self.pk])

    def clean(self):
        super().clean()
        if isinstance(self.nama, str):
            self.nama = self.nama.strip()
            if not self.nama:
                raise ValidationError({"nama": "Nama gedung wajib diisi."})

    @property
    def unit_singkat(self):
        return SINGKAT.get(self.fakultas, self.get_fakultas_display())

    @property
    def nama_awal(self):
        """Kata pertama nama (untuk judul dua warna: LOBI GEDUNG A)."""
        return self.nama.split(" ", 1)[0]

    @property
    def nama_sisa(self):
        parts = self.nama.split(" ", 1)
        return parts[1] if len(parts) > 1 else ""

    @property
    def gedung(self):
        return self.alamat or self.nama
