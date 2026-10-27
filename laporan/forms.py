from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import translation
from django.utils.formats import date_format

from .models import Laporan
from .permissions import is_admin


class AdminLoginForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not is_admin(user):
            raise forms.ValidationError(
                "Akun ini tidak memiliki akses pengelola laporan.", code="forbidden"
            )


class LaporanForm(forms.ModelForm):
    judul = forms.CharField(
        label="Judul laporan",
        max_length=160,
        required=False,
        help_text="Opsional, otomatis memakai nama periode.",
    )

    def clean(self):
        data = super().clean()
        start, end = data.get("periode_mulai"), data.get("periode_selesai")
        if not data.get("judul") and start and end:
            with translation.override("id"):
                if (start.year, start.month) == (end.year, end.month):
                    period = date_format(start, "F Y")
                else:
                    start_label = date_format(start, "j M Y")
                    end_label = date_format(end, "j M Y")
                    period = f"{start_label} – {end_label}"
            data["judul"] = f"Laporan Dampak {period}"
        return data

    class Meta:
        model = Laporan
        fields = ["judul", "periode_mulai", "periode_selesai", "catatan"]
        labels = {
            "judul": "Judul laporan",
            "periode_mulai": "Periode mulai",
            "periode_selesai": "Periode selesai",
            "catatan": "Catatan untuk laporan",
        }
        help_texts = {
            "periode_mulai": "Tanggal pertama dalam laporan.",
            "periode_selesai": "Tidak boleh sebelum periode mulai.",
            "catatan": "Opsional, tampil di bagian bawah PDF.",
        }
        widgets = {
            "periode_mulai": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "periode_selesai": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date"}
            ),
            "catatan": forms.Textarea(attrs={"rows": 1}),
        }


class FilterLaporanForm(forms.Form):
    q = forms.CharField(label="Cari judul", max_length=160, required=False)
    status = forms.ChoiceField(
        label="Status",
        required=False,
        choices=[("", "Semua status"), *Laporan.Status.choices],
    )
