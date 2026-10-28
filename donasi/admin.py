from django.contrib import admin

from .models import Donasi
from .forms import DonasiForm


# Mengatur tampilan dan fitur model Donasi pada halaman Django Admin.
@admin.register(Donasi)
class DonasiAdmin(admin.ModelAdmin):
    form = DonasiForm
    list_display = ["nama", "donor", "jumlah_porsi", "lokasi", "status", "waktu_akhir_pengambilan"]
    list_filter = ["lokasi"]
    search_fields = ["nama", "lokasi", "donor__username"]
    readonly_fields = ["dibuat_pada", "diperbarui_pada"]
