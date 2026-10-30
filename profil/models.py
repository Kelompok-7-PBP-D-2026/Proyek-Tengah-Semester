from django.conf import settings
from django.db import models


class JenisDonor(models.TextChoices):
    PANITIA = "panitia_acara", "Panitia Acara"
    HIMPUNAN = "himpunan", "Himpunan / UKM"
    KANTIN = "kantin", "Kantin Kampus"
    KATERING = "katering", "Mitra Katering"


class Fakultas(models.TextChoices):
    FASILKOM = "fasilkom", "Fasilkom"
    FT = "ft", "Fakultas Teknik"
    FMIPA = "fmipa", "FMIPA"
    FEB = "feb", "FEB"
    FH = "fh", "FH"
    FK = "fk", "FK"
    FIK = "fik", "FIK"
    FISIP = "fisip", "FISIP"
    FPSI = "fpsi", "F.Psi"
    FIB = "fib", "FIB"
    FF = "ff", "FF"
    VOKASI = "vokasi", "Vokasi"


def _inisial(nama):
    """Dua huruf inisial untuk avatar bulat, mis. 'Kantin Fasilkom' -> 'KF'."""
    kata = [bagian for bagian in str(nama).split() if bagian]
    if not kata:
        return "?"
    if len(kata) == 1:
        return kata[0][:2].upper()
    return (kata[0][0] + kata[1][0]).upper()


class ProfilDonor(models.Model):
    """Profil penyelenggara acara, kantin, atau katering yang punya makanan surplus."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profil_donor",
    )
    nama_unit = models.CharField("nama unit / penyelenggara", max_length=100)
    jenis = models.CharField(
        "jenis donor",
        max_length=20,
        choices=JenisDonor.choices,
        default=JenisDonor.PANITIA,
    )
    kontak = models.CharField(
        "kontak penanggung jawab",
        max_length=100,
        help_text="Email atau nomor WhatsApp.",
    )
    deskripsi = models.TextField(blank=True)
    terverifikasi = models.BooleanField("sudah diverifikasi admin", default=False)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diubah_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nama_unit"]
        verbose_name = "profil donor"
        verbose_name_plural = "profil donor"

    @property
    def inisial(self):
        """Inisial untuk avatar (dipakai template, tidak disimpan di DB)."""
        return _inisial(self.nama_unit)

    def __str__(self):
        return f"{self.nama_unit} ({self.get_jenis_display()})"


class ProfilPenerima(models.Model):
    """Profil mahasiswa atau komunitas penerima makanan."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profil_penerima",
    )
    nama_lengkap = models.CharField(max_length=100)
    nim = models.CharField("NIM", max_length=10, unique=True)
    fakultas = models.CharField(max_length=20, choices=Fakultas.choices)
    kontak = models.CharField(
        "kontak",
        max_length=100,
        help_text="Email atau nomor WhatsApp.",
    )
    terverifikasi = models.BooleanField("sudah diverifikasi admin", default=False)
    dibuat_pada = models.DateTimeField(auto_now_add=True)
    diubah_pada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nama_lengkap"]
        verbose_name = "profil penerima"
        verbose_name_plural = "profil penerima"

    @property
    def inisial(self):
        """Inisial untuk avatar (dipakai template, tidak disimpan di DB)."""
        return _inisial(self.nama_lengkap)

    def __str__(self):
        return f"{self.nama_lengkap} ({self.nim})"
