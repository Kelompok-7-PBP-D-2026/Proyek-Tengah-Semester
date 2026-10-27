"""Admin configuration for claims."""
from django.contrib import admin

from .models import Claim


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    """Read-friendly admin for inspecting claims."""

    list_display = (
        "pickup_code", "food_name", "recipient", "donor",
        "portions", "status", "pickup_time", "expires_at", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("pickup_code", "food_name", "recipient__username", "donor__username")
    readonly_fields = (
        "pickup_code", "created_at", "updated_at", "picked_up_at", "closed_at",
    )
    raw_id_fields = ("recipient", "donor")