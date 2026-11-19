from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import ProfilDonor, ProfilPenerima


class DaftarDonorForm(UserCreationForm):
    """Akun baru + profil donor dalam satu form."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    nama_unit = forms.CharField(max_length=100, label="Nama unit / penyelenggara")
    jenis = forms.ChoiceField(choices=ProfilDonor._meta.get_field("jenis").choices)
    kontak = forms.CharField(max_length=100, help_text="Email atau nomor WhatsApp.")
    deskripsi = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False)


class DaftarPenerimaForm(UserCreationForm):
    """Akun baru + profil penerima dalam satu form."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    nama_lengkap = forms.CharField(max_length=100)
    nim = forms.CharField(max_length=10, label="NIM")
    fakultas = forms.ChoiceField(choices=ProfilPenerima._meta.get_field("fakultas").choices)
    kontak = forms.CharField(max_length=100, help_text="Email atau nomor WhatsApp.")

    def clean_nim(self):
        nim = self.cleaned_data["nim"]
        if ProfilPenerima.objects.filter(nim=nim).exists():
            raise forms.ValidationError("NIM ini sudah terdaftar.")
        return nim


class ProfilDonorForm(forms.ModelForm):
    class Meta:
        model = ProfilDonor
        fields = ("nama_unit", "jenis", "kontak", "deskripsi", "alamat", "latitude", "longitude")
        widgets = {
            "deskripsi": forms.Textarea(attrs={"rows": 4}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }


class ProfilPenerimaForm(forms.ModelForm):
    class Meta:
        model = ProfilPenerima
        fields = ("nama_lengkap", "nim", "fakultas", "kontak")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # NIM dikunci setelah daftar supaya identitas tidak bisa diganti sembarangan.
        self.fields["nim"].disabled = True
