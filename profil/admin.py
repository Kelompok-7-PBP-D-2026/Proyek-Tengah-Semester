from django.contrib import admin

from .models import ProfilDonor, ProfilPenerima


@admin.register(ProfilDonor)
class ProfilDonorAdmin(admin.ModelAdmin):
    list_display = ("nama_unit", "jenis", "kontak", "terverifikasi", "dibuat_pada")
    list_filter = ("jenis", "terverifikasi")
    search_fields = ("nama_unit", "kontak", "user__username")
    actions = ("tandai_terverifikasi",)

    @admin.action(description="Tandai profil terpilih sebagai terverifikasi")
    def tandai_terverifikasi(self, request, queryset):
        jumlah = queryset.update(terverifikasi=True)
        self.message_user(request, f"{jumlah} profil donor ditandai terverifikasi.")


@admin.register(ProfilPenerima)
class ProfilPenerimaAdmin(admin.ModelAdmin):
    list_display = ("nama_lengkap", "nim", "fakultas", "terverifikasi", "dibuat_pada")
    list_filter = ("fakultas", "terverifikasi")
    search_fields = ("nama_lengkap", "nim", "user__username")
    actions = ("tandai_terverifikasi",)

    @admin.action(description="Tandai profil terpilih sebagai terverifikasi")
    def tandai_terverifikasi(self, request, queryset):
        jumlah = queryset.update(terverifikasi=True)
        self.message_user(request, f"{jumlah} profil penerima ditandai terverifikasi.")
