from decimal import Decimal

from django import forms

from .models import UnitVenue, Venue

DUA_ENAM = Decimal("0.000001")


class KoordinatField(forms.DecimalField):
    """Menerima koma sebagai pemisah desimal (-6,3641) dan membulatkan ke 6 digit."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace("\u2212", "-").replace(",", ".")
        value = super().to_python(value)
        if isinstance(value, Decimal):
            value = value.quantize(DUA_ENAM)
        return value


class VenueForm(forms.ModelForm):
    latitude = KoordinatField(
        label="Latitude",
        max_digits=10,
        decimal_places=6,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "autocomplete": "off"}),
        error_messages={"required": "Latitude wajib diisi."},
    )
    longitude = KoordinatField(
        label="Longitude",
        max_digits=10,
        decimal_places=6,
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "decimal", "autocomplete": "off"}),
        error_messages={"required": "Longitude wajib diisi."},
    )

    class Meta:
        model = Venue
        fields = [
            "nama",
            "fakultas",
            "latitude",
            "longitude",
            "deskripsi_akses",
            "alamat",
        ]
        widgets = {
            "nama": forms.TextInput(attrs={"class": "form-control", "maxlength": 120}),
            "fakultas": forms.Select(attrs={"class": "form-select"}),
            "deskripsi_akses": forms.TextInput(attrs={"class": "form-control", "maxlength": 300}),
            "alamat": forms.HiddenInput(),
        }
        error_messages = {
            "nama": {"required": "Nama gedung wajib diisi."},
            "fakultas": {"required": "Pilih fakultas atau unit."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fakultas"].choices = [("", "Pilih fakultas")] + list(UnitVenue.choices)

    def clean(self):
        cleaned = super().clean()
        nama = (cleaned.get("nama") or "").strip()
        fakultas = cleaned.get("fakultas")
        if nama and fakultas:
            duplikat = Venue.objects.filter(nama__iexact=nama, fakultas=fakultas)
            if self.instance.pk:
                duplikat = duplikat.exclude(pk=self.instance.pk)
            if duplikat.exists():
                self.add_error("nama", "Venue dengan nama ini sudah ada di fakultas tersebut.")
        return cleaned
