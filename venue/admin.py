from django.contrib import admin

from .models import Venue


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("nama", "fakultas", "latitude", "longitude", "diubah_pada")
    list_filter = ("fakultas",)
    search_fields = ("nama", "alamat")
