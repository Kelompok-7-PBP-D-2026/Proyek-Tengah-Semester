from zoneinfo import ZoneInfo

from django import forms
from django.utils import timezone

from .models import MAX_PORSI, Donasi


class WIBDateTimeField(forms.DateTimeField):
    def to_python(self, value):
        # Also parse wall-clock inputs correctly outside donation views, e.g. Django Admin.
        with timezone.override(ZoneInfo("Asia/Jakarta")):
            return super().to_python(value)


class DonasiForm(forms.ModelForm):
    class Meta:
        model = Donasi
        fields = [
            "nama", "jumlah_porsi", "lokasi", "waktu_tersedia",
            "waktu_akhir_pengambilan", "foto", "catatan",
        ]
        field_classes = {"waktu_tersedia": WIBDateTimeField, "waktu_akhir_pengambilan": WIBDateTimeField}
        labels = {
            "waktu_tersedia": "Mulai pengambilan",
            "waktu_akhir_pengambilan": "Akhir pengambilan",
            "jumlah_porsi": "Jumlah stok (porsi)",
        }
        error_messages = {
            "nama": {"required": "Nama makanan wajib diisi.", "max_length": "Nama makanan maksimal 140 karakter."},
            "lokasi": {"required": "Lokasi pengambilan wajib diisi.", "max_length": "Lokasi pengambilan maksimal 200 karakter."},
            "jumlah_porsi": {
                "required": "Jumlah stok wajib diisi.",
                "invalid": "Jumlah stok harus berupa angka bulat.",
                "min_value": "Jumlah stok tidak boleh negatif.",
                "max_value": "Jumlah stok terlalu besar. Maksimal 2.147.483.647 porsi.",
            },
            "waktu_tersedia": {"required": "Waktu mulai pengambilan wajib diisi.", "invalid": "Masukkan tanggal dan jam mulai pengambilan yang valid."},
            "waktu_akhir_pengambilan": {"required": "Batas akhir pengambilan wajib diisi.", "invalid": "Masukkan tanggal dan jam akhir pengambilan yang valid."},
            "foto": {
                "invalid_image": "File foto tidak valid atau rusak. Gunakan gambar JPG atau PNG.",
                "invalid_extension": "Gunakan foto berformat JPG atau PNG.",
                "contradiction": "Pilih salah satu: unggah foto baru atau hapus foto saat ini.",
                "empty": "File foto kosong. Pilih gambar JPG atau PNG yang valid.",
            },
            "catatan": {"max_length": "Catatan maksimal 200 karakter."},
        }
        widgets = {
            "nama": forms.TextInput(attrs={"placeholder": "Contoh: Nasi ayam bakar box"}),
            "jumlah_porsi": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "lokasi": forms.TextInput(attrs={"placeholder": "Contoh: Lobi Gedung A, Fasilkom UI", "list": "lokasi-options"}),
            "waktu_tersedia": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "waktu_akhir_pengambilan": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
            "foto": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png"}),
            "catatan": forms.Textarea(attrs={"rows": 2, "placeholder": "Bahan makanan, kondisi kemasan, atau petunjuk pengambilan."}),
        }
        help_texts = {
            "nama": "Wajib, maksimal 140 huruf.",
            "jumlah_porsi": "Isi jumlah porsi yang tersedia, minimal 1 porsi untuk donasi baru.",
            "lokasi": "Tulis titik pengambilan yang mudah ditemukan.",
            "waktu_tersedia": "Waktu mulai pengambilan (WIB), harus sebelum batas akhir.",
            "waktu_akhir_pengambilan": "Batas terakhir makanan bisa diambil (WIB).",
            "foto": "Opsional, JPG atau PNG, maksimal 5 MB.",
            "catatan": "Opsional, maksimal 200 huruf.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            field.widget.attrs["aria-describedby"] = f"id_{name}_help id_{name}_errors"
        self.fields["jumlah_porsi"].widget.attrs["max"] = MAX_PORSI
        self.fields["jumlah_porsi"].widget.attrs["min"] = 0 if self.instance.pk else 1
        if self.instance.pk:
            self.fields["jumlah_porsi"].help_text = "Isi sisa stok saat ini. Gunakan 0 jika sudah habis."
        # Explicit conversion keeps this module in WIB without changing other apps.
        if self.instance.pk:
            for name in ["waktu_tersedia", "waktu_akhir_pengambilan"]:
                value = getattr(self.instance, name)
                self.initial[name] = timezone.localtime(value, ZoneInfo("Asia/Jakarta")).replace(tzinfo=None)

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        if foto and hasattr(foto, "content_type"):
            if foto.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Ukuran foto maksimal 5 MB.")
            if foto.image.format not in {"JPEG", "PNG"}:
                raise forms.ValidationError("Gunakan foto berformat JPG atau PNG.")
            # Match the stored extension to the decoded image, even if renamed by the uploader.
            extension = "jpg" if foto.image.format == "JPEG" else "png"
            foto.name = f"foto.{extension}"
        return foto

    def clean_jumlah_porsi(self):
        value = self.cleaned_data["jumlah_porsi"]
        if not self.instance.pk and value == 0:
            raise forms.ValidationError("Stok donasi baru harus minimal 1 porsi.")
        return value

    def clean(self):
        data = super().clean()
        start = data.get("waktu_tersedia")
        end = data.get("waktu_akhir_pengambilan")
        if end and (not start or end > start) and end <= timezone.now():
            original = self.instance.waktu_akhir_pengambilan if self.instance.pk else None
            unchanged = original and end == original.replace(second=0, microsecond=0)
            closing = data.get("jumlah_porsi") == 0
            if not (unchanged and closing):
                self.add_error("waktu_akhir_pengambilan", "Akhir pengambilan harus di masa depan. Untuk menutup donasi lama, ubah sisa stok menjadi 0 tanpa mengubah waktunya.")
        return data
