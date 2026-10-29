from django.contrib import admin

from .models import Laporan


@admin.register(Laporan)
class LaporanAdmin(admin.ModelAdmin):
    list_display = (
        "judul",
        "periode_mulai",
        "periode_selesai",
        "status",
        "dibuat_oleh",
    )
    list_filter = ("status",)
    search_fields = ("judul",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
